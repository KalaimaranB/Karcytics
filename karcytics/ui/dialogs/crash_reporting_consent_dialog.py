"""First-run crash reporting consent dialog.

Shown exactly once to new users (when ``is_consent_given()`` returns None
and a DSN is configured). Presents a plain-language summary of what is sent
and two choices: Enable or No Thanks. Either answer is persisted so the
dialog never re-appears.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from karcytics.core import crash_reporting
from karcytics.ui.theme import Colors, Fonts, theme_manager


class CrashReportingConsentDialog(QDialog):
    """Yes/No opt-in dialog for crash reporting — shown once on first launch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help Improve Karcytics")
        self.setMinimumSize(520, 380)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._setup_ui()
        self._apply_styles()

        theme_manager.theme_changed.connect(self._apply_styles)

    def _setup_ui(self):  # noqa: PLR0915
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(18)

        # Icon + title
        self.title_label = QLabel("🛡️  Help Us Fix Bugs Faster")
        self.title_label.setFont(Fonts.H2)
        layout.addWidget(self.title_label)

        # Body text
        body = (
            "Would you like to automatically send crash reports when Karcytics "
            "encounters an error? This helps us find and fix bugs quickly.\n\n"
            "Each report contains:\n"
            "  • The error message and stack trace\n"
            "  • Last 50 log lines from your session\n"
            "  • OS name and app version\n"
            "  • Plugin ID and version (if a plugin caused the error)\n\n"
            "What is never sent:\n"
            "  • File paths — replaced with <redacted-file> before leaving\n"
            "    your machine (e.g. /home/user/Sample.fcs → <redacted-file>)\n"
            "  • Your home directory path — replaced with <home>\n"
            "  • Raw variable values from stack frames\n"
            "  • Any file contents or biological data\n\n"
            "You can change this at any time in:\n"
            "  Settings → Diagnostics & Privacy"
        )
        self.body_label = QLabel(body)
        self.body_label.setFont(Fonts.BODY)
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.decline_btn = QPushButton("No Thanks")
        self.decline_btn.setMinimumWidth(110)
        self.decline_btn.clicked.connect(self._on_decline)

        self.enable_btn = QPushButton("Enable Crash Reporting")
        self.enable_btn.setMinimumWidth(180)
        self.enable_btn.clicked.connect(self._on_enable)

        btn_layout.addWidget(self.decline_btn)
        btn_layout.addWidget(self.enable_btn)
        layout.addLayout(btn_layout)

    def _on_enable(self):
        crash_reporting.set_consent(True)
        self.accept()

    def _on_decline(self):
        crash_reporting.set_consent(False)
        self.reject()

    def _apply_styles(self):
        theme_manager.apply_style(self.title_label, f"color: {Colors.FG_PRIMARY};")
        theme_manager.apply_style(self.body_label, f"color: {Colors.FG_SECONDARY};")
        theme_manager.apply_style(
            self.enable_btn,
            f"""
            QPushButton {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            """,
        )
        theme_manager.apply_style(
            self,
            f"""
            QDialog {{
                background-color: {Colors.BG_DARKEST};
                border: 1px solid {Colors.BORDER};
            }}
            QLabel {{
                color: {Colors.FG_PRIMARY};
            }}
            QPushButton {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 10px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_MEDIUM};
                border: 1px solid {Colors.ACCENT_PRIMARY};
            }}
            """,
        )
