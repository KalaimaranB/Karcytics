import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from karcytics.ui.workers.plugin_dependency_installer import PluginDependencyInstallerWorker

logger = logging.getLogger(__name__)


class DependencyInstallerDialog(QDialog):
    """Dialog that shows progress while installing python dependencies for a plugin."""

    def __init__(self, plugin_dir: Path, plugin_name: str, parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.plugin_name = plugin_name

        self.setWindowTitle(f"Installing Dependencies - {self.plugin_name}")
        self.setFixedSize(600, 400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        # Prevent closing during install
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)

        self.setup_ui()
        self.start_installation()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"Setting up Python environment for {self.plugin_name}...")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Starting installation...")
        layout.addWidget(self.status_label)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        font = QFont("Courier", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_console.setFont(font)
        self.log_console.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; padding: 5px; border-radius: 4px; }"
        )
        layout.addWidget(self.log_console)

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.retry_btn = QPushButton("Retry")
        self.retry_btn.hide()
        self.retry_btn.clicked.connect(self.start_installation)
        btn_layout.addWidget(self.retry_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.hide()
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def start_installation(self):
        self.retry_btn.hide()
        self.close_btn.hide()
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Installing...")
        self.log_console.clear()

        self.worker = PluginDependencyInstallerWorker(self.plugin_dir)
        self.worker.progress.connect(self.on_progress)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, value):
        if value == 100:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)

    def on_log_message(self, message: str):
        self.log_console.appendPlainText(message)
        scrollbar = self.log_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_finished(self, success: bool, message: str):
        if success:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText("Installation complete!")
            self.accept()
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Error: {message}")
            self.retry_btn.show()
            self.close_btn.show()
            # Re-enable close button on failure
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowCloseButtonHint)
            self.show()
