"""Simple text window for viewing application logs."""

from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from karcytics.core.config import AppConfig
from karcytics.ui.theme import Colors, Fonts, theme_manager


class LogViewerDialog(QDialog):
    """A dialog to browse the core, IPC, and per-plugin log files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Karcytics Logs")
        self.setMinimumSize(800, 600)

        self._setup_ui()
        self._apply_styles()
        self._populate_sources()
        self._load_logs()

        from karcytics.ui.theme import theme_manager

        theme_manager.theme_changed.connect(self._apply_styles)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.source_selector = QComboBox()
        self.source_selector.currentIndexChanged.connect(self._load_logs)
        layout.addWidget(self.source_selector)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        mono_font = QFont(Fonts.FAMILY_MONO, 10)
        self.text_area.setFont(mono_font)
        self.text_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_area)

        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self._copy_logs)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        theme_manager.apply_style(
            self,
            f"""
            QDialog {{
                background-color: {Colors.BG_DARKEST};
                border: 1px solid {Colors.BORDER};
            }}
            QTextEdit {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
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
            QComboBox {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 6px 10px;
                border-radius: 4px;
            }}
        """,
        )

    def _logs_dir(self) -> Path:
        return AppConfig.APP_DATA_DIR / "logs"

    def _populate_sources(self):
        logs_dir = self._logs_dir()
        self.source_selector.blockSignals(True)
        self.source_selector.clear()
        self.source_selector.addItem("Core", logs_dir / "core.log")
        self.source_selector.addItem("Plugin Communication (IPC)", logs_dir / "ipc.log")
        plugins_dir = logs_dir / "plugins"
        if plugins_dir.is_dir():
            for log_file in sorted(plugins_dir.glob("*.log")):
                self.source_selector.addItem(f"Plugin: {log_file.stem}", log_file)
        self.source_selector.blockSignals(False)

    def _refresh(self):
        current_path = self.source_selector.currentData()
        self._populate_sources()
        if current_path is not None:
            idx = self.source_selector.findData(current_path)
            if idx >= 0:
                self.source_selector.setCurrentIndex(idx)
        self._load_logs()

    def _load_logs(self):
        log_file = self.source_selector.currentData()
        if log_file is None:
            self.text_area.setPlainText("No log source selected.")
        elif log_file.exists():
            try:
                with open(log_file, encoding="utf-8") as f:
                    content = f.read()
                self.text_area.setPlainText(content)
                # Scroll to bottom
                scrollbar = self.text_area.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except Exception as e:
                self.text_area.setPlainText(f"Error reading log file:\n{e}")
        else:
            self.text_area.setPlainText(f"Log file not found at {log_file}")
        self.copy_btn.setText("Copy to Clipboard")

    def _copy_logs(self):
        QApplication.clipboard().setText(self.text_area.toPlainText())
        self.copy_btn.setText("Copied!")
