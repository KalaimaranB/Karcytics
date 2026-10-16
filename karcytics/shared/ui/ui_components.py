import warnings  # noqa: D100

warnings.warn(
    "Importing UI components from `karcytics.shared.ui.ui_components` is deprecated and will be removed in a future version. "  # noqa: E501
    "Please import from `karcytics_sdk.plugin.components` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QFrame, QLabel, QPushButton  # noqa: E402


class PrimaryButton(QPushButton):
    """The main action button (accent color)."""

    def __init__(self, text, parent=None):  # noqa: D107
        """Initialize a primary-styled button with the specified text and optional parent widget.

        Parameters:
            text: The text displayed on the button.
            parent: The optional parent widget.
        """
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("PrimaryButton")


class SecondaryButton(QPushButton):
    """The standard outline/cancel button."""

    def __init__(self, text, parent=None):  # noqa: D107
        """Initialize a secondary-styled button with the specified text and parent widget.

        Parameters:
            text: The label displayed on the button.
            parent: The optional parent widget.
        """
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("SecondaryButton")


class ModuleCard(QFrame):
    """A standardized, interactive card for lists and grids."""

    def __init__(self, parent=None):  # noqa: D107
        super().__init__(parent)
        self.setObjectName("BioCard")
        self.setObjectName("BioCard")


class HeaderLabel(QLabel):
    """Standardized H1 Header."""

    def __init__(self, text, parent=None):  # noqa: D107
        super().__init__(text, parent)
        self.setObjectName("HeaderLabel")


class DangerButton(QPushButton):
    """The standard destructive/remove button."""

    def __init__(self, text, parent=None):  # noqa: D107
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("DangerButton")
