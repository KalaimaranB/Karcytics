"""Premium Error Reporting Dialog for Karcytics."""

import json
import os

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

        # Details (Scrollable Traceback)
        self.details_area = QTextEdit()
        self.details_area.setReadOnly(True)
        self.details_area.setPlainText(self.error_data.get("traceback", "No traceback available."))
        mono_font = QFont(Fonts.FAMILY_MONO, 9)
        self.details_area.setFont(mono_font)
        self.details_area.setMinimumHeight(150)
        layout.addWidget(self.details_area)

        # Crash reporting status — only shown when a DSN is configured.
        # Since all errors are now auto-sent when consent is given, this
        # section is purely informational (no "send" button needed).
        self.reporting_status_label = None
        if crash_reporting.get_configured_dsn() is not None:
            reporting_layout = QHBoxLayout()

            if crash_reporting.is_active():
                status_text = "✓ Report sent automatically to help fix this issue."
            elif crash_reporting.is_consent_given() is False:
                status_text = (
                    "Crash reporting is disabled. Enable it in Diagnostics & Privacy settings."
                )
            else:
                status_text = (
                    "Enable crash reporting in Diagnostics & Privacy settings to share this report."
                )

            self.reporting_status_label = QLabel(status_text)
            self.reporting_status_label.setFont(Fonts.CAPTION)
            self.reporting_status_label.setWordWrap(True)
            reporting_layout.addWidget(self.reporting_status_label)
            reporting_layout.addStretch()
            layout.addLayout(reporting_layout)

        # Actions
        btn_layout = QHBoxLayout()

        self.log_btn = QPushButton("View Logs")
        self.log_btn.clicked.connect(self._open_log_folder)

        self.copy_btn = QPushButton("Copy Details")
        self.copy_btn.clicked.connect(self._copy_details)

        self.export_btn = QPushButton("Export Diagnostic Pack")
        self.export_btn.clicked.connect(self._export_diagnostic_pack)

        self.contact_label = QLabel("Contact Developer regarding errors")
        self.contact_label.setFont(Fonts.CAPTION)

        self.close_btn = QPushButton("Dismiss")
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.log_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.contact_label)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        is_fatal = bool(self.error_data.get("fatal"))
        title_color = Colors.ACCENT_DANGER if is_fatal else Colors.FG_PRIMARY
        theme_manager.apply_style(self.title_label, f"color: {title_color};")
        theme_manager.apply_style(self.subtitle_label, f"color: {Colors.FG_SECONDARY};")
        theme_manager.apply_style(
            self.contact_label, f"color: {Colors.FG_SECONDARY}; margin-right: 10px;"
        )
        if self.reporting_status_label is not None:
            is_sent = crash_reporting.is_active()
            status_color = Colors.ACCENT_SUCCESS if is_sent else Colors.FG_SECONDARY
            theme_manager.apply_style(
                self.reporting_status_label, f"color: {status_color}; font-style: italic;"
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

    def _copy_details(self):
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(json.dumps(self.error_data, indent=4))
        self.copy_btn.setText("Copied!")

    def _open_log_folder(self):
        import os
        import platform
        import subprocess

        log_path = os.path.expanduser("~/.karcytics")
        if os.path.exists(log_path):
            if platform.system() == "Darwin":
                subprocess.run(["open", log_path])
            elif platform.system() == "Windows":
                os.startfile(log_path)
            else:
                import webbrowser

                webbrowser.open(f"file://{log_path}")

    def _export_diagnostic_pack(self):
        import platform

        import psutil
        from PyQt6.QtWidgets import QFileDialog

        from karcytics.core.sbom import SBOMGenerator
        from karcytics.core.utils import AtomicJsonFile

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagnostic Pack",
            os.path.expanduser("~/karcytics_diagnostics.json"),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        # Scrub file paths from the locally exported pack — the same
        # _before_send hook strips them from Sentry events, but a locally
        # saved file bypasses that hook entirely.
        scrubbed_error = crash_reporting._scrub_value(self.error_data)

        pack = {
            "error_report": scrubbed_error,
            "system_specs": {
                "os": platform.system(),
                "os_release": platform.release(),
                "python": platform.python_version(),
                "cpu_count": psutil.cpu_count(logical=True),
                "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            },
            "sbom": SBOMGenerator().compile_sbom(),
        }

        try:
            AtomicJsonFile.save(file_path, pack)
            self.export_btn.setText("Pack Exported!")
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Failed to export diagnostic pack: {e}", exc_info=True
            )
            self.export_btn.setText("Export Failed")
