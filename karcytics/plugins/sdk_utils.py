"""Common utilities for plugins — I/O, dialogs, file handling."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QLabel, QMessageBox, QVBoxLayout

from karcytics.core.config import AppConfig

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# FILE DIALOGS
# ──────────────────────────────────────────────────────────────────────────────


def get_image_path(parent=None, title: str = "Select Image", start_dir: str = "") -> str | None:
    """Show file dialog to select an image.

    Args:
        parent: Parent widget
        title: Dialog title
        start_dir: Initial directory

    Returns:
        Selected file path or None if cancelled
    """
    file_path, _ = QFileDialog.getOpenFileName(
        parent, title, start_dir, "Images (*.png *.jpg *.jpeg *.tiff *.tif);;All Files (*)"
    )
    return file_path if file_path else None


def get_image_paths(parent=None, title: str = "Select Images", start_dir: str = "") -> list[str]:
    """Show file dialog to select multiple images."""
    file_paths, _ = QFileDialog.getOpenFileNames(
        parent, title, start_dir, "Images (*.png *.jpg *.jpeg *.tiff *.tif);;All Files (*)"
    )
    return file_paths if file_paths else []


def import_assets_workflow(parent, project_manager, file_paths: list[str]) -> list[str]:
    """Orchestrates the multi-file import workflow."""
    if not file_paths:
        return []

    subfolder = None
    if len(file_paths) > 1 and ask_yes_no(
        parent,
        "Group Files?",
        "Would you like to create a subdirectory in 'assets' for this collected set of files?",
    ):
        subfolder = get_text(
            parent, "Subdirectory Name", "Enter folder name:", default="experiment_data"
        )
        if not subfolder or not subfolder.strip():
            subfolder = None

    copy_to_workspace = ask_yes_no(
        parent,
        "Copy to Workspace?",
        f"Copy these {len(file_paths)} files into the project assets folder?",
    )

    from pathlib import Path

    path_objs = [Path(p) for p in file_paths]

    return project_manager.batch_add_images(path_objs, copy_to_workspace, subfolder)


def get_save_path(
    parent=None, title: str = "Save As", start_dir: str = "", file_filter: str = ""
) -> str | None:
    """Show save file dialog.

    Args:
        parent: Parent widget
        title: Dialog title
        start_dir: Initial directory
        file_filter: Qt file filter string (e.g. "CSV Files (*.csv);;All Files (*)")

    Returns:
        Selected file path or None if cancelled
    """
    if not file_filter:
        file_filter = "All Files (*)"

    file_path, _ = QFileDialog.getSaveFileName(parent, title, start_dir, file_filter)
    return file_path if file_path else None


def get_directory(parent=None, title: str = "Select Directory", start_dir: str = "") -> str | None:
    """Show directory selection dialog.

    Args:
        parent: Parent widget
        title: Dialog title
        start_dir: Initial directory

    Returns:
        Selected directory path or None if cancelled
    """
    dir_path = QFileDialog.getExistingDirectory(parent, title, start_dir)
    return dir_path if dir_path else None


# ──────────────────────────────────────────────────────────────────────────────
# MESSAGE BOXES
# ──────────────────────────────────────────────────────────────────────────────


from karcytics.shared.ui.alerts import ask_question  # noqa: E402


def ask_yes_no(parent=None, title: str = "", message: str = "") -> bool:
    """Show yes/no question dialog.

    Returns:
        True if user clicks Yes, False otherwise
    """
    return ask_question(parent, title, message, default_no=True)


def ask_ok_cancel(parent=None, title: str = "", message: str = "") -> bool:
    """Show OK/Cancel dialog.

    Returns:
        True if user clicks OK, False otherwise
    """
    reply = QMessageBox.question(
        parent, title, message, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )
    return reply == QMessageBox.StandardButton.Ok


# ──────────────────────────────────────────────────────────────────────────────
# INPUT DIALOGS
# ──────────────────────────────────────────────────────────────────────────────


def get_text(parent=None, title: str = "", label: str = "", default: str = "") -> str | None:
    """Show text input dialog.

    Returns:
        User input or None if cancelled
    """
    text, ok = QInputDialog.getText(parent, title, label, text=default)
    return text if ok else None


def get_number(
    parent=None,
    title: str = "",
    label: str = "",
    value: int = 0,
    min_val: int = -999999,
    max_val: int = 999999,
) -> int | None:
    """Show integer input dialog.

    Returns:
        User input or None if cancelled
    """
    num, ok = QInputDialog.getInt(parent, title, label, value, min_val, max_val)
    return num if ok else None


def get_double(
    parent=None,
    title: str = "",
    label: str = "",
    value: float = 0.0,
    min_val: float = -999.99,
    max_val: float = 999.99,
    decimals: int = 2,
) -> float | None:
    """Show float input dialog.

    Returns:
        User input or None if cancelled
    """
    num, ok = QInputDialog.getDouble(parent, title, label, value, min_val, max_val, decimals)
    return num if ok else None


# ──────────────────────────────────────────────────────────────────────────────
# JSON UTILITIES
# ──────────────────────────────────────────────────────────────────────────────


def load_json(path: str) -> dict[str, Any]:
    """Load JSON from file.

    Args:
        path: File path

    Returns:
        Parsed JSON dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    import json

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict[str, Any], pretty: bool = True) -> None:
    """Save JSON to file.

    Args:
        path: File path
        data: Dictionary to save
        pretty: If True, indent for readability
    """
    from karcytics.core.utils import AtomicJsonFile

    AtomicJsonFile.save(path, data, indent=2 if pretty else None)


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────


