"""Tests for PluginLoaderFactory._wire_theme_sync — keeps an isolated
module's window in sync with the Hub's live color palette (see
_load_ui_isolated's docstring in karcytics/core/plugins/loader.py).

Uses a lightweight QWidget double rather than a real ModuleStatusWidget +
PluginUIDaemon subprocess: this is purely a test of the wiring (when does a
push happen, does it stop happening after the widget is gone), which the
SDK's own test suite doesn't and shouldn't know about, since
ModuleStatusWidget itself has no idea the Hub's theme system exists.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from karcytics.core.plugins.loader import PluginLoaderFactory
from karcytics.ui.theme import Colors
from karcytics.ui.theme import theme_manager as hub_theme_manager


class _FakeStatusWidget(QWidget):
    STATE_RUNNING = "running"
    state_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.pushed_colors: list[dict[str, str]] = []

    def push_theme(self, colors: dict[str, str]) -> None:
        self.pushed_colors.append(colors)


def test_wire_theme_sync_pushes_current_colors_when_state_becomes_running(
    qapp: QApplication,
) -> None:  # noqa: ARG001
    widget = _FakeStatusWidget()
    PluginLoaderFactory._wire_theme_sync(widget)  # type: ignore[arg-type]

    widget.state_changed.emit(widget.STATE_RUNNING)

    assert len(widget.pushed_colors) == 1
    assert widget.pushed_colors[0]["ACCENT_PRIMARY"] == Colors.ACCENT_PRIMARY


def test_wire_theme_sync_ignores_non_running_state_transitions(qapp):  # noqa: ARG001
    widget = _FakeStatusWidget()
    PluginLoaderFactory._wire_theme_sync(widget)  # type: ignore[arg-type]

    widget.state_changed.emit("spawning")
    widget.state_changed.emit("crashed")

    assert widget.pushed_colors == []


def test_wire_theme_sync_pushes_again_on_hub_theme_change(qapp):  # noqa: ARG001
    widget = _FakeStatusWidget()
    PluginLoaderFactory._wire_theme_sync(widget)  # type: ignore[arg-type]

    try:
        hub_theme_manager.theme_changed.emit()
        assert len(widget.pushed_colors) == 1
    finally:
        widget.deleteLater()
        QApplication.processEvents()


def test_wire_theme_sync_disconnects_from_hub_once_widget_is_destroyed(qapp):  # noqa: ARG001
    """If the connection to the long-lived hub_theme_manager singleton isn't
    torn down when the widget goes away, the next Hub theme change would
    try to call push_theme() on a deleted C++ object and raise RuntimeError.
    """
    widget = _FakeStatusWidget()
    PluginLoaderFactory._wire_theme_sync(widget)  # type: ignore[arg-type]

    widget.deleteLater()
    QApplication.processEvents()
    QApplication.processEvents()

    hub_theme_manager.theme_changed.emit()  # must not raise
