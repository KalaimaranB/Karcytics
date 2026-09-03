from datetime import datetime

from karcytics_sdk.plugin import DangerButton, PrimaryButton, SecondaryButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from karcytics.shared.ui.alerts import ask_question, show_error, show_info
from karcytics.ui.theme import Colors, theme_manager


class WorkflowPropertiesDialog(QDialog):
    """Dialog showing workflow file metadata, tags, and deletion options."""

    workflow_deleted = pyqtSignal()
    attachment_deleted = pyqtSignal()
    workflow_updated = pyqtSignal()

    def __init__(self, project_manager, module_id: str, filename: str, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.module_id = module_id
        self.filename = filename

        # Load data
        self.payload = self.project_manager.load_workflow_payload(self.filename)
        self.wf_path = self.project_manager.workflows.wf_dir / self.filename
        try:
            from karcytics.core.utils import AtomicJsonFile

            self.full_data = AtomicJsonFile.load(self.wf_path, default={})
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug(f"Failed to load workflow data: {e}")
            self.full_data = {}

        self.metadata = self.full_data.get("metadata", {})
        self.attachments = self.full_data.get("attachments", [])

        self.setWindowTitle(f"Workflow Properties: {self.metadata.get('name', 'Untitled')}")
        self.setMinimumSize(500, 500)
        theme_manager.apply_style(
            self, f"background-color: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        lbl_title = QLabel("Workflow Properties")
        theme_manager.apply_style(
            lbl_title, f"font-size: 18px; font-weight: bold; color: {Colors.FG_PRIMARY};"
        )
        layout.addWidget(lbl_title)

        # File Stats
        wf_size = self.wf_path.stat().st_size if self.wf_path.exists() else 0
        wf_size_str = self._format_size(wf_size)

        created_str = "Unknown"
        modified_str = "Unknown"
        if self.wf_path.exists():
            stat = self.wf_path.stat()
            created_str = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Form Layout for Metadata
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.lbl_name = QLabel(self.metadata.get("name", "Untitled"))
        form_layout.addRow("Name:", self.lbl_name)

        lbl_size = QLabel(wf_size_str)
        theme_manager.apply_style(lbl_size, f"color: {Colors.FG_SECONDARY};")
        form_layout.addRow("Size:", lbl_size)

        lbl_created = QLabel(created_str)
        theme_manager.apply_style(lbl_created, f"color: {Colors.FG_SECONDARY};")
        form_layout.addRow("Created:", lbl_created)

        lbl_modified = QLabel(modified_str)
        theme_manager.apply_style(lbl_modified, f"color: {Colors.FG_SECONDARY};")
        form_layout.addRow("Modified:", lbl_modified)

        # Editable Tags
        self.edit_tags = QLineEdit()
        tags = self.metadata.get("tags", [])
        self.edit_tags.setText(", ".join(tags))
        self.edit_tags.setPlaceholderText("tag1, tag2, tag3")
        theme_manager.apply_style(
            self.edit_tags,
            f"background: {Colors.BG_MEDIUM}; border: 1px solid {Colors.BORDER}; color: {Colors.FG_PRIMARY}; padding: 4px; border-radius: 4px;",
        )
        form_layout.addRow("Tags:", self.edit_tags)

        # Editable Description
        self.edit_desc = QTextEdit()
        self.edit_desc.setPlainText(self.metadata.get("description", ""))
        self.edit_desc.setPlaceholderText("Workflow description...")
        self.edit_desc.setMaximumHeight(80)
        theme_manager.apply_style(
            self.edit_desc,
            f"background: {Colors.BG_MEDIUM}; border: 1px solid {Colors.BORDER}; color: {Colors.FG_PRIMARY}; padding: 4px; border-radius: 4px;",
        )
        form_layout.addRow("Description:", self.edit_desc)

        layout.addLayout(form_layout)

        # Save Button for Metadata
        btn_save = PrimaryButton("Save Metadata")
        btn_save.clicked.connect(self._on_save_metadata)

        save_layout = QHBoxLayout()
        save_layout.addStretch()
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)

        # Attachments Section
        if self.attachments:
            layout.addWidget(self._create_section_header("Associated Data (Attachments)"))

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            theme_manager.apply_style(scroll, "QScrollArea { border: none; }")

            att_container = QWidget()
            att_layout = QVBoxLayout(att_container)
            att_layout.setContentsMargins(0, 0, 0, 0)

            for att in self.attachments:
                att_layout.addWidget(self._create_attachment_row(att))

            att_layout.addStretch()
            scroll.setWidget(att_container)
            layout.addWidget(scroll)
        else:
            lbl_no_data = QLabel("No associated data blocks.")
            theme_manager.apply_style(lbl_no_data, f"color: {Colors.FG_SECONDARY};")
            layout.addWidget(lbl_no_data)

        layout.addStretch()

        # Danger Zone
        danger_frame = QFrame()
        theme_manager.apply_style(
            danger_frame, f"border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 6px;"
        )
        danger_layout = QHBoxLayout(danger_frame)

        lbl_danger = QLabel("Delete Entire Workflow")
        theme_manager.apply_style(
            lbl_danger, f"color: {Colors.ACCENT_DANGER}; font-weight: bold; border: none;"
        )

        btn_delete_wf = DangerButton("Delete")
        btn_delete_wf.clicked.connect(self._on_delete_workflow)

        danger_layout.addWidget(lbl_danger)
        danger_layout.addStretch()
        danger_layout.addWidget(btn_delete_wf)

        layout.addWidget(danger_frame)

        # Close
        btn_close = SecondaryButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _create_section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        theme_manager.apply_style(
            lbl,
            f"font-weight: bold; color: {Colors.FG_PRIMARY}; margin-top: 10px; border-bottom: 1px solid {Colors.BORDER}; padding-bottom: 4px;",
        )
        return lbl

    def _create_attachment_row(self, att: dict) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 5, 0, 5)

        name = att.get("filename", "Unknown")
        size = att.get("size_bytes", 0)
        key = att.get("key", "")

        lbl_name = QLabel(name)
        lbl_size = QLabel(self._format_size(size))
        theme_manager.apply_style(lbl_size, f"color: {Colors.FG_SECONDARY};")

        btn_del = QPushButton("🗑️")
        btn_del.setFixedSize(24, 24)
        theme_manager.apply_style(
            btn_del,
            f"""
            QPushButton {{ background: transparent; border: none; }}
            QPushButton:hover {{ background: {Colors.ACCENT_DANGER}44; border-radius: 4px; }}
        """,
        )
        btn_del.clicked.connect(lambda: self._on_delete_attachment(key, name))

        row_layout.addWidget(lbl_name)
        row_layout.addStretch()
        row_layout.addWidget(lbl_size)
        row_layout.addWidget(btn_del)

        return row

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _on_save_metadata(self):
        tags_raw = self.edit_tags.text()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        desc = self.edit_desc.toPlainText().strip()

        self.metadata["tags"] = tags
        self.metadata["description"] = desc

        try:
            self.project_manager.save_workflow(
                self.module_id,
                self.payload,
                self.metadata,
                self.filename,
                self.attachments,
            )
            self.full_data["metadata"] = self.metadata
            self.workflow_updated.emit()
            show_info(self, "Success", "Workflow metadata updated successfully.")
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Failed to save metadata: {e}")
            show_error(self, "Error", f"Failed to save metadata:\n{str(e)}")

    def _on_delete_attachment(self, key: str, name: str):
        if ask_question(
            self,
            "Delete Data Block",
            f"Are you sure you want to delete '{name}'?\nThis cannot be undone.",
        ):
            if self.project_manager.delete_workflow_attachment(self.filename, key):
                self.attachment_deleted.emit()
                self.accept()
            else:
                show_error(self, "Error", "Failed to delete attachment.")

    def _on_delete_workflow(self):
        if ask_question(
            self,
            "Delete Workflow",
            "Are you sure you want to permanently delete this workflow and all its data?\n\nThis cannot be undone.",
        ):
            if self.project_manager.delete_workflow(self.module_id, self.filename):
                self.workflow_deleted.emit()
                self.accept()
            else:
                show_error(self, "Error", "Failed to delete workflow.")
