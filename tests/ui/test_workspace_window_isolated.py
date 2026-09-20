"""End-to-end test: opening an isolated module through the real
WorkspaceWindow/PluginLoaderManager choreography, driving a real
ModuleStatusWidget backed by a real PluginUIDaemon subprocess — not a mock
panel. Proves open_module() reveals it as a blocking overlay on root_stack
immediately, without switching to the analysis page or playing the Hub's own
GalacticLoader animation — an isolated module's real content is a separate
window with its own loading state, not anything the Hub itself is rendering.
"""

from unittest.mock import MagicMock, patch

import pytest
from karcytics_sdk.host.core_services import CoreServicesServer
from karcytics_sdk.host.module_status_widget import ModuleStatusWidget
from karcytics_sdk.plugin.daemon import PluginUIDaemon

from karcytics.ui.windows.workspace_window import _PAGE_HOME, WorkspaceWindow


@pytest.fixture(autouse=True)
def core_services():
    """`run()` now blocks on confirming the Hub's real theme before building
    any UI (see `ui_daemon_runtime._confirm_hub_theme_or_exit`) — without a
    reachable `CoreServicesServer`, `fast_worker_script` below would never
    reach "ready".
    """
    server = CoreServicesServer()
    server.register("theme.get_current_colors", lambda _kwargs: {"BG_DARKEST": "#0a0a0a"})
    server.start()
    PluginUIDaemon.set_core_services(server.port, server.token)
    yield server
    PluginUIDaemon._core_services_port = None
    PluginUIDaemon._core_services_token = None
    PluginUIDaemon._core_icon_path = None
    server.stop()


@pytest.fixture
def fast_worker_script(tmp_path):
    script_path = tmp_path / "fast_worker.py"
    code = """
from PyQt6.QtWidgets import QLabel
from karcytics_sdk.plugin.ui_daemon_runtime import run

def build_panel():
    return QLabel("fast")

if __name__ == "__main__":
    run(build_panel)
"""
    script_path.write_text(code, encoding="utf-8")
    return script_path


@pytest.fixture
def slow_worker_script(tmp_path):
    """Delays its ready event well past a normal crossfade — lets a test
    observe the Hub's own workspace before the daemon has reported ready.
    """
    script_path = tmp_path / "slow_worker.py"
    code = """
import time
from PyQt6.QtWidgets import QLabel
from karcytics_sdk.plugin.ui_daemon_runtime import run

def build_panel():
    time.sleep(2.0)
    return QLabel("slow")

if __name__ == "__main__":
    run(build_panel)
"""
    script_path.write_text(code, encoding="utf-8")
    return script_path


