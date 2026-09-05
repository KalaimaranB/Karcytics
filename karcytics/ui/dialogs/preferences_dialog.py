"""Unified Preferences Dialog."""

import typing

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karcytics.ui.dialogs.diagnostics_settings_widget import DiagnosticsSettingsWidget
from karcytics.ui.theme import Colors, Fonts, theme_manager


class ThemeSettingsWidget(QWidget):
    """Widget for selecting the application theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("theme_settings_widget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel("Appearance & Themes")
        title_label.setFont(Fonts.H2)
        theme_manager.apply_style(title_label, f"color: {Colors.FG_PRIMARY};")
        layout.addWidget(title_label)

        desc_label = QLabel("Select your preferred theme for the workspace.")
        desc_label.setObjectName("secondaryText")
        desc_label.setFont(Fonts.CAPTION)
        theme_manager.apply_style(desc_label, f"color: {Colors.FG_SECONDARY};")
        layout.addWidget(desc_label)

        self.button_group = QButtonGroup(self)

        # Discover themes dynamically from theme manager
        categorized_themes = theme_manager.get_categorized_themes()

        for category, themes in categorized_themes.items():
            cat_label = QLabel(category)
            cat_label.setFont(Fonts.H3 if hasattr(Fonts, "H3") else Fonts.H2)
            theme_manager.apply_style(cat_label, f"color: {Colors.FG_PRIMARY}; margin-top: 12px;")
            layout.addWidget(cat_label)

            for name, path in themes:
                radio = QRadioButton(name)
                radio.setFont(Fonts.BODY)
                theme_manager.apply_style(radio, f"color: {Colors.FG_PRIMARY};")
                radio.toggled.connect(lambda checked, p=path: self._on_theme_toggled(checked, p))

                # Check if it's the current theme
                if theme_manager.current_theme_name == name:
                    radio.setChecked(True)

                self.button_group.addButton(radio)
                layout.addWidget(radio)

        layout.addStretch()
        self._apply_styles()
        theme_manager.theme_changed.connect(self._apply_styles)
        self._apply_styles()
        theme_manager.theme_changed.connect(self._apply_styles)

    def _apply_styles(self):
        from PyQt6.QtWidgets import QLabel, QRadioButton

        for label in self.findChildren(QLabel):
            if label.objectName() == "secondaryText":
                theme_manager.apply_style(label, f"color: {Colors.FG_SECONDARY};")
            else:
                theme_manager.apply_style(label, f"color: {Colors.FG_PRIMARY};")

        for radio in self.findChildren(QRadioButton):
            theme_manager.apply_style(radio, f"color: {Colors.FG_PRIMARY};")

    def _on_theme_toggled(self, checked: bool, path: str):

        if checked:
            from pathlib import Path

            from karcytics.core.preferences import core_preferences

            theme_manager.load_theme(Path(path))
            core_preferences.set("theme", str(path))


class AboutSettingsWidget(QWidget):
    """Widget displaying combined About Karcytics and About Developer information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        from karcytics.core.about_info import DEVELOPER_ABOUT, KARCYTICS_ABOUT

        # Karcytics About
        app_title = QLabel(KARCYTICS_ABOUT["name"])
        app_title.setFont(Fonts.H2)
        layout.addWidget(app_title)

        app_desc = QLabel(
            f"<p><b>{KARCYTICS_ABOUT['tagline']}</b></p><p>{KARCYTICS_ABOUT['description']}</p>"
        )
        app_desc.setWordWrap(True)
        app_desc.setFont(Fonts.BODY)
        layout.addWidget(app_desc)

        layout.addSpacing(16)

        # Developer About
        dev_title = QLabel(f"About the Developer: {DEVELOPER_ABOUT['name']}")
        dev_title.setFont(Fonts.H3 if hasattr(Fonts, "H3") else Fonts.H2)
        layout.addWidget(dev_title)

        bio_text = "".join(f"<p>{p}</p>" for p in DEVELOPER_ABOUT["bio"].split("\n\n"))
        dev_desc = QLabel(bio_text)
        dev_desc.setWordWrap(True)
        dev_desc.setFont(Fonts.BODY)
        layout.addWidget(dev_desc)

        layout.addStretch()

        self._apply_styles()
        theme_manager.theme_changed.connect(self._apply_styles)

    def _apply_styles(self):
        from PyQt6.QtWidgets import QLabel

        for label in self.findChildren(QLabel):
            theme_manager.apply_style(label, f"color: {Colors.FG_PRIMARY};")


