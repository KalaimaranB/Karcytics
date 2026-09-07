"""Tests for tutorial plugin handoff and WaitForEventStep progression logic."""

import pytest
from karcytics_sdk.plugin.tutorial_models import Course, InfoStep, WaitForEventStep
from PyQt6.QtWidgets import QApplication

from karcytics.core.tutorial_manager import HubAcademyManager, _HubAcademyEventBus


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    import typing

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return typing.cast(QApplication, app)


def test_wait_for_event_step_blocks_next(tmp_path, qapp) -> None:
    """Verify that a WaitForEventStep ignores manual next_step() calls but advances on the event."""
    # Create a fresh HubAcademyManager with its event bus adapter
    event_bus_adapter = _HubAcademyEventBus()
    academy_manager = HubAcademyManager(
        event_bus=event_bus_adapter, persistence_dir=tmp_path / "academy"
    )

    test_course = Course(
        id="test_handoff_course",
        title="Test Handoff",
        steps=[
            InfoStep(id="step1", text="Step 1", next_step_id="wait_step"),
            WaitForEventStep(
                id="wait_step",
                text="Waiting for plugin handoff",
                event_name="PLUGIN_HANDOFF_COMPLETE",
                next_step_id="final_step",
            ),
            InfoStep(id="final_step", text="Final Step"),
        ],
    )

    # Register and start the course
    academy_manager.register_storyboard("test", test_course)
    started = academy_manager.start_course_confirmed("test_handoff_course")
    assert started is True
    assert academy_manager.current_step is not None
    assert academy_manager.current_step.id == "step1"

    # Advance past step1 normally (it's an InfoStep, so next_step() works)
    academy_manager.next_step()
    assert academy_manager.current_step is not None
    assert academy_manager.current_step.id == "wait_step"

    # CRITICAL TEST: Manually calling next_step() on a WaitForEventStep should NOT advance it
    academy_manager.next_step()
    assert academy_manager.current_step is not None
    assert academy_manager.current_step.id == "wait_step", (
        "next_step() should be ignored while on a WaitForEventStep"
    )

    # Emitting the specified event should advance it automatically
    event_bus_adapter.emit("PLUGIN_HANDOFF_COMPLETE")
    assert academy_manager.current_step is not None
    assert academy_manager.current_step.id == "final_step", (
        "Emitting PLUGIN_HANDOFF_COMPLETE should automatically advance the wait step"
    )
