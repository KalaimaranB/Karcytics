"""Theme Manager for WorkspaceWindow."""

from pathlib import Path
from typing import TYPE_CHECKING, Final

from PySide6.QtWidgets import QWidget

from karcytics.ui.theme import Colors, theme_manager

if TYPE_CHECKING:
    from karcytics.ui.windows.workspace_window import WorkspaceWindow

_RESTYLE_INTERVAL: Final[int] = 40
_MENU_PADDING_V: Final[str] = "4px"
_MENU_PADDING_H: Final[str] = "20px"


class ThemeManager:
    def __init__(self, main_window: "WorkspaceWindow") -> None:
        self.main_window = main_window
        self._switching_theme = False

    def apply_supplemental_qss(self) -> None:
        checked_path, unchecked_path = self._write_checkbox_svgs()

        extra = (
            f"QCheckBox {{ spacing: 8px; color: {Colors.FG_PRIMARY}; }}"
            # ── Standalone QCheckBox indicators ──────────────────────────────
            f"QCheckBox::indicator {{ width: 16px; height: 16px; }}"
            f"QCheckBox::indicator:unchecked {{ image: url({unchecked_path}); }}"
            f"QCheckBox::indicator:checked   {{ image: url({checked_path}); }}"
            # ── QListWidget item checkboxes (ItemIsUserCheckable) ─────────────
            f"QListView::indicator {{ width: 16px; height: 16px; }}"
            f"QListView::indicator:unchecked {{ image: url({unchecked_path}); }}"
            f"QListView::indicator:checked   {{ image: url({checked_path}); }}"
            f"QGroupBox {{ color: {Colors.FG_PRIMARY}; font-weight: bold; "
            f" border: 1px solid {Colors.BORDER}; border-radius: 6px; margin-top: 12px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 5px; }}"
            f"QRadioButton {{ color: {Colors.FG_PRIMARY}; }}"
            f"QLabel {{ color: {Colors.FG_PRIMARY}; }}"
            f"QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{"
            f"  background-color: {Colors.BG_DARKEST};"
            f"  color: {Colors.FG_PRIMARY};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"}}"
            f"QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{"
            f"  border: 1px solid {Colors.BORDER_FOCUS};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border-left: 1px solid {Colors.BORDER};"
            f"  width: 20px;"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  background: {Colors.BG_DARK}; width: 12px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {Colors.BORDER}; min-height: 20px; border-radius: 6px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background: {Colors.BORDER_FOCUS};"
            f"}}"
            f"QListWidget {{"
            f"  background-color: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px;"
            f"}}"
            f"QListWidget::item:selected {{\n"
            f"  background-color: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST};\n"
            f"}}\n"
            f"QMenu {{\n"
            f"  background-color: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY};\n"
            f"  border: 1px solid {Colors.BORDER}; border-radius: 4px;\n"
            f"}}\n"
            f"QMenu::item {{\n"
            f"  padding: {_MENU_PADDING_V} {_MENU_PADDING_H} {_MENU_PADDING_V} {_MENU_PADDING_H};\n"
            f"}}\n"
            f"QMenu::item:selected {{\n"
            f"  background-color: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST};\n"
            f"}}\n"
        )
        theme_manager.apply_style(self.main_window, self.main_window.styleSheet() + "\n" + extra)

    def _write_checkbox_svgs(self) -> tuple[str, str]:
        """Write theme-aware SVG checkbox images to a temp dir and return their paths."""
        import os
        import tempfile

        # Checked — accent-filled box with white checkmark polyline
        checked_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            f'<rect width="16" height="16" rx="3" fill="{Colors.ACCENT_PRIMARY}"/>'
            '<polyline points="3,8.5 6.5,12 13,4" fill="none" stroke="white"'
            ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg>"
        )
        # Unchecked — neutral box, clearly bordered
        unchecked_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            f'<rect x="1" y="1" width="14" height="14" rx="3"'
            f' fill="{Colors.BG_MEDIUM}" stroke="{Colors.FG_SECONDARY}" stroke-width="1.5"/>'
            "</svg>"
        )

        tmp = tempfile.gettempdir()
        checked_path = os.path.join(tmp, "karcytics_cb_checked.svg")
        unchecked_path = os.path.join(tmp, "karcytics_cb_unchecked.svg")

        # Convert backslashes for Qt stylesheet URLs (Windows)
        checked_path = checked_path.replace("\\", "/")
        unchecked_path = unchecked_path.replace("\\", "/")

        with open(checked_path, "w", encoding="utf-8") as f:
            f.write(checked_svg)
        with open(unchecked_path, "w", encoding="utf-8") as f:
            f.write(unchecked_svg)

        return checked_path, unchecked_path

    def switch_theme(self, theme_path: Path) -> None:
        """Switches the active theme.

        Loading a theme rebuilds the entire workspace UI synchronously, which
        can take a noticeable moment. A single deferred callback isn't enough
        here: macOS flags the app as unresponsive (spinning-wheel cursor)
        whenever the main run loop goes quiet for a stretch, regardless of
        what was painted right before the block started. So we show the
        overlay, force it onto screen immediately, and then pump the event
        loop at checkpoints throughout the rebuild (see `_pump_events`) to
        keep both the app responsive and the overlay animating.
        """
        # Pumping events mid-rebuild (below) lets a second theme click
        # re-enter this method before the first switch finishes; ignore it
        # rather than let two rebuilds interleave and corrupt the UI.
        if self._switching_theme:
            return
        self._switching_theme = True

        overlay = getattr(self.main_window, "theme_loading_overlay", None)
        try:
            if overlay is not None:
                overlay.set_text("Changing theme…")
                overlay.start()
                overlay.repaint()
                self._pump_events()

            self._apply_theme(theme_path)
        finally:
            if overlay is not None:
                overlay.stop()
            self._switching_theme = False

    def _apply_theme(self, theme_path: Path) -> None:
        if theme_manager.load_theme(theme_path):
            from karcytics.core.preferences import core_preferences

            core_preferences.set("theme", str(theme_path.absolute()))

    @staticmethod
    def _pump_events() -> None:
        """Processes pending Qt events so the UI stays responsive and the
        loading overlay's animation actually advances during long rebuilds."""
        from PySide6.QtCore import QEventLoop
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def on_theme_changed(self) -> None:
        """Full workspace UI rebuild on theme swap."""
        from karcytics.ui.theme import Strings

        mw = self.main_window

        # 0. Update Window Title
        project_name = mw.project_manager.data.get("project_name", "Untitled Project")
        mw.setWindowTitle(f"{Strings.APP_TITLE} — {project_name}")

        # Save where the user is currently looking!
        current_idx = mw.root_stack.currentIndex()

        # 1. Update Main Window Base
        theme_manager.apply_style(
            mw, f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};"
        )
        self.apply_supplemental_qss()
        self._pump_events()

        # 2. Update status bar and toolbar
        is_sw = "Galactic" in theme_manager.current_theme_name
        theme_manager.apply_style(
            mw.status_bar,
            f"background: {Colors.BG_DARK}; color: {Colors.FG_SECONDARY};"
            f" border-top: 1px solid {Colors.BORDER};",
        )
        if hasattr(mw, "analysis_toolbar"):
            mw.analysis_toolbar._apply_theme_styles()

        # 3. Update status message
        if is_sw:
            mw.status_bar.showMessage("SECTOR STATUS: READY | NAV-COMPUTER ONLINE")
        else:
            mw.status_bar.showMessage("Welcome to Karcytics — choose a module to begin")

        # 4. Rebuild the Hub
        if hasattr(mw, "home_screen"):
            mw.root_stack.removeWidget(mw.home_screen)
            mw.home_screen.deleteLater()

            # Remove dead python reference to avoid resizeEvent crashing
            if hasattr(mw, "home_tutorial_overlay"):
                del mw.home_tutorial_overlay

        self._pump_events()

        from karcytics.ui.dashboards.workspace_dashboard import WorkspaceDashboard as HomeScreen

        mw.home_screen = HomeScreen()

        # Recreate the tutorial overlay for the new home screen
        from karcytics_sdk.plugin.tutorial_overlay import TutorialOverlay

        from karcytics.core.tutorial_manager import global_tutorial_manager, hub_academy_event_bus

        mw.home_tutorial_overlay = TutorialOverlay(
            global_tutorial_manager, hub_academy_event_bus, mw.home_screen
        )
        mw.home_tutorial_overlay.hide()
        mw.home_tutorial_overlay.btn_next.clicked.connect(mw._on_tutorial_next)
        mw.home_tutorial_overlay.skip_requested.connect(mw._on_tutorial_skip)

        # Rewire signals
        mw.home_screen.module_selected.connect(
            mw.plugin_manager.open_module if hasattr(mw, "plugin_manager") else mw._open_module
        )
        mw.home_screen.return_to_hub_requested.connect(mw.return_to_hub)
        mw.home_screen.open_store_requested.connect(
            mw.hub_manager.open_store if hasattr(mw, "hub_manager") else mw._open_store
        )
        mw.home_screen.open_ai_requested.connect(
            mw.menu_manager.open_ai_chat if hasattr(mw, "menu_manager") else mw._open_ai_chat
        )
        mw.home_screen.workflow_selected.connect(
            mw.hub_manager.load_workflow_from_dashboard
            if hasattr(mw, "hub_manager")
            else mw._load_workflow_from_dashboard
        )
        mw.home_screen.workflow_settings_requested.connect(
            mw.hub_manager.handle_workflow_settings
            if hasattr(mw, "hub_manager")
            else mw._handle_workflow_settings
        )
        mw.home_screen.trust_module_requested.connect(
            mw.hub_manager.on_trust_requested
            if hasattr(mw, "hub_manager")
            else mw._on_trust_requested
        )
        mw.home_screen.open_academy_requested.connect(
            mw.hub_manager.open_academy_from_home
            if hasattr(mw, "hub_manager")
            else mw._open_academy_from_home
        )
        mw.home_screen.open_academy_for_module_requested.connect(
            mw.hub_manager.open_academy_for_module
            if hasattr(mw, "hub_manager")
            else mw._open_academy_for_module
        )

        # Insert back into stack at index 0 (Assuming _PAGE_HOME = 0)
        mw.root_stack.insertWidget(0, mw.home_screen)
        mw.home_screen.populate_modules(mw.module_manager.get_available_modules())
        if hasattr(mw, "hub_manager"):
            mw.hub_manager.refresh_hub_workflows()
        else:
            mw._refresh_hub_workflows()
        self._pump_events()

        # Update active module UI, if present
        if hasattr(mw, "wizard_panel") and mw.wizard_panel is not None:
            self.refresh_widget_theme(mw.wizard_panel)
            mw.wizard_panel.update()

        # 4.5 Refresh Analysis Page and Tech Subtitle
        if hasattr(mw, "analysis_page"):
            theme_manager.apply_style(mw.analysis_page, f"background: {Colors.BG_DARKEST};")

        # 5. Update Hologram Overlay
        if hasattr(mw, "hologram_overlay"):
            if Colors.SCANLINE_OPACITY > 0:
                mw.hologram_overlay.show()
                mw.hologram_overlay.setGeometry(mw.root_stack.geometry())
                mw.hologram_overlay.raise_()
            else:
                mw.hologram_overlay.hide()

        # Restore the view
        mw.root_stack.setCurrentIndex(current_idx)

        # 6. Re-raise the isolated-module blocking overlay, if one is up.
        # It's a floating child of root_stack, not one of its pages, so
        # step 4's home_screen rebuild above (removeWidget/insertWidget)
        # never touched it directly — but the freshly-inserted home_screen
        # sibling still ends up stacked above it in paint order (and
        # setCurrentIndex() above re-raises whichever page is current one
        # more time besides), burying an otherwise perfectly alive overlay
        # behind the rebuilt page. Must run *after* setCurrentIndex(), not
        # before it, or that call's own raise of the current page undoes
        # this. Mirrors the hologram_overlay re-raise above for the same
        # reason.
        module_overlay = getattr(mw, "module_overlay", None)
        if module_overlay is not None:
            module_overlay.setGeometry(mw.root_stack.rect())
            module_overlay.raise_()

    def refresh_widget_theme(self, widget: QWidget):
        """Recursively refreshes theme styles for a widget and its children."""
        if widget is None:
            return

        if hasattr(widget, "_apply_theme_styles"):
            widget._apply_theme_styles()
        elif hasattr(widget, "refresh_styles"):
            widget.refresh_styles()

        if widget.styleSheet():
            theme_manager.apply_style(widget, widget.styleSheet())

        for i, child in enumerate(widget.findChildren(QWidget)):
            if hasattr(child, "_apply_theme_styles"):
                child._apply_theme_styles()
            elif hasattr(child, "refresh_styles"):
                child.refresh_styles()

            if child.styleSheet():
                theme_manager.apply_style(child, child.styleSheet())
            child.update()

            # Restyling can walk hundreds of widgets on a busy module panel —
            # yield to the event loop periodically so the app stays responsive
            # and the loading overlay keeps animating instead of stalling.
            if i % _RESTYLE_INTERVAL == 0:
                self._pump_events()