class AdvancedSettingsWidget(QWidget):
    """Widget for advanced data management and developer tools."""

    def __init__(self, parent=None, hub_manager=None, workspace_window=None):
        super().__init__(parent)
        self.hub_manager = hub_manager
        self.workspace_window = workspace_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Developer Section
        dev_label = QLabel("Developer Tools")
        dev_label.setFont(Fonts.H2)
        theme_manager.apply_style(dev_label, f"color: {Colors.FG_PRIMARY};")
        layout.addWidget(dev_label)

        logs_btn = QPushButton("📜 View Logs")
        theme_manager.apply_style(
            logs_btn, f"background-color: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
        )
        logs_btn.clicked.connect(self._view_logs)
        layout.addWidget(logs_btn)

        layout.addSpacing(24)

        # Data Section
        data_label = QLabel("Data Management")
        data_label.setFont(Fonts.H2)
        theme_manager.apply_style(data_label, f"color: {Colors.FG_PRIMARY};")
        layout.addWidget(data_label)

        clear_btn = QPushButton("🧹 Clear App Data...")
        clear_btn.setObjectName("dangerBtn")
        theme_manager.apply_style(
            clear_btn,
            f"""
            QPushButton {{
                background-color: {Colors.BG_DARK};
                color: #ff4444;
                border: 1px solid #ff4444;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ff4444;
                color: #ffffff;
            }}
            """,
        )
        clear_btn.clicked.connect(self._clear_data)
        layout.addWidget(clear_btn)

        uninstall_btn = QPushButton("🗑️ Uninstall Karcytics...")
        uninstall_btn.setObjectName("dangerBtn")
        theme_manager.apply_style(
            uninstall_btn,
            f"""
            QPushButton {{
                background-color: {Colors.BG_DARK};
                color: #ff4444;
                border: 1px solid #ff4444;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ff4444;
                color: #ffffff;
            }}
            """,
        )
        uninstall_btn.clicked.connect(self._uninstall)
        layout.addWidget(uninstall_btn)

        layout.addStretch()
        self._apply_styles()
        theme_manager.theme_changed.connect(self._apply_styles)

    def _apply_styles(self):
        from PyQt6.QtWidgets import QLabel, QPushButton

        for label in self.findChildren(QLabel):
            theme_manager.apply_style(label, f"color: {Colors.FG_PRIMARY};")

        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "dangerBtn":
                theme_manager.apply_style(
                    btn,
                    f"""
                    QPushButton {{
                        background-color: {Colors.BG_DARK};
                        color: #ff4444;
                        border: 1px solid #ff4444;
                        padding: 8px 16px;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: #ff4444;
                        color: #ffffff;
                    }}
                    """,
                )
            else:
                theme_manager.apply_style(
                    btn, f"background-color: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
                )

    def _view_logs(self):

        from karcytics.ui.dialogs.log_viewer import LogViewerDialog

        dialog = LogViewerDialog(self)
        dialog.exec()

    def _clear_data(self):
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Clear App Data",
            "Are you sure you want to completely clear all Karcytics application data?\n\nThis will remove all your projects and settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.hub_manager and hasattr(self.hub_manager, "_clear_app_data"):
                self.hub_manager._clear_app_data()
            elif hasattr(self.workspace_window, "_clear_app_data"):
                self.workspace_window._clear_app_data()

    def _uninstall(self):
        import shutil
        import sys
        from pathlib import Path

        from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

        reply = QMessageBox.question(
            self,
            "Uninstall Karcytics",
            "Are you sure you want to uninstall Karcytics?\n\nThis will permanently delete your ~/.karcytics directory, which includes all your projects, settings, and plugins.\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            text, ok = QInputDialog.getText(
                self,
                "Confirm Uninstall",
                "Please type 'UNINSTALL' to confirm deletion of all data:",
                QLineEdit.EchoMode.Normal,
                "",
            )

            if ok and text == "UNINSTALL":
                data_dir = Path.home() / ".karcytics"
                try:
                    if data_dir.exists():
                        shutil.rmtree(data_dir)

                    QMessageBox.information(
                        self,
                        "Uninstallation Complete",
                        "Karcytics application data has been successfully removed.\n\nThe application will now exit. You can delete the Karcytics application bundle or folder to finish uninstalling.",
                        QMessageBox.StandardButton.Ok,
                    )
                    QApplication.quit()
                    sys.exit(0)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Uninstall Failed",
                        f"Failed to remove Karcytics data: {e}",
                        QMessageBox.StandardButton.Ok,
                    )
            elif ok:
                QMessageBox.warning(
                    self,
                    "Uninstall Aborted",
                    "Confirmation failed. You must type 'UNINSTALL' exactly.",
                    QMessageBox.StandardButton.Ok,
                )


