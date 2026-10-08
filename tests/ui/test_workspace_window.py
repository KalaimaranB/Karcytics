"""Tests for WorkspaceWindow UI and logic."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

from karcytics.ui.theme import theme_manager
from karcytics.ui.windows.workspace_window import _PAGE_ANALYSIS, _PAGE_HOME, WorkspaceWindow


class TestWorkspaceWindow:
    @pytest.fixture
    def window(self, qtbot):
        # Setup mocks
        pm = MagicMock()
        pm.data = {"project_name": "Unit Testing"}
        pm.history_manager = MagicMock()

        mm = MagicMock()
        mm.get_available_modules.return_value = [
            {"id": "plugin_a", "name": "Plugin A", "icon": "A"}
        ]

        up = MagicMock()

        hub_cb = MagicMock()
        store_cb = MagicMock()

        store_cb = MagicMock()

        with patch("karcytics.ui.windows.workspace.hub_manager.HubManager.maybe_start_core_intro"):
            win = WorkspaceWindow(pm, mm, up, store_cb, hub_cb)
            qtbot.addWidget(win)
            return win

    def test_initialization(self, window):
        assert "Unit Testing" in window.windowTitle()
        assert window.root_stack.currentIndex() == _PAGE_HOME
        # Verify populated modules
        assert window.home_screen.modules_layout.count() == 1

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_open_module_success(self, mock_err, window, qtbot):
        manifest = {"id": "plugin_a", "display_name": "Plugin A", "name": "Plugin A", "icon": "A"}

        # Mock UI loader with a real QWidget to avoid Qt type issues
        class MockPanel(QWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.load_state = MagicMock()
                self.export_state = MagicMock()

        window.module_manager.load_module_ui.return_value = MockPanel

        window.plugin_manager.open_module(manifest)

        # Wait for async worker to finish
        qtbot.waitUntil(lambda: window.wizard_panel is not None, timeout=5000)

        assert window.current_module_id == "plugin_a"
        assert isinstance(window.wizard_panel, MockPanel)
        # Verify title change in toolbar
        assert "Plugin A" in window.analysis_toolbar.title_lbl.text()
        mock_err.assert_not_called()

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_open_module_switch_unloads_previous_before_loading_next(self, mock_err, window, qtbot):
        """Regression test for the hot-swap crash: switching from module A to
        module B must fully destroy A's panel and call module_manager.unload_module
        for it *before* B's panel is created — not race the two, which is what
        produced the ModuleNotFoundError / "wrapped C/C++ object" crash.
        """

        class PanelA(QWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.load_state = MagicMock()
                self.export_state = MagicMock()

        class PanelB(QWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.load_state = MagicMock()
                self.export_state = MagicMock()

        manifest_a = {"id": "plugin_a", "display_name": "Plugin A", "name": "Plugin A", "icon": "A"}
        manifest_b = {"id": "plugin_b", "display_name": "Plugin B", "name": "Plugin B", "icon": "B"}

        window.module_manager.load_module_ui.return_value = PanelA
        window.plugin_manager.open_module(manifest_a)
        qtbot.waitUntil(lambda: window.wizard_panel is not None, timeout=5000)
        assert isinstance(window.wizard_panel, PanelA)

        window.module_manager.load_module_ui.return_value = PanelB
        window.plugin_manager.open_module(manifest_b)

        # unload_module for the outgoing module must fire as part of the switch —
        # and only after PanelA's C++ object was actually destroyed, which
        # qtbot.waitUntil's event-loop pumping is what allows to happen at all.
        qtbot.waitUntil(lambda: window.module_manager.unload_module.called, timeout=5000)
        window.module_manager.unload_module.assert_called_once_with("plugin_a")

        qtbot.waitUntil(lambda: isinstance(window.wizard_panel, PanelB), timeout=5000)
        assert window.current_module_id == "plugin_b"
        mock_err.assert_not_called()

    def test_open_module_ignores_reentrant_call_during_switch(self, window, qtbot):
        """A second open_module() call while one is already in flight must be
        ignored rather than racing a second unload/load sequence against the first.
        """

        class SlowPanel(QWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

        manifest_a = {"id": "plugin_a", "display_name": "Plugin A", "name": "Plugin A", "icon": "A"}
        window.module_manager.load_module_ui.return_value = SlowPanel

        window.plugin_manager.open_module(manifest_a)
        assert window._switch_in_progress is True

        # Re-entrant call while the first switch is still in flight.
        window.plugin_manager.open_module(manifest_a)

        qtbot.waitUntil(lambda: window.wizard_panel is not None, timeout=5000)
        assert window.module_manager.load_module_ui.call_count == 1

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_open_module_failure(self, mock_exec, window, qtbot):
        manifest = {"id": "broken", "name": "Broken"}
        window.module_manager.load_module_ui.side_effect = Exception("Load Failed")

        window.plugin_manager.open_module(manifest)

        # Wait for error dialog
        qtbot.waitUntil(lambda: mock_exec.called, timeout=5000)
        mock_exec.assert_called_once()

    def test_history_integration(self, window, qtbot):
        """Verify that UI triggers push/undo/redo on HistoryManager."""
        window.current_module_id = "plugin_a"

        # Use simple widget with required methods
        class MockPanel(QWidget):
            def __init__(self):
                super().__init__()
                self.load_state = MagicMock()
                self.export_state = MagicMock()

        window.wizard_panel = MockPanel()
        window.wizard_panel.export_state.return_value = {"val": 1}

        history = MagicMock()
        window.project_manager.history_manager.get_module_history.return_value = history

        # 1. Push
        window._push_history()
        history.push.assert_called_with({"val": 1})

        # 2. Undo
        history.undo.return_value = {"val": 0}
        window.trigger_undo()
        window.wizard_panel.load_state.assert_called_with({"val": 0})

        # 3. Redo
        history.redo.return_value = {"val": 1}
        window.trigger_redo()
        window.wizard_panel.load_state.assert_called_with({"val": 1})

    def test_theme_changed_signal_rebuilds_hub(self, window, qtbot):
        """Verify that changing theme triggers UI rebuild logic."""
        old_home = window.home_screen

        with patch.object(window.hub_manager, "refresh_hub_workflows") as mock_refresh:
            theme_manager.theme_changed.emit()

            # The window destroys the old home and creates a new one
            assert window.home_screen is not old_home
            mock_refresh.assert_called_once()

    def test_return_to_hub_cleanup(self, window, qtbot):
        """Verify that returning to hub closes project and triggers callback."""
        window.return_to_hub()

        # Note: project_manager.close() might be called multiple times during window
        # destruction/handoff, so we verify it was called at least once.
        assert window.project_manager.close.called
        window.return_to_hub_callback.assert_called_once()

    def test_transition_animation_start(self, window, qtbot):
        """Verify that page transitions initiate animations."""
        window._transition_to_page(_PAGE_ANALYSIS)
        assert hasattr(window, "_anim_out")
        # Ensure the animation is targeting our fade effect
        assert window._anim_out.targetObject() is window._fade_effect
