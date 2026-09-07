"""Tests for `_run_smoke_test`'s own responsibilities: parsing args,
force-installing the requested plugin, starting `CoreServicesServer` (see
docs/internal/26 — an isolated worker's startup theme gate needs this
reachable or it refuses to build any window at all), and routing to
`_run_smoke_test_in_process` or `_run_smoke_test_isolated` based on the
plugin's own `process_model`. The two dispatched functions' own behavior is
covered separately (tests/test_boot_cli.py, tests/test_boot_cli_isolated.py)
— these tests replace both with sentinel stubs so a failure here can only
mean the routing/lifecycle logic itself is wrong, not something downstream
of it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


class _MockNetworkUpdater:
    plugin_dir = Path("/tmp/plugins")
    registry_url = "https://example.com/test-registry.json"

    def fetch_remote_registry(self, url: str) -> dict[str, Any]:  # noqa: ARG002
        # Any plugin id "exists" — the point of these tests is routing after
        # install, not the registry lookup itself.
        return {
            "plugins": {
                "flow_cytometry": {"version": "1.0.0", "repo_url": "mock://repo"},
                "test_plugin": {"version": "1.0.0", "repo_url": "mock://repo"},
            }
        }

    def install_plugin(self, plugin_id: str, plugin_info: dict[str, Any]) -> tuple[bool, str]:  # noqa: ARG002
        return True, "Success"


class _MockModuleManager:
    """`.modules` is populated directly by the test (standing in for what a
    real `reload_modules()` call would discover from disk) — `reload_modules`
    itself is a no-op double, since `_install_plugin_for_smoke_test` calls it
    but this test suite isn't exercising plugin discovery.
    """

    def __init__(self, modules: dict[str, Any]) -> None:
        self.modules = modules
        self.reload_calls = 0

    def reload_modules(self) -> None:
        self.reload_calls += 1


class _FakeCoreServicesServer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _patch_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("karcytics.core.network_updater.NetworkUpdater", _MockNetworkUpdater)
    monkeypatch.setattr(
        "karcytics.core.network.plugin_registry_fetcher.PluginRegistryFetcher.fetch",
        lambda *args: {"project": {"name": "test"}},
    )
    monkeypatch.setattr(
        "karcytics.core.network.plugin_registry_fetcher.PluginRegistryFetcher.enrich_entry",
        lambda *args: None,
    )
    monkeypatch.setattr(
        "karcytics.core.network.plugin_registry_fetcher.PluginRegistryFetcher.resolve_download_url",
        lambda *args: "mock://download",
    )


def _patch_core_services(monkeypatch: pytest.MonkeyPatch) -> _FakeCoreServicesServer:
    server = _FakeCoreServicesServer()
    monkeypatch.setattr(
        "karcytics.core.core_services_bootstrap.start_core_services", lambda: server
    )
    return server


def test_isolated_manifest_routes_to_isolated_smoke_test(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_install(monkeypatch)
    server = _patch_core_services(monkeypatch)

    import karcytics.__main__ as main_module

    calls: list[tuple[str, str | None]] = []

    def _fake_isolated(module_manager, plugin_id, data_file) -> int:  # noqa: ARG001
        calls.append(("isolated", data_file))
        return 0

    monkeypatch.setattr(main_module, "_run_smoke_test_isolated", _fake_isolated)
    monkeypatch.setattr(
        main_module,
        "_run_smoke_test_in_process",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not route here")),
    )

    mm = _MockModuleManager({"flow_cytometry": {"manifest": {"process_model": "isolated"}}})
    monkeypatch.setattr("karcytics.core.module_manager.ModuleManager", lambda: mm)

    exit_code = main_module._run_smoke_test(
        ["karcytics", "--smoke-test=flow_cytometry", "/tmp/x.fcs"]
    )

    assert exit_code == 0
    assert calls == [("isolated", "/tmp/x.fcs")]
    assert server.stopped is True


def test_in_process_manifest_routes_to_in_process_smoke_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_install(monkeypatch)
    server = _patch_core_services(monkeypatch)

    import karcytics.__main__ as main_module

    calls: list[tuple[str, str | None]] = []

    def _fake_in_process(module_manager, plugin_id, data_file) -> int:  # noqa: ARG001
        calls.append(("in_process", data_file))
        return 0

    monkeypatch.setattr(main_module, "_run_smoke_test_in_process", _fake_in_process)
    monkeypatch.setattr(
        main_module,
        "_run_smoke_test_isolated",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not route here")),
    )

    # No process_model key at all — must default to in-process, same as
    # PluginManifest.process_model's own "in_process" default.
    mm = _MockModuleManager({"test_plugin": {"manifest": {}}})
    monkeypatch.setattr("karcytics.core.module_manager.ModuleManager", lambda: mm)

    exit_code = main_module._run_smoke_test(["karcytics", "--smoke-test=test_plugin", "/tmp/x.fcs"])

    assert exit_code == 0
    assert calls == [("in_process", "/tmp/x.fcs")]
    assert server.stopped is True


def test_core_services_stopped_even_when_dispatched_test_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_install(monkeypatch)
    server = _patch_core_services(monkeypatch)

    import karcytics.__main__ as main_module

    def _boom(*_a: Any, **_k: Any) -> int:
        raise RuntimeError("simulated crash inside the dispatched smoke test")

    monkeypatch.setattr(main_module, "_run_smoke_test_in_process", _boom)

    mm = _MockModuleManager({"test_plugin": {"manifest": {}}})
    monkeypatch.setattr("karcytics.core.module_manager.ModuleManager", lambda: mm)

    with pytest.raises(RuntimeError, match="simulated crash"):
        main_module._run_smoke_test(["karcytics", "--smoke-test=test_plugin", "/tmp/x.fcs"])

    assert server.stopped is True


def test_missing_plugin_after_install_raises_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_install(monkeypatch)
    _patch_core_services(monkeypatch)

    import karcytics.__main__ as main_module

    mm = _MockModuleManager({})  # install "succeeded" but nothing showed up
    monkeypatch.setattr("karcytics.core.module_manager.ModuleManager", lambda: mm)

    with pytest.raises(RuntimeError, match="not discoverable"):
        main_module._run_smoke_test(["karcytics", "--smoke-test=test_plugin", "/tmp/x.fcs"])


def test_no_plugin_id_is_a_bare_boot_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """No --smoke-test value at all: must not install anything, must not
    start CoreServicesServer, must not touch either dispatched function —
    just prove the app object itself can be constructed and torn down.
    """
    import karcytics.__main__ as main_module

    core_services_called = False

    def _fail_if_called() -> Any:
        nonlocal core_services_called
        core_services_called = True
        raise AssertionError("should not be called for a bare boot check")

    monkeypatch.setattr(
        "karcytics.core.core_services_bootstrap.start_core_services", _fail_if_called
    )
    monkeypatch.setattr(
        main_module,
        "_run_smoke_test_in_process",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not route here")),
    )
    monkeypatch.setattr(
        main_module,
        "_run_smoke_test_isolated",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not route here")),
    )

    mm = _MockModuleManager({})
    monkeypatch.setattr("karcytics.core.module_manager.ModuleManager", lambda: mm)
    monkeypatch.setattr(main_module, "SMOKE_TEST_TICK_MS", 10)

    exit_code = main_module._run_smoke_test(["karcytics", "--smoke-test="])

    assert exit_code == 0
    assert core_services_called is False

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app:
        app.quit()
