"""Menu Manager for WorkspaceWindow."""

from PyQt6.QtGui import QAction

from karcytics.ui.theme import theme_manager


class MenuManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def setup_menu_bar(self) -> None:
        """
        Builds and attaches the application's menus using the SDK StandardMenuBuilder.
        """
        mw = self.main_window

        from karcytics_sdk.plugin.menu_builder import StandardMenuBuilder

        builder = StandardMenuBuilder(mw)

        # --- File Menu ---
        project_view_action = QAction("&Project View", mw)
        project_view_action.setShortcut("Ctrl+H")
        project_view_action.triggered.connect(
            mw.hub_manager.show_home if hasattr(mw, "hub_manager") else mw._show_home
        )

        close_project_action = QAction("Close Project && Return to Hub", mw)
        close_project_action.triggered.connect(mw.return_to_hub)

        exit_action = QAction("E&xit", mw)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(mw.close)

        # File actions order (we have a separator, so let's add them separately or just pass them)
        # StandardMenuBuilder add_file_menu just appends actions. Let's do it manually for the separator.
        file_menu = builder.add_file_menu([project_view_action, close_project_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # --- Edit Menu ---
        builder.add_edit_menu(
            undo_cb=mw.trigger_undo if hasattr(mw, "trigger_undo") else None,
            redo_cb=mw.trigger_redo if hasattr(mw, "trigger_redo") else None,
            pref_cb=self.open_preferences,
        )

        def _switch_theme(path: str) -> None:
            from karcytics.core.preferences import core_preferences

            theme_manager.load_theme(path)
            core_preferences.set("theme", str(path))

        # --- View Menu (Theme) ---
        builder.add_theme_menu(
            switch_theme_cb=_switch_theme,
            categorized_themes=theme_manager.get_categorized_themes(),
        )

        # --- Help Menu ---
        builder.add_help_menu(
            docs_cb=self.open_help_center,
            wiki_cb=self.open_wiki_online,
            about_cb=self.show_about,
            about_dev_cb=self.show_about_developer,
            onboarding_cb=mw.restart_core_intro if hasattr(mw, "restart_core_intro") else None,
        )

    def open_help_center(self):
        """Launch the localized help center."""
        from karcytics.ui.dialogs.help_dialog import HelpCenterDialog

        dialog = HelpCenterDialog(
            module_manager=self.main_window.module_manager, parent=self.main_window
        )
        dialog.exec()

    def open_wiki_online(self):
        """Open the online documentation in the browser."""
        import webbrowser

        webbrowser.open("https://kalaimaranb.github.io/Karcytics/")

    def view_logs(self):
        """View application logs."""
        from karcytics.ui.dialogs.log_viewer import LogViewerDialog

        dialog = LogViewerDialog(self.main_window)
        dialog.exec()

    def open_preferences(self):
        """Open the unified preferences dialog."""
        from karcytics.ui.dialogs.preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(
            parent=self.main_window,
            hub_manager=getattr(self.main_window, "hub_manager", None),
            workspace_window=self.main_window,
        )
        dialog.exec()

    def show_about(self) -> None:
        """Show the About Karcytics dialog."""
        from karcytics.ui.dialogs.about_karcytics import AboutKarcyticsDialog

        dialog = AboutKarcyticsDialog(self.main_window)
        dialog.exec()

    def show_about_developer(self) -> None:
        """Show the About Developer dialog."""
        from karcytics.ui.dialogs.about_developer import AboutDeveloperDialog

        dialog = AboutDeveloperDialog(self.main_window)
        dialog.exec()

    def open_ai_chat(self):
        """Opens the AI floating panel for contextual help."""
        from karcytics.ui.components.ai_panel import AIChatWindow

        # Make the AI window a child of main window but as a tool (floating, on top)
        if not hasattr(self.main_window, "ai_window") or self.main_window.ai_window is None:
            self.main_window.ai_window = AIChatWindow(self.main_window)

        if self.main_window.ai_window.isHidden():
            self.main_window.ai_window.show()
            self.main_window.ai_window.raise_()
            self.main_window.ai_window.activateWindow()
        else:
            self.main_window.ai_window.hide()
