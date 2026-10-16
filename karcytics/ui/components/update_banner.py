"""Update notification banner widget for Karcytics.

Single Responsibility: renders an ambient, non-blocking strip at the top of the
Hub window when a core app update is available. All logic lives in UpdateChecker.

Subscribes to KarcyticsEvent.CORE_UPDATE_AVAILABLE on construction and tears down
cleanly when the widget is destroyed (no dangling event bus references).
"""

import logging
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from karcytics.core.event_bus import KarcyticsEvent, get_event_bus
from karcytics.ui.theme import Colors, theme_manager

logger = logging.getLogger(__name__)

_BANNER_STYLE = """
    QWidget#UpdateBanner {{
        background-color: {bg};
        border-bottom: 1px solid {border};
    }}
"""

_LABEL_STYLE = "color: {fg}; font-size: 13px; font-weight: 500; background: transparent;"

_BTN_DOWNLOAD_STYLE = """
    QPushButton {{
        background-color: {accent};
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {accent_hover};
    }}
"""

_BTN_SECONDARY_STYLE = """
    QPushButton {{
        background-color: transparent;
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {bg_hover};
    }}
"""

_BTN_CLOSE_STYLE = """
    QPushButton {{
        background: transparent;
        color: {fg};
        border: none;
        padding: 2px 6px;
        font-size: 16px;
    }}
    QPushButton:hover {{
        color: {danger};
    }}
"""


class UpdateBannerWidget(QWidget):
    """Dismissible amber banner that appears when a Karcytics core update is available.

    Design:
    - SRP: Only owns the visual representation — no network calls, no config I/O.
    - OCP: Subscribes to the event bus; adding new update sources doesn't require
      changing this widget.
    - Starts hidden. Shown only when CORE_UPDATE_AVAILABLE fires.
    - The × button hides without skipping (banner re-appears next launch).
    - "Skip This Version" hides AND persists the skip via update_checker.
    - "Download Now" opens the GitHub releases page in the system browser.
    """

    def __init__(self, update_checker, parent: QWidget | None = None):
        super().__init__(parent)
        self._update_checker = update_checker
        self._remote_version: str = ""
        self._download_url: str = ""
        self._notes: str = ""

        self.setObjectName("UpdateBanner")
        self._build_ui()
        self._apply_styles()

        # Subscribe to the event bus
        self._bus = get_event_bus()
        self._bus.subscribe(KarcyticsEvent.CORE_UPDATE_AVAILABLE, self._on_update_available)

        # Start hidden — shown only when the event fires
        self.hide()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 8, 6)
        layout.setSpacing(10)

        # Update icon + label (left-anchored)
        self.lbl_message = QLabel()
        self.lbl_message.setObjectName("BannerLabel")
        layout.addWidget(self.lbl_message, stretch=1)

        # "Download Now" CTA
        self.btn_download = QPushButton("⬇  Download Now")
        self.btn_download.setObjectName("BannerDownload")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._on_download)
        layout.addWidget(self.btn_download)

        # "Skip This Version" secondary action
        self.btn_skip = QPushButton("Skip This Version")
        self.btn_skip.setObjectName("BannerSkip")
        self.btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip.clicked.connect(self._on_skip)
        layout.addWidget(self.btn_skip)

        # × close button (hide only, no skip)
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("BannerClose")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        layout.addWidget(self.btn_close)

        self.setFixedHeight(44)

    def _apply_styles(self) -> None:
        theme_manager.apply_style(
            self,
            _BANNER_STYLE.format(
                bg=Colors.ACCENT_WARNING + "22",  # amber at 13% opacity
                border=Colors.ACCENT_WARNING + "55",
            ),
        )
        theme_manager.apply_style(self.lbl_message, _LABEL_STYLE.format(fg=Colors.FG_PRIMARY))
        theme_manager.apply_style(
            self.btn_download,
            _BTN_DOWNLOAD_STYLE.format(
                accent=Colors.ACCENT_WARNING,
                accent_hover=Colors.ACCENT_WARNING + "cc",
            ),
        )
        theme_manager.apply_style(
            self.btn_skip,
            _BTN_SECONDARY_STYLE.format(
                fg=Colors.FG_SECONDARY,
                border=Colors.BORDER,
                bg_hover=Colors.BG_MEDIUM,
            ),
        )
        theme_manager.apply_style(
            self.btn_close,
            _BTN_CLOSE_STYLE.format(
                fg=Colors.FG_SECONDARY,
                danger=Colors.ACCENT_DANGER,
            ),
        )

    # ── Event Handlers ────────────────────────────────────────────────────────

    def _on_update_available(self, remote_version: str, download_url: str, notes: str = "") -> None:
        """Called from the event bus when a core update is detected."""
        self._remote_version = remote_version
        self._download_url = download_url
        self._notes = notes

        from karcytics import __version__ as current_version

        self.lbl_message.setText(
            f"🎉  Karcytics v{remote_version} is available  —  you have v{current_version}"
        )
        self.lbl_message.setToolTip(notes)
        self.show()
        logger.info(f"Update banner shown for v{remote_version}")

    def _on_download(self) -> None:
        if self._download_url:
            webbrowser.open(self._download_url)
        self.hide()

    def _on_skip(self) -> None:
        if self._remote_version:
            self._update_checker.skip_version(self._remote_version)
        self.hide()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Unsubscribe from event bus to prevent dangling listeners."""
        self._bus.unsubscribe(KarcyticsEvent.CORE_UPDATE_AVAILABLE, self._on_update_available)
        super().closeEvent(event)
