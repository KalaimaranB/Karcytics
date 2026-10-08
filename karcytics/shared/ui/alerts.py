from PySide6.QtWidgets import QMessageBox, QWidget  # noqa: D100


def show_error(parent: QWidget | None, title: str, text: str) -> None:
    """Displays a standard critical error dialog."""
    QMessageBox.critical(parent, title, text)


def show_warning(parent: QWidget | None, title: str, text: str) -> None:
    """Displays a standard warning dialog."""
    QMessageBox.warning(parent, title, text)


def show_info(parent: QWidget | None, title: str, text: str) -> None:
    """Displays a standard information dialog."""
    QMessageBox.information(parent, title, text)


def show_about(parent: QWidget | None, title: str, text: str) -> None:
    """Displays an about dialog."""
    QMessageBox.about(parent, title, text)


def ask_question(parent: QWidget | None, title: str, text: str, default_no: bool = True) -> bool:
    """Displays a Yes/No question dialog and returns True if Yes was clicked."""
    default_button = QMessageBox.StandardButton.No if default_no else QMessageBox.StandardButton.Yes
    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_button,
    )
    return reply == QMessageBox.StandardButton.Yes
