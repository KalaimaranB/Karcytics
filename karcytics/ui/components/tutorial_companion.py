"""Floating tutorial companion — keeps Cyto above a dialog the tour opens.

A window's own `TutorialOverlay` is a child widget of that window, so any
separate dialog the tour sends the user into (Preferences, Plugin Details)
is its own top-level window and always stacks above it — Cyto and the step
text vanish behind the dialog mid-step. `TutorialCompanion` is the same
overlay class re-hosted as a frameless tool window parented to that dialog
instead: the window manager keeps a tool window above its parent, it closes
with it, and as a child of a modal dialog it is not input-blocked by it.
"""

import weakref
from collections.abc import Callable

from karcytics_sdk.plugin.tutorial_models import BaseStep
from karcytics_sdk.plugin.tutorial_overlay import TutorialOverlay
from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QPaintEvent, QRegion
from PySide6.QtWidgets import QApplication, QDialog

from karcytics.core.tutorial_manager import global_tutorial_manager, hub_academy_event_bus

# Mirrors TutorialOverlay's compact (Cyto + bubble side by side) layout: the
# bubble starts 240px into Cyto's 300x400 widget and sits 30px lower.
_CYTO_BUBBLE_OFFSET = 240
_CYTO_HEIGHT = 400
_BUBBLE_DROP = 30
_MARGIN = 10
# Gap between the dialog's frame and the companion beside it.
_GAP = 12


class TutorialCompanion(TutorialOverlay):
    """Cyto and the step bubble, floating beside `host` above every Hub window.

    Never dims or spotlights anything — the dialog itself is the focus — so
    it is painted see-through and only Cyto and the bubble take clicks.
    """

    _live: "weakref.WeakSet[TutorialCompanion]" = weakref.WeakSet()

    def __init__(self, host: QDialog, on_skip: Callable[[], None]) -> None:
        super().__init__(global_tutorial_manager, hub_academy_event_bus, host, compact_mode=True)
        self._host = host
        self._made_room = False
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.hide()
        self.skip_requested.connect(on_skip)
        self.skip_requested.connect(self.hide)
        host.installEventFilter(self)
        TutorialCompanion._live.add(self)

    @classmethod
    def any_visible(cls) -> bool:
        """Whether some dialog's companion is currently showing Cyto."""
        return any(c._is_alive() and c.isVisible() for c in list(cls._live))

    def render_step(self, step: BaseStep | None) -> None:
        # Step changes keep arriving over the event bus after the dialog
        # closes (closing Preferences is itself what advances step 6) —
        # never resurface once the host is gone.
        if not self._is_alive():
            return
        if not self._host.isVisible():
            self.hide()
            return
        super().render_step(step)
        if self.isVisible() and self.bubble_container.isVisible():
            self._fit_to_content()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._host and self._is_alive():
            kind = event.type()
            if kind == QEvent.Type.Show:
                self.render_step(global_tutorial_manager.current_step)
            elif kind in (QEvent.Type.Move, QEvent.Type.Resize):
                if self.isVisible():
                    self._place_beside_host()
            elif kind in (QEvent.Type.Hide, QEvent.Type.Close):
                self.hide()
        return super().eventFilter(watched, event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802, ARG002
        """Nothing to paint — Cyto and the bubble draw themselves."""

    def _update_mask_impl(self) -> None:
        # Only Cyto and the bubble block clicks; the rest of the window is
        # see-through and must not swallow clicks meant for what's below.
        mask = QRegion()
        for widget in (self.cyto, self.bubble_container):
            if widget.isVisible():
                mask = mask.united(QRegion(widget.geometry()))
        self.setMask(mask)

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _fit_to_content(self) -> None:
        """Sizes the window to the Cyto + bubble pair and re-lays them out."""
        bubble = self.bubble_container.sizeHint()
        if self._cyto_enabled():
            width = _CYTO_BUBBLE_OFFSET + bubble.width() + 2 * _MARGIN
            height = max(_CYTO_HEIGHT, bubble.height()) + _BUBBLE_DROP + 4 * _MARGIN
        else:
            width = bubble.width() + 2 * _MARGIN
            height = bubble.height() + 2 * _MARGIN
        self.resize(width, height)
        self._place_beside_host()
        self._reposition_cyto_and_bubble([])
        self._update_mask()

    def _place_beside_host(self) -> None:
        """Puts the companion just left (else right) of the dialog, on its screen.

        The first time, if neither side has room but the dialog and the
        companion would fit side by side, the dialog is moved over to make
        that room. Failing even that, the companion overlaps the screen's
        bottom-left corner — it can still be dragged out of the way.
        """
        screen = self._host.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        frame = self._host.frameGeometry()
        width, height = self.width(), self.height()

        left_x = frame.left() - _GAP - width
        right_x = frame.left() + frame.width() + _GAP
        fits_left = left_x >= avail.left()
        fits_right = right_x + width <= avail.left() + avail.width()

        if not (fits_left or fits_right) and not self._made_room:
            self._made_room = True
            total = width + _GAP + frame.width()
            if total <= avail.width():
                group_left = avail.left() + (avail.width() - total) // 2
                self._host.move(
                    self._host.pos() + QPoint(group_left + width + _GAP - frame.left(), 0)
                )
                frame = self._host.frameGeometry()
                left_x = frame.left() - _GAP - width
                fits_left = left_x >= avail.left()

        if fits_left:
            x = left_x
        elif fits_right:
            x = right_x
        else:
            self.move(avail.left(), avail.top() + avail.height() - height)
            return
        y = frame.top() + (frame.height() - height) // 2
        y = max(avail.top(), min(y, avail.top() + avail.height() - height))
        self.move(x, y)


def attach_tutorial_companion(
    host: QDialog, on_skip: Callable[[], None]
) -> TutorialCompanion | None:
    """Gives `host` a floating Cyto while a tour is running; None otherwise.

    Call before `host` is shown — the companion renders the live step on
    the dialog's Show event and follows it from then on.
    """
    if global_tutorial_manager.active_course is None:
        return None
    return TutorialCompanion(host, on_skip)


_deferring: "weakref.WeakSet[TutorialOverlay]" = weakref.WeakSet()


def defer_to_companion(overlay: TutorialOverlay) -> bool:
    """Hides `overlay`'s own Cyto and bubble while a companion shows them.

    Otherwise the window's overlay keeps a second Cyto behind the dialog,
    visible as soon as the dialog is dragged aside. Returns True while
    deferring — callers skip their own spotlight update then. On the first
    call after the companion goes away, re-renders the live step so the
    overlay's own Cyto comes back even without a step change.
    """
    if TutorialCompanion.any_visible():
        # set_targets() re-lays out (and re-shows) Cyto, so hide after it.
        overlay.set_targets([])
        overlay.cyto.hide()
        overlay.bubble_container.hide()
        _deferring.add(overlay)
        return True
    if overlay in _deferring:
        _deferring.discard(overlay)
        overlay.render_step(global_tutorial_manager.current_step)
    return False
