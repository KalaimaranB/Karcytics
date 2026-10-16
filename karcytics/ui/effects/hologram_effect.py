from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from karcytics.ui.theme import Colors


class HologramEffect(QWidget):
    """A high-tech holographic overlay with moving scanlines and a scan beam."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._offset = 0
        self._beam_x = 0
        self._flicker = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.start(30)  # Faster for smoother beam

    def _update_animation(self):
        # 1. Update horizontal scanlines
        """
        Update the holographic overlay animation state and schedule a repaint.
        """
        self._offset = (self._offset + 1) % 20

        # 2. Update vertical scan beam
        self._beam_x += 10
        if self._beam_x > self.width():
            self._beam_x = -50

        # 3. Subtle flicker
        import random

        if random.random() > 0.95:
            self._flicker = random.uniform(0.7, 1.0)
        else:
            self._flicker = 1.0

        self.update()

    def paintEvent(self, event):  # noqa: ARG002, N802
        """
        Paints the holographic overlay with a soft vertical depth gradient and current opacity.
        """
        if Colors.SCANLINE_OPACITY <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._flicker)

        h = self.height()

        # 1. Add a soft vertical gradient for depth
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor(0, 0, 0, 30))
        gradient.setColorAt(0.5, QColor(0, 0, 0, 0))
        gradient.setColorAt(1, QColor(0, 0, 0, 30))
        painter.fillRect(self.rect(), gradient)
