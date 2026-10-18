"""Tests for `_run_smoke_test_isolated` — the isolated-plugin half of the
smoke test split in karcytics/__main__.py (see `_run_smoke_test_in_process`'s
own tests in tests/test_boot_cli.py for the in-process half).

A real isolated plugin drives an actual subprocess over msgpack/stdio (see
karcytics_sdk/plugin/daemon.py's `PluginUIDaemon`) — these tests replace that
with a fake daemon whose `event_received`/`process_exited` "signals" invoke
their connected callbacks synchronously, so a test can simulate the worker
process's asynchronous behavior (a `panel_data_ready` event landing, a crash)
without spawning anything or touching the real Qt cross-thread queued
connection machinery. What's under test is `_run_smoke_test_isolated`'s own
control flow — request/response handling, event-topic interpretation, timeout
and crash detection — not `PluginUIDaemon` itself, which has its own real,
subprocess-driven e2e coverage in the SDK repo.
"""

from __future__ import annotations

from typing import Any

import pytest

TEST_SPAWN_TIMEOUT_S = 0.2


class _FakeSignal:
    """Stands in for a Signal: `.connect()` records a callback,
    `.emit()` invokes every connected callback synchronously and immediately
    — unlike the real cross-thread signal this replaces, there is no queued
    connection to pump via QApplication.processEvents() here, so a test can
    call `.emit()` directly instead of needing a real background reader
    thread to produce it.
    """

    def __init__(self) -> None:
        self._slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        self._slots.append(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self._slots):
            slot(*args)


class _FakeIsolatedDaemon:
    """Fake `PluginUIDaemon` singleton. `call_log` records every `call()`
    invocation so a test can assert what was actually sent (e.g. that
    `inject_workflow`'s payload is `{}`, not `None` — see
    `_run_smoke_test_isolated`'s own comment on why that distinction matters).
    """

    _instances: dict[str, _FakeIsolatedDaemon] = {}

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self.pending_workflow = False
        self.event_received = _FakeSignal()
        self.process_exited = _FakeSignal()
        self.call_log: list[tuple[str, dict]] = []
        self.stopped = False
        # Configurable behavior, set by each test:
        self.ensure_started_error: Exception | None = None
        self.call_error: Exception | None = None
        self.call_result: dict = {"status": "ok"}
        self.emit_on_call: list[tuple[str, dict]] = []

    @classmethod
    def get_instance(cls, plugin_id: str, daemon_script_path: Any = None) -> _FakeIsolatedDaemon:  # noqa: ARG003
        if plugin_id not in cls._instances:
            cls._instances[plugin_id] = cls(plugin_id)
        return cls._instances[plugin_id]

    @classmethod
    def stop_instance(cls, plugin_id: str) -> None:
        daemon = cls._instances.pop(plugin_id, None)
        if daemon is not None:
            daemon.stopped = True

    @classmethod
    def reset(cls) -> None:
        cls._instances = {}

    def ensure_started(self, timeout: float = 30.0) -> None:  # noqa: ARG002
        if self.ensure_started_error is not None:
            raise self.ensure_started_error

    def call(self, method: str, kwargs: dict, timeout: float = 120.0) -> dict:  # noqa: ARG002
        self.call_log.append((method, kwargs))
        if self.call_error is not None:
            raise self.call_error
        for topic, payload in self.emit_on_call:
            self.event_received.emit(topic, payload)
        return self.call_result


@pytest.fixture(autouse=True)
def _reset_fake_daemon_registry():
    _FakeIsolatedDaemon.reset()
    yield
    _FakeIsolatedDaemon.reset()


def _patch_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginUIDaemon", _FakeIsolatedDaemon)
    monkeypatch.setattr(
        "karcytics.__main__.SMOKE_TEST_TIMEOUT_MS", int(TEST_SPAWN_TIMEOUT_S * 1000)
    )
    monkeypatch.setattr(
        "karcytics.__main__.SMOKE_TEST_ISOLATED_SPAWN_TIMEOUT_S", TEST_SPAWN_TIMEOUT_S
    )


class _MockModuleManager:
    def __init__(self, panel_factory: Any) -> None:
        self._panel_factory = panel_factory

    def load_module_ui(self, module_id: str) -> Any:  # noqa: ARG002
        return self._panel_factory


def test_isolated_success_returns_zero_on_panel_data_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")
    daemon.emit_on_call = [("panel_data_ready", {})]

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 0
    assert daemon.call_log == [("inject_workflow", {"payload": {}, "filename": "/tmp/sample.fcs"})]
    # Must go through the pending-workflow path, not the "already running"
    # dynamic-inject path — see _run_smoke_test_isolated's own comment.
    assert daemon.pending_workflow is True
    assert daemon.stopped is True


def test_isolated_returns_failure_on_workflow_injection_failed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")
    daemon.emit_on_call = [("workflow_injection_failed", {"error": "simulated failure"})]

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 1


def test_isolated_returns_failure_on_timeout_with_no_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing ever arrives on event_received — the exact failure mode a
    Hub-side routing bug (the isolated plugin proxy having no load_workflow)
    used to produce silently, via app.exec() with no quit condition wired.
    Now it must resolve, and resolve as a failure, within the timeout.
    """
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    _FakeIsolatedDaemon.get_instance("flow_cytometry")  # no emit_on_call configured

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 1


def test_isolated_returns_failure_when_worker_crashes_before_data_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")

    def _crash_instead(*_args: Any, **_kwargs: Any) -> dict:
        daemon.process_exited.emit()
        return {"status": "ok"}

    daemon.call = _crash_instead  # type: ignore[method-assign]

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 1


def test_isolated_returns_failure_when_daemon_fails_to_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """inject_workflow's own call() internally calls ensure_started() first
    — a ready-handshake failure (no CoreServicesServer reachable, a broken
    plugin .venv, ...) surfaces as an exception out of call() itself, not an
    event.
    """
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")
    daemon.call_error = RuntimeError("failed ready handshake")

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 1


def test_isolated_returns_failure_when_panel_factory_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(None), "flow_cytometry", "/tmp/sample.fcs"
    )

    assert exit_code == 1


def test_isolated_no_data_file_just_confirms_daemon_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    """No data file: the isolated smoke test's only job is confirming the
    daemon reaches ready — no inject_workflow call, no pending_workflow.
    """
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", None
    )

    assert exit_code == 0
    assert daemon.call_log == []
    assert daemon.pending_workflow is False


def test_isolated_no_data_file_returns_failure_when_daemon_fails_to_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_daemon(monkeypatch)
    from karcytics.__main__ import _run_smoke_test_isolated

    daemon = _FakeIsolatedDaemon.get_instance("flow_cytometry")
    daemon.ensure_started_error = RuntimeError("failed ready handshake")

    exit_code = _run_smoke_test_isolated(
        _MockModuleManager(lambda: object()), "flow_cytometry", None
    )

    assert exit_code == 1
