"""Tests for the floating tutorial companion that keeps Cyto above tour dialogs."""

import pytest
from karcytics_sdk.plugin.tutorial_overlay import TutorialOverlay
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QDialog, QWidget

from karcytics.core.tutorial_manager import global_tutorial_manager, hub_academy_event_bus
from karcytics.tutorials.core_intro import core_intro_course
from karcytics.ui.components.tutorial_companion import (
    TutorialCompanion,
    attach_tutorial_companion,
    defer_to_companion,
)


def _step(step_id: str):
    return next(s for s in core_intro_course.steps if s.id == step_id)


@pytest.fixture
def tour(monkeypatch):
    """Puts the core tour on the Preferences step without touching saved progress."""
    monkeypatch.setattr(global_tutorial_manager, "active_course", core_intro_course)
    monkeypatch.setattr(global_tutorial_manager, "current_step", _step("hub_about_appearance"))


@pytest.fixture
def host(qtbot):
    dialog = QDialog()
    dialog.resize(400, 300)
    qtbot.addWidget(dialog)
    return dialog


def test_hub_open_preferences_step_locks_the_hub():
    # The menu bar sits outside the Hub overlay, so a non-interactive step
    # dims and blocks every other click while leaving the menu reachable.
    assert _step("hub_open_preferences").allow_interaction is False


def test_attach_does_nothing_without_an_active_tour(monkeypatch, host):
    monkeypatch.setattr(global_tutorial_manager, "active_course", None)
    assert attach_tutorial_companion(host, lambda: None) is None


@pytest.mark.usefixtures("tour")
def test_companion_is_a_tool_window_owned_by_the_dialog(host):
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    assert companion.isWindow()
    assert companion.windowFlags() & Qt.WindowType.Tool
    assert companion.parentWidget() is host
    assert not companion.isVisible()


@pytest.mark.usefixtures("tour")
def test_companion_shows_with_dialog_and_hides_with_it(qtbot, host):
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)
    assert companion.cyto.isVisible()
    assert companion.bubble_container.isVisible()
    assert "Appearance" in companion.text_label.text()
    assert TutorialCompanion.any_visible()

    host.hide()
    assert not companion.isVisible()
    assert not TutorialCompanion.any_visible()


@pytest.mark.usefixtures("tour")
def test_companion_stays_hidden_on_step_change_after_dialog_closes(qtbot, host):
    # Closing Preferences is what advances the tour to its next step, so a
    # step change can arrive just after the dialog is gone.
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)
    host.hide()

    companion.render_step(_step("hub_orientation"))
    assert not companion.isVisible()


class _FakeScreen:
    def __init__(self, rect: QRect) -> None:
        self._rect = rect

    def availableGeometry(self) -> QRect:  # noqa: N802
        return self._rect


@pytest.mark.usefixtures("tour")
def test_companion_sits_left_of_the_dialog_when_there_is_room(qtbot, monkeypatch, host):
    monkeypatch.setattr(host, "screen", lambda: _FakeScreen(QRect(0, 0, 2400, 1400)))
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.move(1200, 400)
    host.show()
    qtbot.waitUntil(companion.isVisible)

    frame = host.frameGeometry()
    assert companion.geometry().right() < frame.left()
    assert not companion.geometry().intersects(frame)


@pytest.mark.usefixtures("tour")
def test_companion_moves_a_centred_dialog_aside_to_make_room(qtbot, monkeypatch, host):
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)
    # Just wide enough for the pair side by side, but not with the dialog
    # centred — neither side alone has room.
    width = companion.width() + host.frameGeometry().width() + 40
    monkeypatch.setattr(host, "screen", lambda: _FakeScreen(QRect(0, 0, width, 1400)))
    host.move((width - host.frameGeometry().width()) // 2, 300)
    companion._made_room = False
    centred_left = host.frameGeometry().left()
    companion._place_beside_host()

    frame = host.frameGeometry()
    assert frame.left() > centred_left
    assert companion.geometry().left() >= 0
    assert companion.geometry().right() < frame.left()


@pytest.mark.usefixtures("tour")
def test_companion_mask_only_covers_cyto_and_bubble(qtbot, host):
    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)

    mask = companion.mask()
    assert mask.contains(companion.bubble_container.geometry().center())
    assert mask.contains(companion.cyto.geometry().center())
    # The empty top-right corner is see-through: clicks there pass below.
    assert not mask.contains(QPoint(companion.width() - 2, 2))


@pytest.mark.usefixtures("tour")
def test_skip_from_companion_hides_it_and_calls_host_skip(qtbot, host):
    skipped = []
    companion = attach_tutorial_companion(host, lambda: skipped.append(True))
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)

    companion.skip_requested.emit()
    assert skipped == [True]
    assert not companion.isVisible()


@pytest.mark.usefixtures("tour")
def test_window_overlay_defers_to_companion_then_comes_back(qtbot, host):
    window = QWidget()
    window.resize(900, 700)
    qtbot.addWidget(window)
    overlay = TutorialOverlay(global_tutorial_manager, hub_academy_event_bus, window)
    overlay.setGeometry(window.rect())
    window.show()
    overlay.render_step(global_tutorial_manager.current_step)
    assert overlay.cyto.isVisible()

    companion = attach_tutorial_companion(host, lambda: None)
    assert companion is not None
    host.show()
    qtbot.waitUntil(companion.isVisible)

    assert defer_to_companion(overlay) is True
    assert not overlay.cyto.isVisible()
    assert not overlay.bubble_container.isVisible()

    host.hide()
    assert defer_to_companion(overlay) is False
    assert overlay.cyto.isVisible()
    assert overlay.bubble_container.isVisible()
