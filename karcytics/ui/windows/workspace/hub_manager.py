"""Hub Manager for WorkspaceWindow."""

import logging
from collections.abc import Callable

from PyQt6.QtWidgets import QMainWindow

from karcytics.shared.ui.alerts import ask_question, show_error

logger = logging.getLogger(__name__)

StoreCallback = Callable[[QMainWindow], None]


class HubManager:
    def __init__(self, main_window: QMainWindow) -> None:
        self.main_window = main_window

    def show_home(self) -> None:
        mw = self.main_window
        logger.info("HubManager: Returning to home screen. Closing any active modules.")
        if mw.wizard_panel and hasattr(mw.wizard_panel, "reset_to_setup"):
            mw.wizard_panel.reset_to_setup()

        self.refresh_hub_workflows()

        mw.current_module_id = None

        # We assume `_transition_to_page` is kept on main_window for layout management
        mw._transition_to_page(0)  # _PAGE_HOME = 0

        mw.status_bar.showMessage("Welcome to Karcytics — choose a module to begin")
        mw.zoom_label.setText("")

    def open_academy_from_home(self):
        """Called via the top-bar Academy button while on the home screen.
        Opens the Global Academy Hub, showing all available courses.
        """
        self.open_academy_for_module(None)

    def open_academy_for_module(self, module_id: str | None) -> None:
        """Opens the Academy course catalogue for the given module (or Global Hub if None).
        If a specific module is provided and has exactly one course that hasn't
        been started yet, starts it directly (fast path). Otherwise opens the full catalogue.
        """
        from karcytics.core.tutorial_manager import global_tutorial_manager
        from karcytics.ui.dialogs.academy_window import AcademyWindow

        mw = self.main_window

        # Fast path: single unstarted course → start immediately without the catalogue
        if module_id is not None:
            courses = global_tutorial_manager.get_courses_for_module(module_id)
            if len(courses) == 1:
                c = courses[0]
                progress = global_tutorial_manager.get_progress(c.id)
                if progress == 0.0:
                    global_tutorial_manager.start_course_confirmed(c.id)
                    mw.tutorial_overlay.setGeometry(mw.analysis_page.rect())
                    mw.tutorial_overlay.show()
                    mw.status_bar.showMessage(f"Started: {c.title}")
                    return

        # Default: open full catalogue
        dialog = AcademyWindow(global_tutorial_manager, module_id, mw)

        def _handle_core_course():
            if hasattr(mw, "root_stack") and mw.root_stack.currentIndex() != 0:
                mw.status_bar.showMessage(
                    "Please return to the Hub view to start the onboarding tour.", 5000
                )
                return
            self.show_home()
            global_tutorial_manager.start_core_intro()

        dialog.core_course_requested.connect(_handle_core_course)
        dialog.exec()

        if global_tutorial_manager.active_course:
            overlay = mw._active_overlay()
            if overlay:
                if overlay == getattr(mw, "home_tutorial_overlay", None):
                    overlay.setGeometry(mw.home_screen.rect())
                else:
                    overlay.setGeometry(mw.analysis_page.rect())
                overlay.show()
                overlay.raise_()
            mw.status_bar.showMessage(
                "Started Academy Course: " + global_tutorial_manager.active_course.title
            )

    def maybe_start_core_intro(self) -> None:
        """Start (or continue) the core onboarding tutorial."""
        from karcytics.core.preferences import core_preferences
        from karcytics.core.tutorial_manager import global_tutorial_manager

        mw = self.main_window

        # Case 0: a course is already active in memory (e.g. this very course,
        # mid-run) — starting it again would reset it back to step one, since
        # start_course_confirmed() always jumps to steps[0]. Don't clobber it.
        if global_tutorial_manager.active_course is not None:
            return

        # Case 1: already dismissed once (they can restart from help menu)
        if core_preferences.get("core_intro_dismissed_once", False):
            return

        # Case 2: course already fully completed
        if global_tutorial_manager.get_progress("core_intro_v1") >= 1.0:
            return

        # Case 3: started but paused — resume!
        if global_tutorial_manager.get_progress("core_intro_v1") > 0.0:
            started = global_tutorial_manager.start_core_intro()
            if started:
                mw.home_tutorial_overlay.setGeometry(mw.home_screen.rect())
                mw.home_tutorial_overlay.show()
                mw.home_tutorial_overlay.raise_()
            return

        # Case 4: first ever launch — start fresh
        started = global_tutorial_manager.start_core_intro()
        if started:
            mw.home_tutorial_overlay.setGeometry(mw.home_screen.rect())
            mw.home_tutorial_overlay.show()
            mw.home_tutorial_overlay.raise_()

    def restart_core_intro(self) -> None:
        """Re-launches the onboarding tour without losing completion status."""
        from karcytics.core.preferences import core_preferences
        from karcytics.core.tutorial_manager import global_tutorial_manager

        mw = self.main_window
        if hasattr(mw, "root_stack") and mw.root_stack.currentIndex() != 0:
            mw.status_bar.showMessage(
                "Please return to the Hub view to restart the onboarding tour.", 5000
            )
            return

        core_preferences.set("core_intro_dismissed_once", False)
        global_tutorial_manager.active_course = None
        global_tutorial_manager.current_step = None

        self.show_home()

        # Start directly, bypassing the "already completed" guard in maybe_start_core_intro
        started = global_tutorial_manager.start_core_intro()
        if started:
            mw.home_tutorial_overlay.setGeometry(mw.home_screen.rect())
            mw.home_tutorial_overlay.show()
            mw.home_tutorial_overlay.raise_()

    def open_store(self) -> None:
        """Open the plugin store from the Hub."""
        if self.main_window.open_store_callback:
            from karcytics.core.event_bus import KarcyticsEvent, event_bus

            event_bus.emit(KarcyticsEvent.STORE_OPENED)
            self.main_window.open_store_callback(self.main_window)
            event_bus.emit(KarcyticsEvent.STORE_CLOSED)
        return

    def on_trust_requested(self, module_id: str) -> bool:
        """
        Trust locally modified plugin files after user confirmation.

        Parameters:
            module_id (str): Identifier of the module whose local changes should be trusted.

        Returns:
            bool: `True` if the changes were trusted successfully, `False` if the user cancels or trust fails.
        """
        mw = self.main_window
        if ask_question(
            mw,
            "Security: Trust Local Changes?",
            f"The module '{module_id}' has been modified locally.\n\n"
            "Do you trust these changes and want to lock them on this machine?\n\n"
            "By clicking 'Yes', Karcytics will snapshot these files and trust them from now on.",
        ):
            if mw.module_manager.trust_module(module_id):
                mw.status_bar.showMessage(
                    f"Permanently trusted local changes for {module_id}.", 5000
                )
                # Refresh dashboard
                mw.home_screen.populate_modules(mw.module_manager.get_available_modules())
                return True
            show_error(mw, "Error", "Failed to trust module. Could not calculate hashes.")
        return False

    def refresh_hub_workflows(self) -> None:
        """Populate the dashboard with workflows found in the project's workflows folder.

        Workflows are ordered by timestamp with the newest entries first.
        """
        mw = self.main_window
        workflows = []
        if mw.project_manager and mw.project_manager.project_dir:
            wf_dir = mw.project_manager.project_dir / "workflows"
            if wf_dir.exists():
                from karcytics.core.utils import AtomicJsonFile

                for wf_file in wf_dir.rglob("*.json"):
                    data = AtomicJsonFile.load(wf_file)
                    if data:
                        metadata = data.get("metadata", {})
                        workflows.append(
                            {
                                "filename": wf_file.name,
                                "module_id": metadata.get("module", "western_blot"),
                                "name": metadata.get("name", wf_file.stem),
                                "timestamp": metadata.get("timestamp", "Unknown Date"),
                                "description": metadata.get("description", ""),
                                "tags": metadata.get("tags", []),
                            }
                        )

        # Sort newest first
        workflows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        mw.home_screen.populate_workflows(workflows)

    def load_workflow_from_dashboard(self, module_id: str, filename: str) -> None:
        """Handler for when a user clicks a workflow card in the Hub."""
        mw = self.main_window
        try:
            # 1. Load the payload
            payload = mw.project_manager.load_workflow_payload(filename)

            # 2. Find the manifest
            manifests = mw.module_manager.get_available_modules()
            manifest = next((m for m in manifests if m["id"] == module_id), None)

            if not manifest:
                show_error(mw, "Load Error", f"Module {module_id} is not currently installed.")
                return

            # 3. Store the pending payload for when the module is fully loaded
            mw._pending_workflow_payload = payload
            mw._pending_workflow_filename = filename

            from karcytics.core.utils import AtomicJsonFile

            wf_file = mw.project_manager.project_dir / "workflows" / filename
            data = AtomicJsonFile.load(wf_file, default={})
            mw._pending_workflow_metadata = data.get("metadata", {})

            # 4. Open the module asynchronously
            if hasattr(mw, "plugin_manager"):
                mw.plugin_manager.open_module(manifest)
            else:
                mw._open_module(manifest)

        except Exception as e:
            logger.exception("Failed to load workflow")
            show_error(mw, "Load Error", f"Could not load workflow:\n{str(e)}")

    def handle_workflow_settings(self, module_id: str, filename: str) -> None:
        mw = self.main_window
        from karcytics.ui.dialogs.workflow_properties import WorkflowPropertiesDialog

        dialog = WorkflowPropertiesDialog(mw.project_manager, module_id, filename, parent=mw)
        dialog.workflow_deleted.connect(self.refresh_hub_workflows)
        dialog.attachment_deleted.connect(self.refresh_hub_workflows)
        dialog.workflow_updated.connect(self.refresh_hub_workflows)
        dialog.exec()
