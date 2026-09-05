import logging

from karcytics.core.diagnostics import BlackBoxHandler, DiagnosticEngine
from karcytics.core.event_bus import KarcyticsEvent, event_bus


def test_black_box_capacity():
    handler = BlackBoxHandler(capacity=5)
    logger = logging.getLogger("test_bb")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    for i in range(10):
        logger.info(f"Message {i}")

    history = handler.get_history()
    assert len(history) == 5
    assert history[-1]["message"] == "Message 9"
    assert history[0]["message"] == "Message 5"


def test_diagnostic_engine_singleton():
    d1 = DiagnosticEngine()
    d2 = DiagnosticEngine()
    assert d1 is d2


def test_error_reporting(qtbot):
    engine = DiagnosticEngine()

    received_data = []

    def on_error(data):
        received_data.append(data)

    event_bus.subscribe(KarcyticsEvent.ERROR_OCCURRED, on_error)

    try:
        raise ValueError("Test Error")
    except ValueError as e:
        engine.report_error("Test failure message", exception=e, plugin_id="test_plugin")

    assert len(received_data) == 1
    data = received_data[0]
    assert data["message"] == "Test failure message"
    assert "Test Error" in data["exception"]
    assert data["plugin_id"] == "test_plugin"
    assert "traceback" in data
    assert len(data["history"]) > 0


def test_error_reporting_with_remote_exception_and_traceback(qtbot):
    """An isolated plugin has no live exception object to hand over — its
    error crosses an RPC/event boundary as already-formatted strings (see
    core_services_bootstrap.py's diagnostics.report_error handler and
    plugins/loader.py's diagnostics_error event forwarding). Both must
    survive into the broadcast error_data exactly like the live-exception
    path does.
    """
    engine = DiagnosticEngine()

    received_data = []
    event_bus.subscribe(KarcyticsEvent.ERROR_OCCURRED, received_data.append)

    try:
        engine.report_error(
            "Remote failure message",
            plugin_id="flow_cytometry",
            exception_repr="ValueError: nope",
            traceback_str="Traceback (most recent call last):\n...",
        )

        assert len(received_data) == 1
        data = received_data[0]
        assert data["message"] == "Remote failure message"
        assert data["exception"] == "ValueError: nope"
        assert data["traceback"] == "Traceback (most recent call last):\n..."
        assert data["plugin_id"] == "flow_cytometry"
    finally:
        event_bus.unsubscribe(KarcyticsEvent.ERROR_OCCURRED, received_data.append)


from typing import Any, Final

_LISTENER_FAILURE_WAIT_MS: Final[int] = 50


def test_listener_exception_does_not_trigger_recursive_reporting(qtbot: Any) -> None:
    """Regression test for a real production incident: a broken `ERROR_OCCURRED`
    listener (a `setFont()` type mismatch in the error dialog) caused infinite
    recursion — `report_error` -> `event_bus.emit` -> `_dispatch` -> listener
    raises -> `event_bus.py`'s `logger.error(..., exc_info=True)` ->
    `AutoReportHandler` -> `report_error` -> `event_bus.emit` -> ... — until the
    Python recursion limit was hit. `AutoReportHandler` must ignore event_bus's
    own listener-failure logs so a broken listener can't re-trigger itself.
    """
    engine = DiagnosticEngine()

    call_count = {"n": 0}

    def broken_listener(_data: Any) -> None:
        call_count["n"] += 1
        raise TypeError("simulated setFont() failure")

    event_bus.subscribe(KarcyticsEvent.ERROR_OCCURRED, broken_listener)
    try:
        engine.report_error("trigger", plugin_id="test_plugin")
        qtbot.wait(_LISTENER_FAILURE_WAIT_MS)
    finally:
        event_bus.unsubscribe(KarcyticsEvent.ERROR_OCCURRED, broken_listener)

    # Without the fix this listener is invoked recursively (>1, until the
    # recursion limit). With the fix, exactly once — its own failure never
    # gets reported as a new application error.
    assert call_count["n"] == 1


def test_black_box_formatting():
    handler = BlackBoxHandler(capacity=1)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    record = logging.LogRecord("test", logging.INFO, "path", 10, "Formatted message", None, None)
    handler.emit(record)

    history = handler.get_history()
    assert history[0]["message"] == "INFO - Formatted message"
