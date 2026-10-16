import math
import random

from karcytics_sdk.plugin.cyto_character import CytoWidget
from PySide6.QtCore import Property, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class Confetti:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dx = random.uniform(-5, 5)
        self.dy = random.uniform(-15, -5)
        self.color = random.choice(
            [
                QColor("#58a6ff"),
                QColor("#39ff14"),
                QColor("#f78166"),
                QColor("#d29922"),
                QColor("#a371f7"),
            ]
        )
        self.size = random.uniform(4, 8)
        self.angle = random.uniform(0, 360)
        self.rot_speed = random.uniform(-10, 10)

    def update(self):
        self.dy += 0.5  # Gravity
        self.x += self.dx
        self.y += self.dy
        self.angle += self.rot_speed
        return self.y < 2000


class BadgeAwardOverlay(QWidget):
    """Full-screen animation modal for when a user earns an Academy Badge."""

    animation_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        self.badge_name = ""
        self.badge_icon = ""
        self._bg_alpha = 0
        self._badge_scale = 0.0

        self.confetti = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_frame)

        self.cyto = CytoWidget(self)
        self.cyto.hide()

    def play_award(self, badge_name: str, badge_icon: str):
        """Starts the award sequence."""
        self.badge_name = badge_name
        self.badge_icon = badge_icon
        self.confetti.clear()
        self._bg_alpha = 0
        self._badge_scale = 0.0
        self.show()

        # Move Cyto to bottom corner
        self.cyto.move(self.width() - 250, self.height() - 350)
        self.cyto.show()
        self.cyto.play_animation("cheering")
        self.cyto.speak(f"You earned the {badge_name} badge!!")

        # Burst confetti
        cx = self.width() / 2
        cy = self.height() / 2
        for _ in range(200):
            self.confetti.append(Confetti(cx, cy))

        self.timer.start(16)

        # Phase 1: Fade in BG
        self.bg_anim = QPropertyAnimation(self, b"bg_alpha")
        self.bg_anim.setDuration(500)
        self.bg_anim.setStartValue(0)
        self.bg_anim.setEndValue(220)
        self.bg_anim.start()

        # Phase 2: Pop Badge
        self.badge_anim = QPropertyAnimation(self, b"badge_scale")
        self.badge_anim.setDuration(800)
        self.badge_anim.setStartValue(0.0)
        self.badge_anim.setEndValue(1.0)
        # Bouncy curve
        self.badge_anim.setEasingCurve(self.badge_anim.EasingCurve.Type.OutElastic)
        self.badge_anim.start()

        # Auto-close after 5 seconds
        QTimer.singleShot(6000, self.finish_sequence)

    def finish_sequence(self):
        self.timer.stop()
        self.hide()
        self.cyto.hide()
        self.animation_finished.emit()

    def animate_frame(self):
        """Advance the confetti animation by one frame and refresh the overlay."""
        alive = []
        for c in self.confetti:
            if c.update():
                alive.append(c)
        self.confetti = alive
        self.update()

    def mousePressEvent(self, event):  # noqa: ARG002, N802
        # Click to dismiss early
        """
        Dismisses the award overlay when it has reached sufficient opacity.

        Parameters:
                event: The mouse press event.
        """
        if self._bg_alpha > 100:
            self.finish_sequence()

    @Property(int)
    def bg_alpha(self):
        return self._bg_alpha

    @bg_alpha.setter
    def bg_alpha(self, value):
        self._bg_alpha = value
        self.update()

    @Property(float)
    def badge_scale(self):
        return self._badge_scale

    @badge_scale.setter
    def badge_scale(self, value):
        """Set the badge display scale and refresh the overlay."""
        self._badge_scale = value
        self.update()

    def paintEvent(self, event):  # noqa: ARG002, N802
        """
        Render the dimmed award overlay, confetti, and animated badge artwork.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark dimming background
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._bg_alpha))

        # Confetti
        for c in self.confetti:
            painter.translate(c.x, c.y)
            painter.rotate(c.angle)
            painter.fillRect(
                QRect(-int(c.size / 2), -int(c.size / 2), int(c.size), int(c.size)), c.color
            )
            painter.rotate(-c.angle)
            painter.translate(-c.x, -c.y)

        if self._badge_scale > 0:
            cx = self.width() / 2
            cy = self.height() / 2

            painter.translate(cx, cy)
            painter.scale(self._badge_scale, self._badge_scale)

            # Glow behind badge
            glow = QRadialGradient(0, 0, 150)
            glow.setColorAt(0, QColor(210, 153, 34, 150))
            glow.setColorAt(1, QColor(210, 153, 34, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse((-150), (-150), 300, 300)

            # Badge Background (Hexagon)
            painter.setBrush(QBrush(QColor("#0d1117")))
            painter.setPen(QPen(QColor("#d29922"), 4))

            # Draw hexagon
            points = []
            from PySide6.QtCore import QPointF

            for i in range(6):
                angle = i * math.pi / 3 - math.pi / 2
                points.append(QPointF(math.cos(angle) * 100, math.sin(angle) * 100))
            painter.drawPolygon(*points)

            # Badge Icon
            painter.setPen(QColor("#ffffff"))
            font = QFont("Arial", 48)
            painter.setFont(font)
            fm = painter.fontMetrics()
            painter.drawText(
                -fm.horizontalAdvance(self.badge_icon) // 2, fm.height() // 3, self.badge_icon
            )

            # Badge Text
            painter.setPen(QColor("#c9d1d9"))
            font = QFont("Arial", 24, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            painter.drawText(-fm.horizontalAdvance(self.badge_name) // 2, 160, self.badge_name)

            # "BADGE EARNED!" Text
            painter.setPen(QColor("#d29922"))
            font = QFont("Arial", 16, QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
            painter.setFont(font)
            fm = painter.fontMetrics()
            painter.drawText(-fm.horizontalAdvance("BADGE EARNED") // 2, -130, "BADGE EARNED")

            painter.scale(1 / self._badge_scale, 1 / self._badge_scale)
            painter.translate(-cx, -cy)
