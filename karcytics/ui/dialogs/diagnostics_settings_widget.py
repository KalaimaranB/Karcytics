"""Diagnostics & Privacy settings dialog."""

import json
import os
import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karcytics.core import crash_reporting
from karcytics.core.config import AppConfig
from karcytics.core.diagnostics import diagnostics
from karcytics.ui.theme import Colors, Fonts, theme_manager


class DiagnosticsSettingsWidget(QWidget):
    """Lets the user control crash reporting consent and inspect diagnostic data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnostics & Privacy")
        self.setMinimumSize(480, 320)

        self._setup_ui()
        self._apply_styles()

        theme_manager.theme_changed.connect(self._apply_styles)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.title_label = QLabel("Diagnostics & Privacy")
        self.title_label.setFont(Fonts.H2)
        layout.addWidget(self.title_label)

        dsn_configured = crash_reporting.get_configured_dsn() is not None

        self.consent_checkbox = QCheckBox("Automatically send crash reports to help fix issues")
        self.consent_checkbox.setChecked(crash_reporting.is_consent_given() is True)
        self.consent_checkbox.setEnabled(dsn_configured)
        self.consent_checkbox.toggled.connect(crash_reporting.set_consent)
        layout.addWidget(self.consent_checkbox)

        self.detail_label = QLabel(
            (
                "When enabled, every error is automatically sent to help diagnose and fix issues.\n\n"
                "Each report includes:\n"
                "  • Error message and stack trace\n"
                "  • Last 50 log lines from this session (the 'black box')\n"
                "  • OS name and version, app release version\n"
                "  • Plugin ID and version (if the error came from a plugin)\n\n"
                "File paths are stripped before anything leaves this machine — "
                "paths ending in .fcs, .csv, .xlsx and similar data extensions "
                "are replaced with <redacted-file>. Your home directory path is "
                "also replaced with <home>. Raw variable values from stack "
                "frames are never captured."
            )
            if dsn_configured
            else "Crash reporting isn't configured for this build."
        )
        self.detail_label.setFont(Fonts.CAPTION)
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.send_test_btn = QPushButton("Send Test Event")
        self.send_test_btn.setToolTip(
            "Sends one harmless test event so you can confirm it reaches Sentry — safe to ignore."
        )
        self.send_test_btn.setEnabled(self.consent_checkbox.isChecked())
        self.consent_checkbox.toggled.connect(self.send_test_btn.setEnabled)
        self.send_test_btn.clicked.connect(self._send_test_event)
        layout.addWidget(self.send_test_btn)

        # ── Developer Tools ─────────────────────────────────────────────────
        # Only shown when running from source (not a frozen production build).
        # Lets you activate Sentry for the current session without env vars.
        self._dev_section_widgets: list = []
        if not getattr(sys, "frozen", False):
            self._build_dev_section(layout)
        # ────────────────────────────────────────────────────────────────────

        layout.addStretch()

        btn_layout = QHBoxLayout()

        self.open_logs_btn = QPushButton("Open Logs Folder")
        self.open_logs_btn.clicked.connect(self._open_logs_folder)
        btn_layout.addWidget(self.open_logs_btn)

        self.copy_report_btn = QPushButton("Copy Diagnostic Report")
        self.copy_report_btn.clicked.connect(self._copy_diagnostic_report)
        btn_layout.addWidget(self.copy_report_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _build_dev_section(self, layout: QVBoxLayout) -> None:
        """Build the developer-only Sentry testing panel."""
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)
        self._dev_section_widgets.append(divider)

        dev_title = QLabel("🔧  Developer Tools")
        dev_title.setFont(Fonts.H3 if hasattr(Fonts, "H3") else Fonts.H2)
        layout.addWidget(dev_title)
        self._dev_section_widgets.append(dev_title)

        dev_note = QLabel(
            "Activate Sentry for this session only — no restart needed.\n"
            "Changes here don't affect production builds."
        )
        dev_note.setFont(Fonts.CAPTION)
        dev_note.setWordWrap(True)
        layout.addWidget(dev_note)
        self._dev_section_widgets.append(dev_note)

        # DSN field — pre-filled from env var if already set
        dsn_row = QHBoxLayout()
        dsn_label = QLabel("Sentry DSN:")
        dsn_label.setFont(Fonts.BODY)
        self._dev_dsn_field = QLineEdit()
        self._dev_dsn_field.setPlaceholderText("https://key@host.ingest.sentry.io/project-id")
        self._dev_dsn_field.setText(os.environ.get(crash_reporting._DSN_ENV_VAR, ""))
        dsn_row.addWidget(dsn_label)
        dsn_row.addWidget(self._dev_dsn_field)
        layout.addLayout(dsn_row)
        self._dev_section_widgets.extend([dsn_label, self._dev_dsn_field])

        # Action buttons
        dev_btn_row = QHBoxLayout()

        self._dev_activate_btn = QPushButton()
        self._dev_activate_btn.clicked.connect(self._dev_toggle_sentry)
        self._refresh_activate_btn_label()
        dev_btn_row.addWidget(self._dev_activate_btn)
        self._dev_section_widgets.append(self._dev_activate_btn)

        self._dev_trigger_btn = QPushButton("⚡ Trigger Test Error")
        self._dev_trigger_btn.setToolTip(
            "Fires a real non-fatal DiagnosticEngine error so you can verify "
            "the full flow: capture → Sentry → ErrorReportDialog."
        )
        self._dev_trigger_btn.clicked.connect(self._dev_trigger_error)
        dev_btn_row.addWidget(self._dev_trigger_btn)
        self._dev_section_widgets.append(self._dev_trigger_btn)

        dev_btn_row.addStretch()
        layout.addLayout(dev_btn_row)

        self._dev_status_label = QLabel("")
        self._dev_status_label.setFont(Fonts.CAPTION)
        layout.addWidget(self._dev_status_label)
        self._dev_section_widgets.append(self._dev_status_label)

    def _refresh_activate_btn_label(self) -> None:
        if crash_reporting.is_active():
            self._dev_activate_btn.setText("✓ Sentry active — click to deactivate")
        else:
            self._dev_activate_btn.setText("▶ Activate Sentry for this session")

    def _dev_toggle_sentry(self) -> None:
        if crash_reporting.is_active():
            crash_reporting.shutdown_crash_reporting()
            self._dev_status_label.setText("Sentry deactivated for this session.")
            self.consent_checkbox.setEnabled(False)
            self.send_test_btn.setEnabled(False)
        else:
            dsn = self._dev_dsn_field.text().strip()
            if not dsn:
                self._dev_status_label.setText("⚠ Paste a Sentry DSN above first.")
                return

            # Temporarily set the env var and the sys.frozen flag so
            # get_configured_dsn() and init_crash_reporting() behave as if
            # this is a frozen production build — then restore both.
            prev_dsn = os.environ.get(crash_reporting._DSN_ENV_VAR)
            os.environ[crash_reporting._DSN_ENV_VAR] = dsn

            sys.frozen = True  # type: ignore[attr-defined]
            try:
                # Consent is required — temporarily grant it if not already
                # given, so init doesn't silently no-op.
                was_consented = crash_reporting.is_consent_given()
                if was_consented is not True:
                    crash_reporting.core_preferences.set(
                        crash_reporting.CONSENT_PREFERENCE_KEY, True
                    )

                ok = crash_reporting.init_crash_reporting()
            finally:
                del sys.frozen
                if prev_dsn is None:
                    os.environ.pop(crash_reporting._DSN_ENV_VAR, None)
                else:
                    os.environ[crash_reporting._DSN_ENV_VAR] = prev_dsn

                # Restore consent state if we changed it
                if was_consented is not True:
                    crash_reporting.core_preferences.set(
                        crash_reporting.CONSENT_PREFERENCE_KEY,
                        was_consented,  # type: ignore[arg-type]
                    )

            if ok:
                self._dev_status_label.setText(
                    "✓ Sentry is active for this session. Errors will be sent."
                )
                self.consent_checkbox.setEnabled(True)
                self.send_test_btn.setEnabled(True)
            else:
                self._dev_status_label.setText("✗ Activation failed — check that the DSN is valid.")

        self._refresh_activate_btn_label()
        self._apply_styles()

    def _dev_trigger_error(self) -> None:
        """Fire a real non-fatal DiagnosticEngine error for end-to-end testing."""
        try:
            raise RuntimeError("This is a synthetic developer test error — safe to ignore.")
        except RuntimeError as exc:
            diagnostics.report_error(
                message="Developer test error (synthetic)",
                exception=exc,
                plugin_id=None,
                fatal=False,
            )
        self._dev_status_label.setText(
            "Test error fired — check the ErrorReportDialog and your Sentry project."
        )

    def _apply_styles(self):
        theme_manager.apply_style(self.title_label, f"color: {Colors.FG_PRIMARY};")
        theme_manager.apply_style(self.detail_label, f"color: {Colors.FG_SECONDARY};")

        if hasattr(self, "_dev_status_label"):
            is_active = crash_reporting.is_active()
            status_color = Colors.ACCENT_SUCCESS if is_active else Colors.ACCENT_WARNING
            theme_manager.apply_style(
                self._dev_status_label, f"color: {status_color}; font-style: italic;"
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
            QCheckBox {{
                color: {Colors.FG_PRIMARY};
            }}
            QLineEdit {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 6px 10px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
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

    def _send_test_event(self):
        sent = crash_reporting.capture_error_data(
            {
                "message": "Karcytics test event — safe to ignore.",
                "plugin_id": None,
                "traceback": None,
            }
        )
        self.send_test_btn.setText("Test Event Sent!" if sent else "Nothing To Send")

    def _open_logs_folder(self):
        logs_dir = AppConfig.APP_DATA_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir)))

    def _copy_diagnostic_report(self):
        report = diagnostics.get_full_diagnostic_report()
        QApplication.clipboard().setText(json.dumps(report, indent=2, default=str))
        self.copy_report_btn.setText("Copied!")
