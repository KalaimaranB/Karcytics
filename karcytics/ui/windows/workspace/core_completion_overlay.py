import math
import random

from karcytics_sdk.plugin.effects import apply_glow_effect
from karcytics_sdk.plugin.theme_fallback import Colors
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

# Animation and Layout Constants
NODE_COUNT = 50
NODE_MIN_VELOCITY = -0.0015
NODE_MAX_VELOCITY = 0.0015
ANIMATION_TIMER_MS = 40
CARD_WIDTH = 650
CARD_HEIGHT = 480
TITLE_FONT_SIZE = 28
MESSAGE_FONT_SIZE = 14
CERT_FONT_SIZE = 12
BADGE_FONT_SIZE = 20
BUTTON_FONT_SIZE = 14
NODE_CONNECTION_DIST_SQ = 10000

# Color Constants
CARD_BG_COLOR = "#11151c"
CARD_BORDER_COLOR = "#2a3545"
MESSAGE_TEXT_COLOR = "#CCCCCC"
CERT_TEXT_COLOR = "#888888"
OVERLAY_BG_COLOR = (10, 12, 16, 235)


class CoreCourseCompleteOverlay(QWidget):
    """A premium, tailored completion screen for the core Karcytics onboarding."""

    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        # Background nodes for tech effect
        self._nodes = []
        for _ in range(NODE_COUNT):
            self._nodes.append(
                {
                    "x": random.uniform(0, 1),
                    "y": random.uniform(0, 1),
                    "vx": random.uniform(NODE_MIN_VELOCITY, NODE_MAX_VELOCITY),
                    "vy": random.uniform(NODE_MIN_VELOCITY, NODE_MAX_VELOCITY),
                }
            )

        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._update_bg)
        self._bg_timer.setInterval(ANIMATION_TIMER_MS)

        self._setup_ui()

    def show_completion(self, _: str, badge_reward: str) -> None:
        """Shows the completion screen."""
        self._badge_label.setText(badge_reward)
        self.show()
        self._bg_timer.start()

    def _setup_ui(self) -> None:
        # Full screen layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Central card
        self._card = QFrame()
        self._card.setObjectName("CoreCompleteCard")
        self._card.setStyleSheet(
            f"QFrame#CoreCompleteCard {{ background-color: {CARD_BG_COLOR}; border: 1px solid {CARD_BORDER_COLOR}; border-radius: 12px; }}"
        )

        # Add a prominent glow effect
        apply_glow_effect(self._card, QColor(Colors.ACCENT_PRIMARY).darker(150), blur_radius=80)

        self._card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(50, 50, 50, 50)
        card_layout.setSpacing(20)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Huge Title
        title = QLabel("WELCOME TO KARCYTICS")
        title.setObjectName("CoreCompleteTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = title.font()
        font.setPointSize(TITLE_FONT_SIZE)
        font.setBold(True)
        title.setFont(font)
        title.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY};")

        card_layout.addWidget(title)

        # Subtitle / Message
        self._message_label = QLabel("Congrats on completing the onboarding course!")
        self._message_label.setObjectName("CoreCompleteMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_font = self._message_label.font()
        msg_font.setPointSize(MESSAGE_FONT_SIZE)
        self._message_label.setFont(msg_font)
        self._message_label.setStyleSheet(f"color: {MESSAGE_TEXT_COLOR};")

        card_layout.addWidget(self._message_label)
        card_layout.addSpacing(20)

        # Badge display container
        badge_layout = QVBoxLayout()
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.setSpacing(10)

        cert_label = QLabel("ACHIEVEMENT UNLOCKED")
        cert_label.setObjectName("CoreCompleteCertLabel")
        cert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cert_font = cert_label.font()
        cert_font.setPointSize(CERT_FONT_SIZE)
        cert_font.setBold(True)
        cert_label.setFont(cert_font)
        cert_label.setStyleSheet(f"color: {CERT_TEXT_COLOR}; letter-spacing: 2px;")

        self._badge_label = QLabel("Badge Name")
        self._badge_label.setObjectName("CoreCompleteBadgeLabel")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_font = self._badge_label.font()
        badge_font.setPointSize(BADGE_FONT_SIZE)
        badge_font.setBold(True)
        self._badge_label.setFont(badge_font)
        self._badge_label.setStyleSheet(f"color: {Colors.DNA_SECONDARY};")

        badge_layout.addWidget(cert_label)
        badge_layout.addWidget(self._badge_label)

        card_layout.addLayout(badge_layout)

        card_layout.addStretch()

        # Continue Button
        self._continue_btn = QPushButton("START EXPLORING")
        self._continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_btn.setObjectName("CoreCompleteBtn")
        self._continue_btn.setMinimumHeight(50)

        btn_font = self._continue_btn.font()
        btn_font.setPointSize(BUTTON_FONT_SIZE)
        btn_font.setBold(True)
        self._continue_btn.setFont(btn_font)
        self._continue_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ACCENT_PRIMARY}; color: white; border-radius: 8px; border: none; }}"
            f"QPushButton:hover {{ background-color: {Colors.DNA_SECONDARY}; }}"
        )

        self._continue_btn.clicked.connect(self._on_continue)
        card_layout.addWidget(self._continue_btn)

        main_layout.addWidget(self._card)

    def _update_bg(self) -> None:
        """Update the animated background node positions and schedule the overlay for repainting."""
        for n in self._nodes:
            n["x"] += n["vx"]
            n["y"] += n["vy"]
            if n["x"] < 0 or n["x"] > 1:
                n["vx"] *= -1
            if n["y"] < 0 or n["y"] > 1:
                n["vy"] *= -1
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base overlay (darker than usual)
        painter.fillRect(self.rect(), QColor(*OVERLAY_BG_COLOR))

        w, h = self.width(), self.height()
        base_color = QColor(Colors.ACCENT_PRIMARY)

        # Draw tech nodes
        painter.setPen(Qt.PenStyle.NoPen)
        for n in self._nodes:
            nx = int(n["x"] * w)
            ny = int(n["y"] * h)
            # Twinkle effect based on position
            alpha = int((math.sin(n["x"] * 10 + n["y"] * 10) + 1) * 60 + 20)
            painter.setBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), alpha))
            painter.drawEllipse(nx - 2, ny - 2, 4, 4)

        # Draw connecting lines for nodes that are close
        painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 30), 1))
        for i in range(len(self._nodes)):
            n1 = self._nodes[i]
            x1, y1 = n1["x"] * w, n1["y"] * h
            for j in range(i + 1, len(self._nodes)):
                n2 = self._nodes[j]
                x2, y2 = n2["x"] * w, n2["y"] * h
                dist_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
                if dist_sq < NODE_CONNECTION_DIST_SQ:  # ~100px radius
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _on_continue(self) -> None:
        self._bg_timer.stop()
        # Defer hide and emit to prevent click fall-through to underlying widgets
        QTimer.singleShot(0, self._hide_and_emit)

    def _hide_and_emit(self) -> None:
        self.hide()
        self.dismissed.emit()