class TestWorkspaceWindowIsolatedModule:
    @pytest.fixture
    def window(self, qtbot):
        pm = MagicMock()
        pm.data = {"project_name": "Unit Testing"}
        pm.history_manager = MagicMock()

        mm = MagicMock()
        mm.get_available_modules.return_value = [
            {"id": "isolated_test_plugin", "name": "Isolated Test Plugin", "icon": "🧩"}
        ]
        # A real dict, not a MagicMock chain: open_module() reads
        # modules[id]["manifest"]["process_model"] to decide whether to skip
        # the Hub's own GalacticLoader warp animation entirely (see that
        # method) — a MagicMock attribute access would never equal
        # "isolated", silently exercising the wrong code path.
        isolated_entry = {"trust_level": "verified", "manifest": {"process_model": "isolated"}}
        mm.modules = {
            "isolated_test_plugin": isolated_entry,
            "isolated_test_plugin_slow": isolated_entry,
        }

        up = MagicMock()
        hub_cb = MagicMock()
        store_cb = MagicMock()

        with patch("karcytics.ui.windows.workspace.hub_manager.HubManager.maybe_start_core_intro"):
            win = WorkspaceWindow(pm, mm, up, store_cb, hub_cb)
            qtbot.addWidget(win)
            return win

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_open_isolated_module_reaches_running(
        self, mock_err, window, qtbot, fast_worker_script
    ):
        plugin_id = "isolated_test_plugin"

        def factory():
            daemon = PluginUIDaemon.get_instance(plugin_id, daemon_script_path=fast_worker_script)
            return ModuleStatusWidget(daemon, module_name="Isolated Test Plugin")

        window.module_manager.load_module_ui.return_value = factory

        manifest = {
            "id": plugin_id,
            "display_name": "Isolated Test Plugin",
            "name": "Isolated Test Plugin",
            "icon": "🧩",
        }

        try:
            window.plugin_manager.open_module(manifest)

            qtbot.waitUntil(lambda: window.wizard_panel is not None, timeout=5000)
            assert isinstance(window.wizard_panel, ModuleStatusWidget)
            assert window.module_overlay is window.wizard_panel

            qtbot.waitUntil(
                lambda: window.wizard_panel.state == ModuleStatusWidget.STATE_RUNNING, timeout=10000
            )
            # An isolated module never "enters" the Hub's own analysis page —
            # its real content is the separate window, not anything rendered
            # here — so the Hub stays exactly where it was.
            assert window.root_stack.currentIndex() == _PAGE_HOME

            assert window.current_module_id == plugin_id
            mock_err.assert_not_called()
        finally:
            PluginUIDaemon.stop_instance(plugin_id)

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_theme_switch_keeps_the_module_overlay_on_top(
        self, mock_err, window, qtbot, fast_worker_script
    ):
        """Regression test: ThemeManager.on_theme_changed() destroys and
        recreates home_screen on every theme switch (see that method's step
        4), then re-inserts the fresh instance into root_stack.
        module_overlay is a floating child of root_stack, not one of its
        pages, so that rebuild never touches it directly — but the newly
        inserted home_screen sibling still ends up stacked above it in paint
        order, silently burying an otherwise perfectly alive overlay behind
        the rebuilt page (it never actually disappeared, just stopped being
        visible). ThemeManager.on_theme_changed() must re-raise it, the same
        way it already does for hologram_overlay.
        """
        plugin_id = "isolated_test_plugin"

        def factory():
            daemon = PluginUIDaemon.get_instance(plugin_id, daemon_script_path=fast_worker_script)
            return ModuleStatusWidget(daemon, module_name="Isolated Test Plugin")

        window.module_manager.load_module_ui.return_value = factory

        manifest = {
            "id": plugin_id,
            "display_name": "Isolated Test Plugin",
            "name": "Isolated Test Plugin",
            "icon": "🧩",
        }

        try:
            window.plugin_manager.open_module(manifest)
            qtbot.waitUntil(lambda: window.module_overlay is not None, timeout=5000)
            overlay = window.module_overlay

            window.theme_manager.on_theme_changed()

            # Still the very same widget — the rebuild must not have
            # discarded or replaced it, only its stacking order was at risk.
            assert window.module_overlay is overlay
            assert overlay.geometry() == window.root_stack.rect()
            # Sibling widget paint order follows this list — the freshly
            # rebuilt home_screen was just appended to it too, so the
            # overlay must be re-raised back to the end (the top) or it's
            # the one now buried behind that new page instead of blocking it.
            assert window.root_stack.children()[-1] is overlay
        finally:
            PluginUIDaemon.stop_instance(plugin_id)

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_closing_the_module_hands_the_hub_back_immediately(
        self, mock_err, window, qtbot, fast_worker_script
    ):
        """A user-initiated close — unlike a crash — must give full
        interaction with the Hub back right away, not leave a "Reopen"
        overlay sitting in front of whatever the user was doing.
        """
        plugin_id = "isolated_test_plugin"

        def factory():
            daemon = PluginUIDaemon.get_instance(plugin_id, daemon_script_path=fast_worker_script)
            return ModuleStatusWidget(daemon, module_name="Isolated Test Plugin")

        window.module_manager.load_module_ui.return_value = factory

        manifest = {
            "id": plugin_id,
            "display_name": "Isolated Test Plugin",
            "name": "Isolated Test Plugin",
            "icon": "🧩",
        }

        try:
            window.plugin_manager.open_module(manifest)
            qtbot.waitUntil(lambda: window.module_overlay is not None, timeout=5000)

            window.wizard_panel.cancel()

            assert window.wizard_panel.state == ModuleStatusWidget.STATE_CLOSED
            assert window.module_overlay is None
            mock_err.assert_not_called()
        finally:
            PluginUIDaemon.stop_instance(plugin_id)

    @patch("karcytics.ui.dialogs.error_report.ErrorReportDialog.exec")
    def test_open_isolated_module_reveals_overlay_instantly_without_waiting_for_ready(
        self, mock_err, window, qtbot, slow_worker_script
    ):
        """Regression test for the "windows are getting split" bug: an
        isolated module's own window has its own loading state, so the Hub
        must reveal `ModuleStatusWidget`'s blocking overlay immediately
        instead of holding a loader up behind panel_ready/data_ready.
        `slow_worker_script` sleeps 2 s before its daemon ever reports ready
        — the overlay must appear well before that, while the widget is
        still Spawning, and the Hub's own analysis page must never activate.
        """
        plugin_id = "isolated_test_plugin_slow"

        def factory():
            daemon = PluginUIDaemon.get_instance(plugin_id, daemon_script_path=slow_worker_script)
            return ModuleStatusWidget(daemon, module_name="Isolated Test Plugin")

        window.module_manager.load_module_ui.return_value = factory

        manifest = {
            "id": plugin_id,
            "display_name": "Isolated Test Plugin",
            "name": "Isolated Test Plugin",
            "icon": "🧩",
        }

        try:
            window.plugin_manager.open_module(manifest)

            qtbot.waitUntil(lambda: window.module_overlay is not None, timeout=5000)
            assert isinstance(window.wizard_panel, ModuleStatusWidget)
            # The overlay appeared immediately — the daemon can't possibly
            # be Running yet, `slow_worker_script` hasn't slept 2 s.
            assert window.wizard_panel.state == ModuleStatusWidget.STATE_SPAWNING
            # No Hub-side warp/hyperdrive cinematic ever played for this
            # module, and the Hub never left the page it was already on.
            assert window.loader_widget is None
            assert window.root_stack.currentIndex() == _PAGE_HOME

            qtbot.waitUntil(
                lambda: window.wizard_panel.state == ModuleStatusWidget.STATE_RUNNING, timeout=10000
            )
            mock_err.assert_not_called()
        finally:
            PluginUIDaemon.stop_instance(plugin_id)
