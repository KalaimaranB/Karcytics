import logging

from karcytics_sdk.plugin.galactic_loader import QML_PATH
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget

from karcytics.ui.theme import Colors, theme_manager

_logger = logging.getLogger(__name__)


class GalacticLoader(QQuickWidget):
    """A cinematic Galactic hyperspace loading screen using QML.

    This replaces the old QWidget/paintEvent subprocess loader. By using
    QML and a QQuickWidget, the scene graph renders on a dedicated C++ thread,
    remaining buttery smooth (60fps) even when the main Python thread is blocked
    by heavy GIL-locking imports (e.g., pandas/numpy).
    """

    warp_out_finished = Signal()
    fade_out_finished = Signal()

    def __init__(self, parent=None):
        """
        Initialize the QML-based Galactic loading widget.

        Parameters:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Transparent background for the widget itself
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        self.setClearColor(Qt.GlobalColor.transparent)
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)

        # QML_PATH is karcytics_sdk's copy — the single canonical source for
        # this animation, shared with the isolated-process loader (see that
        # module's docstring for why the Python wrapper isn't shared too).
        if not QML_PATH.exists():
            _logger.error(
                "CRITICAL: QML file not found at %s! The loader will fail and transition will freeze.",
                QML_PATH,
            )

        self.setSource(QUrl.fromLocalFile(str(QML_PATH)))

        if self.status() == QQuickWidget.Status.Error:
            errors = "\n".join([e.toString() for e in self.errors()])
            _logger.error("Failed to load QML source: %s", errors)

        # Connect to theme changes
        theme_manager.theme_changed.connect(self.update_colors)

        # Connect the QML signal back to our Python signal
        root = self.rootObject()
        if root:
            root.warpOutFinished.connect(self.warp_out_finished.emit)
            if hasattr(root, "fadeOutFinished"):
                root.fadeOutFinished.connect(self.fade_out_finished.emit)
            self.update_colors()

    def update_colors(self):
        """
        Update the QML loader colors to reflect the current application theme.
        """
        root = self.rootObject()
        if not root:
            return

        bg_color = Colors.BG_DARKEST
        is_sw = "Galactic" in theme_manager.current_theme_name
        is_dark_side = is_sw and getattr(Colors, "DNA_PRIMARY", "").upper() == "#E60000"

        accent = Colors.ACCENT_PRIMARY
        if is_sw:
            accent = Colors.ACCENT_PRIMARY if not is_dark_side else Colors.DNA_PRIMARY

        text_color = Colors.FG_PRIMARY

        # QML requires standard hex codes, sometimes without alpha or properly formatted
        root.setProperty("bgColor", bg_color)
        root.setProperty("accentColor", accent)
        root.setProperty("textColor", text_color)

    def set_module(self, name: str):
        """
        Reset the loader and assign it to a new module.

        Parameters:
            name (str): Name of the module to display.
        """
        root = self.rootObject()
        if root:
            root.setProperty("moduleName", name)
            import PySide6.QtCore as QtCore

            QtCore.QMetaObject.invokeMethod(root, "reset")

    def set_status_message(self, msg: str) -> None:
        """Update the secondary status line during Phase 2.

        Called by PluginLoaderManager once the skeleton panel is built and
        Phase 2 (heavy widget construction) is about to begin. The message
        replaces the default 'STATUS: HYPERDRIVE ENGAGED' text so the user
        sees a meaningful progress indicator while the loader is still visible.
        """
        root = self.rootObject()
        if root:
            root.setProperty("statusMessage", msg)

    def warp_out(self):
        """Begin the cinematic warp-out sequence."""
        root = self.rootObject()
        if root:
            import PySide6.QtCore as QtCore

            QtCore.QMetaObject.invokeMethod(root, "warpOut")

    def fade_out(self, duration_ms: int = 500):
        """
        Begin the loader's fade-out transition.

        Parameters:
            duration_ms (int): Duration of the transition in milliseconds.
        """
        root = self.rootObject()
        if root:
            import PySide6.QtCore as QtCore

            QtCore.QMetaObject.invokeMethod(root, "fadeOut", QtCore.Q_ARG("QVariant", duration_ms))


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    loader = GalacticLoader()
    loader.set_module("Test Module")
    loader.resize(1000, 700)
    loader.show()

    # Test warp out after 3 seconds
    from PySide6.QtCore import QTimer

    QTimer.singleShot(3000, loader.warp_out)

    sys.exit(app.exec())
