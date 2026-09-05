"""Premium Error Reporting Dialog for Karcytics."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from karcytics.core import crash_reporting
from karcytics.ui.theme import Colors, Fonts, theme_manager

# Maps (fatal, has_plugin_id) → (icon, title, subtitle_template)
# subtitle_template may contain {plugin_id} if has_plugin_id is True.
_ERROR_APPEARANCE: dict[tuple[bool, bool], tuple[str, str, str]] = {
    (True, False): (
        "💥",
        "Karcytics crashed.",
        "A fatal error occurred in the core system. The app may be unstable.",
    ),
    (True, True): ("💥", "Plugin crashed.", "Plugin {plugin_id} encountered a fatal error."),
    (False, True): ("⚠️", "Plugin error.", "Plugin {plugin_id} reported a non-fatal error."),
    (False, False): ("⚠️", "Something went wrong.", "The core system reported an unexpected error."),
}


class ErrorReportDialog(QDialog):
    """A sleek, theme-aware dialog for displaying system errors and tracebacks."""

    def __init__(self, error_data: dict, parent=None):
        super().__init__(parent)
        self.error_data = error_data
        self.setWindowTitle("System Alert — Karcytics Diagnostic")
        self.setMinimumSize(620, 460)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()
        self._apply_styles()

        from karcytics.ui.theme import theme_manager

        theme_manager.theme_changed.connect(self._apply_styles)

    def _setup_ui(self):
        fatal: bool = bool(self.error_data.get("fatal"))
        plugin_id: str | None = self.error_data.get("plugin_id")
        icon_str, title_str, subtitle_str = _ERROR_APPEARANCE[(fatal, plugin_id is not None)]
        if plugin_id:
            subtitle_str = subtitle_str.format(plugin_id=plugin_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        self.icon_label = QLabel(icon_str)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 32))

        title_v_layout = QVBoxLayout()
        self.title_label = QLabel(title_str)
        self.title_label.setFont(Fonts.H2)

        self.subtitle_label = QLabel(subtitle_str)
        self.subtitle_label.setFont(Fonts.CAPTION)

        title_v_layout.addWidget(self.title_label)
        title_v_layout.addWidget(self.subtitle_label)

        header_layout.addWidget(self.icon_label)
        header_layout.addLayout(title_v_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Message
        self.msg_label = QLabel(self.error_data.get("message", "An unexpected error occurred."))
        self.msg_label.setFont(Fonts.BODY)
        self.msg_label.setWordWrap(True)
        layout.addWidget(self.msg_label)

        # Data Preview
        self.details_label = QLabel("The following diagnostic data will be sent:")
        self.details_label.setFont(Fonts.CAPTION)
        layout.addWidget(self.details_label)

        self.details_area = QTextEdit()
        self.details_area.setReadOnly(True)

        preview_lines = []
        if plugin_id:
            preview_lines.append(f"Plugin ID: {plugin_id}")
        preview_lines.append(f"Level: {'fatal' if fatal else 'error'}")
        preview_lines.append(f"Message: {self.error_data.get('message', '')}")

        import platform

        from karcytics.core.config import AppConfig

        preview_lines.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
        preview_lines.append(f"App Version: {AppConfig.CORE_VERSION}")

        if self.error_data.get("traceback"):
            preview_lines.append(f"\nTraceback:\n{self.error_data.get('traceback')}")

        try:
            log_path = AppConfig.APP_DATA_DIR / "logs" / "core.log"
            if log_path.exists():
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                recent_logs = lines[-50:]
                preview_lines.append("\nRecent Core Logs:")
                preview_lines.extend([line.rstrip() for line in recent_logs])
        except Exception:
            pass

        self.details_area.setPlainText("\n".join(preview_lines))
        mono_font = QFont(Fonts.FAMILY_MONO, 9)
        self.details_area.setFont(mono_font)
        self.details_area.setMinimumHeight(120)
        layout.addWidget(self.details_area)

        # User Feedback
        self.comments_label = QLabel("What happened to cause the bug? (Optional)")
        self.comments_label.setFont(Fonts.BODY)
        layout.addWidget(self.comments_label)

        self.comments_area = QTextEdit()
        self.comments_area.setPlaceholderText("Please provide any additional context...")
        self.comments_area.setMinimumHeight(60)
        self.comments_area.setMaximumHeight(100)
        layout.addWidget(self.comments_area)

        # Actions
        btn_layout = QHBoxLayout()

        self.send_btn = QPushButton("Send to Sentry")
        self.send_btn.clicked.connect(self._send_report)

        self.close_btn = QPushButton("Dismiss")
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.send_btn)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        is_fatal = bool(self.error_data.get("fatal"))
        title_color = Colors.ACCENT_DANGER if is_fatal else Colors.FG_PRIMARY
        theme_manager.apply_style(self.title_label, f"color: {title_color};")
        theme_manager.apply_style(self.subtitle_label, f"color: {Colors.FG_SECONDARY};")

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
            QTextEdit {{
                background-color: {Colors.BG_DARK};
                color: {Colors.ACCENT_DANGER};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 10px;
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

    def _send_report(self):
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending...")

        user_comments = self.comments_area.toPlainText().strip()
        success = crash_reporting.send_user_report(self.error_data, user_comments)

        if success:
            self.send_btn.setText("Sent!")
            theme_manager.apply_style(
                self.send_btn,
                f"background-color: {Colors.ACCENT_SUCCESS}; color: white; border: none;",
            )
        else:
            self.send_btn.setText("Send Failed")
            self.send_btn.setEnabled(True)
