from pathlib import Path

from karcytics_sdk.plugin import PrimaryButton, SecondaryButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from karcytics.core.plugin_doctor import CheckStatus, PluginDoctor
from karcytics.shared.ui.alerts import show_error, show_info, show_warning
from karcytics.ui.theme import Colors, theme_manager


class PluginDoctorDialog(QDialog):
    """Diagnose and Repair dialog for an installed plugin."""

    def __init__(self, plugin_id: str, plugin_dir: Path, updater, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.plugin_dir = plugin_dir
        self.updater = updater
        self.doctor = PluginDoctor(plugin_id, plugin_dir)

        self.setWindowTitle(f"Plugin Doctor - {plugin_id}")
        self.setMinimumSize(650, 500)
        theme_manager.apply_style(
            self, f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};"
        )

        self.has_repairable_issues = False
        self.has_manual_issues = False

        self._setup_ui()
        self.run_diagnostics()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Header
        header_lbl = QLabel(f"🩺 Diagnostic Report: {self.plugin_id}")
        theme_manager.apply_style(
            header_lbl, f"font-size: 18px; font-weight: bold; color: {Colors.FG_PRIMARY};"
        )
        self.layout.addWidget(header_lbl)

        # Scroll Area for Checklist
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        theme_manager.apply_style(
            self.scroll, "QScrollArea { border: none; background: transparent; }"
        )

        self.content = QWidget()
        theme_manager.apply_style(self.content, "background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)
        self.layout.addWidget(self.scroll)

        # Bottom Actions
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.export_btn = SecondaryButton("Export Diagnostic Bundle")
        self.export_btn.clicked.connect(self._export_bundle)
        actions_layout.addWidget(self.export_btn)

        self.open_folder_btn = SecondaryButton("Open Plugin Folder")
        self.open_folder_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(Qt.QUrl.fromLocalFile(str(self.plugin_dir.absolute())))
        )
        actions_layout.addWidget(self.open_folder_btn)

        actions_layout.addStretch()

        self.repair_btn = PrimaryButton("Repair Auto-Fixable Issues")
        self.repair_btn.clicked.connect(self._run_repairs)
        self.repair_btn.hide()
        actions_layout.addWidget(self.repair_btn)

        self.close_btn = SecondaryButton("Close")
        self.close_btn.clicked.connect(self.accept)
        actions_layout.addWidget(self.close_btn)

        self.layout.addLayout(actions_layout)

    def run_diagnostics(self):
        """Run the doctor and update the UI."""
        # Clear existing layout
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        self.has_repairable_issues = False
        self.has_manual_issues = False

        results = self.doctor.run_all_checks()

        phases = {
            "phase1": "Phase 1: Location & Download Integrity",
            "phase2": "Phase 2: Trust & Install State Consistency",
            "phase3": "Phase 3: Dependency Completeness",
            "phase4": "Phase 4: Runtime/Process Health",
        }

        for phase_key, title in phases.items():
            phase_lbl = QLabel(title)
            theme_manager.apply_style(
                phase_lbl,
                f"font-weight: bold; font-size: 14px; margin-top: 10px; color: {Colors.ACCENT_PRIMARY};",
            )
            self.content_layout.addWidget(phase_lbl)

            for res in results.get(phase_key, []):
                row = QWidget()
                theme_manager.apply_style(
                    row, f"background: {Colors.BG_MEDIUM}; border-radius: 4px; padding: 5px;"
                )
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 5, 10, 5)

                if res.status == CheckStatus.OK:
                    icon = "✅"
                    color = Colors.ACCENT_SUCCESS
                elif res.status == CheckStatus.WARN:
                    icon = "⚠️"
                    color = Colors.ACCENT_WARNING
                elif res.status == CheckStatus.FAIL:
                    icon = "❌"
                    color = Colors.DNA_PRIMARY
                    self.has_repairable_issues = True
                else:
                    icon = "🛑"
                    color = Colors.DNA_PRIMARY
                    self.has_manual_issues = True

                icon_lbl = QLabel(icon)
                row_layout.addWidget(icon_lbl)

                text_layout = QVBoxLayout()
                title_lbl = QLabel(res.check_name)
                theme_manager.apply_style(title_lbl, f"font-weight: bold; color: {color};")
                text_layout.addWidget(title_lbl)

                msg_lbl = QLabel(res.message)
                msg_lbl.setWordWrap(True)
                theme_manager.apply_style(
                    msg_lbl, f"font-size: 11px; color: {Colors.FG_SECONDARY};"
                )
                text_layout.addWidget(msg_lbl)

                if hasattr(res, "details") and res.details:
                    details_lbl = QLabel(res.details)
                    details_lbl.setWordWrap(True)
                    theme_manager.apply_style(
                        details_lbl,
                        f"font-size: 10px; color: {Colors.DNA_PRIMARY}; font-style: italic; margin-top: 2px;",
                    )
                    text_layout.addWidget(details_lbl)

                row_layout.addLayout(text_layout)
                row_layout.addStretch()

                self.content_layout.addWidget(row)

        if self.has_repairable_issues:
            self.repair_btn.show()
        else:
            self.repair_btn.hide()

        self.content_layout.addStretch()

    def _export_bundle(self):
        bundle = self.doctor.export_diagnostic_bundle()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagnostic Bundle",
            f"karcytics_diagnostic_{self.plugin_id}.json",
            "JSON Files (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(bundle)
            show_info(self, "Exported", "Diagnostic bundle saved successfully.")

    def _run_repairs(self):
        """Execute safe repairs."""
        if self.has_manual_issues:
            show_warning(
                self,
                "Manual Actions Required",
                "Some issues require manual intervention (e.g., closing locked files). "
                "Automated repairs will proceed for other issues.",
            )

        # 1. Re-download if Phase 1 failed
        phase1_failed = any(r.status == CheckStatus.FAIL for r in self.doctor.results["phase1"])
        if phase1_failed:
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
            # We don't have mod_data in full format here, but updater can fetch it
            remote_data = self.updater.fetch_remote_registry(self.updater.registry_url)
            if remote_data and self.plugin_id in remote_data.get("plugins", {}):
                mod_data = remote_data["plugins"][self.plugin_id]
                success, msg = self.updater.install_plugin(self.plugin_id, mod_data)
                if not success:
                    show_error(self, "Repair Failed", f"Failed to re-download plugin: {msg}")
                    return

        # 2. Reinstall Dependencies if Phase 2 or 3 failed
        phase2_failed = any(r.status == CheckStatus.FAIL for r in self.doctor.results["phase2"])
        phase3_failed = any(r.status == CheckStatus.FAIL for r in self.doctor.results["phase3"])

        if phase2_failed or phase3_failed:
            import shutil

            # Clean reinstall of venv
            venv_path = self.plugin_dir / ".venv"
            if venv_path.exists():
                try:
                    shutil.rmtree(venv_path)
                except Exception as e:
                    show_error(
                        self,
                        "Repair Failed",
                        f"Could not clear broken environment. File may be locked: {str(e)}",
                    )
                    return

            from karcytics.ui.dialogs.dependency_installer_dialog import DependencyInstallerDialog

            installer = DependencyInstallerDialog(self.plugin_dir, self.plugin_id, parent=self)
            installer.exec()

        show_info(self, "Repair Complete", "Automated repairs finished. Re-running diagnostics.")
        self.run_diagnostics()
