import platform

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karcytics.core.about_info import KARCYTICS_ABOUT
from karcytics.core.config import AppConfig
from karcytics.ui.theme import Colors, theme_manager


class AboutKarcyticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Karcytics")
        self.setFixedSize(550, 450)

        theme_manager.apply_style(
            self,
            f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};",
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        icon_lbl = QLabel("🧬")
        icon_lbl.setFixedSize(64, 64)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            icon_lbl,
            f"background: {Colors.BG_DARKER}; font-size: 36px; border-radius: 12px; border: 1px solid {Colors.BORDER};",
        )
        header_layout.addWidget(icon_lbl)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(5)

        name_lbl = QLabel(KARCYTICS_ABOUT["name"])
        theme_manager.apply_style(
            name_lbl,
            f"color: {Colors.FG_PRIMARY}; font-size: 24px; font-weight: bold;",
        )

        version_lbl = QLabel(f"Version {KARCYTICS_ABOUT['version']}")
        theme_manager.apply_style(
            version_lbl,
            f"color: {Colors.FG_SECONDARY}; font-size: 14px;",
        )

        title_layout.addWidget(name_lbl)
        title_layout.addWidget(version_lbl)
        title_layout.addStretch()

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Description
        desc_lbl = QLabel(
            f"<p><b>{KARCYTICS_ABOUT['tagline']}</b></p>"
            f"<p>{KARCYTICS_ABOUT['description']}</p>"
            f"<p>{KARCYTICS_ABOUT['copyright']}</p>"
        )
        desc_lbl.setWordWrap(True)
        theme_manager.apply_style(
            desc_lbl,
            f"color: {Colors.FG_PRIMARY}; font-size: 13px; line-height: 1.5;",
        )
        layout.addWidget(desc_lbl)

        # Diagnostics Frame
        diag_frame = QWidget()
        theme_manager.apply_style(
            diag_frame,
            f"background: {Colors.BG_DARKER}; border-radius: 8px; border: 1px solid {Colors.BORDER};",
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(15, 15, 15, 15)

        import PySide6
        import PySide6.QtCore as QtCore

        self.sys_info = (
            f"Karcytics: v{AppConfig.CORE_VERSION}\n"
            f"Python: {platform.python_version()}\n"
            f"PySide6: {PySide6.__version__} (Qt {QtCore.qVersion()})\n"
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})"
        )

        sys_lbl = QLabel(self.sys_info.replace("\n", "<br>"))
        sys_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        theme_manager.apply_style(
            sys_lbl,
            f"color: {Colors.FG_SECONDARY}; font-size: 11px; font-family: monospace;",
        )
        diag_layout.addWidget(sys_lbl)

        copy_btn = QPushButton("📋 Copy System Info")
        theme_manager.apply_style(
            copy_btn,
            f"background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 4px 8px;",
        )
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_sys_info)
        diag_layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(diag_frame)

        layout.addStretch()

        # Links Row
        links_layout = QHBoxLayout()

        repo_btn = QPushButton("GitHub Repository")
        wiki_btn = QPushButton("Help Center")

        for btn in (repo_btn, wiki_btn):
            theme_manager.apply_style(
                btn,
                f"color: {Colors.ACCENT_PRIMARY}; border: none; background: transparent;",
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        repo_btn.clicked.connect(lambda: self._open_url("https://github.com/KalaimaranB/Karcytics"))
        wiki_btn.clicked.connect(
            lambda: self._open_url("https://github.com/KalaimaranB/Karcytics/wiki")
        )

        links_layout.addWidget(repo_btn)
        links_layout.addWidget(wiki_btn)
        links_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        links_layout.addWidget(close_btn)

        layout.addLayout(links_layout)

    def _copy_sys_info(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.sys_info)

    def _open_url(self, url: str):
        import webbrowser

        webbrowser.open(url)