class PluginConfig:
    """Simple configuration management for plugins.

    Stores settings in JSON in ~/.karcytics/plugin_configs/{plugin_id}.json

    Example:
        config = PluginConfig('my_plugin')
        config.set('threshold', 0.5)
        threshold = config.get('threshold', default=0.0)
        config.save()
    """

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.config_dir = AppConfig.APP_DATA_DIR / "plugin_configs"
        self.config_file = self.config_dir / f"{plugin_id}.json"
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load config from disk."""
        if self.config_file.exists():
            try:
                self.data = load_json(str(self.config_file))
            except Exception as e:
                logger.warning(f"Failed to load config for {self.plugin_id}: {e}")
                self.data = {}
        else:
            self.data = {}

    def save(self) -> None:
        """Save config to disk."""
        try:
            save_json(str(self.config_file), self.data)
        except Exception as e:
            logger.error(f"Failed to save config for {self.plugin_id}: {e}")

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.data.get(key, default)

    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self.data

    def clear(self) -> None:
        """Clear all config."""
        self.data.clear()

    def __getitem__(self, key: str):
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────────────────────────────────────


def validate_file_exists(path: str) -> tuple[bool, str]:
    """Check if file exists.

    Returns:
        (is_valid, error_message)
    """
    if not path:
        return False, "File path is empty"
    if not Path(path).exists():
        return False, f"File not found: {path}"
    return True, ""


def validate_directory_exists(path: str) -> tuple[bool, str]:
    """Check if directory exists.

    Returns:
        (is_valid, error_message)
    """
    if not path:
        return False, "Directory path is empty"
    if not Path(path).is_dir():
        return False, f"Directory not found: {path}"
    return True, ""


def validate_value_range(
    value: float, min_val: float, max_val: float, name: str = "value"
) -> tuple[bool, str]:
    """Check if value is within range.

    Returns:
        (is_valid, error_message)
    """
    if value < min_val or value > max_val:
        return False, f"{name} must be between {min_val} and {max_val}"
    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────


def get_plugin_logger(plugin_id: str) -> logging.Logger:
    """Get a logger for a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        Configured logger with plugin name
    """
    return logging.getLogger(f"karcytics.plugins.{plugin_id}")


# ──────────────────────────────────────────────────────────────────────────────
# PROGRESS DIALOG
# ──────────────────────────────────────────────────────────────────────────────


class ProgressDialog(QDialog):
    """Simple progress dialog for long operations.

    Example:
        dialog = ProgressDialog(parent, "Processing...")
        dialog.show()

        for i in range(100):
            # Do work
            dialog.setValue(i)

        dialog.close()
    """

    def __init__(self, parent=None, title: str = "Please Wait", message: str = "Processing..."):
        """
        Initialize a modal progress dialog with a title, message, and zero-percent progress display.

        Parameters:
            parent: Optional parent widget.
            title (str): Window title.
            message (str): Message displayed above the progress percentage.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))

        self.label = QLabel("0%")
        layout.addWidget(self.label)

        self.value = 0

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set the progress value as a percentage.

        Parameters:
            value (int): The progress value, clamped to the range 0–100.
        """
        self.value = max(0, min(100, value))
        self.label.setText(f"{self.value}%")
        self.update()