class PreferencesDialog(QDialog):
    """Unified Preferences Dialog with left navigation and right stacked pages."""

    def __init__(self, parent=None, hub_manager=None, workspace_window=None):
        super().__init__(parent)
        self.setObjectName("preferences_dialog")
        self.setWindowTitle("Preferences")
        self.setMinimumSize(700, 500)

        self.hub_manager = hub_manager
        self.workspace_window = workspace_window

        self._setup_ui()
        self._apply_styles()
        theme_manager.theme_changed.connect(self._apply_styles)

    @typing.override
    def showEvent(self, event):
        from karcytics.core.event_bus import KarcyticsEvent, event_bus

        super().showEvent(event)
        event_bus.emit(KarcyticsEvent.PREFERENCES_OPENED)

    @typing.override
    def closeEvent(self, event):
        from karcytics.core.event_bus import KarcyticsEvent, event_bus

        super().closeEvent(event)
        event_bus.emit(KarcyticsEvent.PREFERENCES_CLOSED)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel: Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        self.nav_list.setFixedWidth(200)
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.nav_list)

        # Right panel: Stacked widget pages
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack)

        # Bottom right buttons (Close)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(16, 16, 16, 16)
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumWidth(80)
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        right_layout.addLayout(btn_layout)

        main_layout.addWidget(right_container, stretch=1)

        # Add pages
        self._add_page("About", AboutSettingsWidget(self))
        self._add_page("Appearance", ThemeSettingsWidget(self))
        self._add_page("Privacy & Diagnostics", DiagnosticsSettingsWidget(self))
        self._add_page(
            "Advanced", AdvancedSettingsWidget(self, self.hub_manager, self.workspace_window)
        )

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget):
        self.nav_list.addItem(title)
        self.stack.addWidget(widget)

    def _apply_styles(self):
        theme_manager.apply_style(
            self,
            f"""
            QDialog {{
                background-color: {Colors.BG_DARKEST};
                border: 1px solid {Colors.BORDER};
            }}
            QListWidget {{
                background-color: {Colors.BG_DARK};
                border: none;
                border-right: 1px solid {Colors.BORDER};
                outline: none;
                padding-top: 12px;
            }}
            QListWidget::item {{
                color: {Colors.FG_SECONDARY};
                padding: 10px 16px;
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.ACCENT_PRIMARY};
                border-left: 3px solid {Colors.ACCENT_PRIMARY};
            }}
            QLabel, QRadioButton {{
                padding-bottom: 4px;
                padding-top: 2px;
            }}
            QPushButton {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }}
            """,
        )
