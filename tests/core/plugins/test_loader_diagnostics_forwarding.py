"""Tests for PluginLoaderFactory._wire_diagnostics_forwarding — forwards an
isolated module's "diagnostics_error" events (pushed by a plugin's own
karcytics_sdk.plugin.runtime_services.diagnostics.report_error(...)) into
the Hub's real DiagnosticEngine.

Before this existed, nothing on the Hub side was ever subscribed to
event_received for that topic, so every one of those reports vanished
silently. Uses a lightweight QObject double rather than a real
PluginUIDaemon subprocess — this is purely a test of the wiring, mirroring
test_loader_theme_sync.py's approach for the same reason.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from karcytics.core.plugins.loader import PluginLoaderFactory


class _FakeDaemon(QObject):
    event_received = pyqtSignal(str, object)


def test_wire_diagnostics_forwarding_forwards_matching_topic(qapp, monkeypatch):  # noqa: ARG001
    calls = []
    monkeypatch.setattr(
        "karcytics.core.diagnostics.diagnostics.report_error",
        lambda **kwargs: calls.append(kwargs),
    )
    daemon = _FakeDaemon()
    PluginLoaderFactory._wire_diagnostics_forwarding(daemon)

    daemon.event_received.emit(
        "diagnostics_error",
        {
            "message": "bad transform",
            "exception": "ValueError: nope",
            "traceback": "Traceback (most recent call last):\n...",
            "plugin_id": "flow_cytometry",
            "fatal": False,
        },
    )

    assert calls == [
        {
            "message": "bad transform",
            "plugin_id": "flow_cytometry",
            "fatal": False,
            "exception_repr": "ValueError: nope",
            "traceback_str": "Traceback (most recent call last):\n...",
        }
    ]


def test_wire_diagnostics_forwarding_ignores_other_topics(qapp, monkeypatch):  # noqa: ARG001
    calls = []
    monkeypatch.setattr(
        "karcytics.core.diagnostics.diagnostics.report_error",
        lambda **kwargs: calls.append(kwargs),
    )
    daemon = _FakeDaemon()
    PluginLoaderFactory._wire_diagnostics_forwarding(daemon)

    daemon.event_received.emit("window_closed", {})

    assert calls == []


def test_wire_diagnostics_forwarding_ignores_non_dict_payload(qapp, monkeypatch):  # noqa: ARG001
    calls = []
    monkeypatch.setattr(
        "karcytics.core.diagnostics.diagnostics.report_error",
        lambda **kwargs: calls.append(kwargs),
    )
    daemon = _FakeDaemon()
    PluginLoaderFactory._wire_diagnostics_forwarding(daemon)

    daemon.event_received.emit("diagnostics_error", "not a dict")

    assert calls == []


def test_wire_diagnostics_forwarding_is_idempotent_per_daemon(qapp, monkeypatch):  # noqa: ARG001
    """get_instance() returns the same daemon singleton on every reopen of an
    already-running module — wiring must not stack a second listener.
    """
    calls = []
    monkeypatch.setattr(
        "karcytics.core.diagnostics.diagnostics.report_error",
        lambda **kwargs: calls.append(kwargs),
    )
    daemon = _FakeDaemon()
    PluginLoaderFactory._wire_diagnostics_forwarding(daemon)
    PluginLoaderFactory._wire_diagnostics_forwarding(daemon)

    daemon.event_received.emit("diagnostics_error", {"message": "x"})

    assert len(calls) == 1
