"""Tests for the Karcytics Event Bus (The Nervous System)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QThread

from karcytics.core.event_bus import EventManager, KarcyticsEvent


class TestEventBus:
    @pytest.fixture
    def bus(self, qtbot):
        """Dedicated EventManager instance for testing."""
        manager = EventManager()
        return manager  # noqa: RET504

    def test_emit_receive(self, bus):
        """Verify basic publish/subscribe functionality."""
        callback = MagicMock()
        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, callback)

        bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, "test_plugin")

        # We need to process events because dispatch happens via internal signal
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        callback.assert_called_once_with("test_plugin")

    def test_multiple_listeners(self, bus):
        """Verify multiple subscribers can listen to the same event."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, cb1)
        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, cb2)

        bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, "shared_msg")
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        cb1.assert_called_once_with("shared_msg")
        cb2.assert_called_once_with("shared_msg")

    def test_unsubscribe(self, bus):
        """Verify that listeners can be removed."""
        callback = MagicMock()
        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, callback)
        bus.unsubscribe(KarcyticsEvent.PLUGIN_INSTALLED, callback)

        bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, "gone")
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        callback.assert_not_called()

    def test_cross_thread_emit(self, bus, qtbot):
        """Ensure background threads can safely emit events to UI listeners."""
        received_data = []

        def listener(data):
            received_data.append(data)

        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, listener)

        # Define a worker thread that emits an event
        class Worker(QThread):
            def run(self):
                bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, "from_bg_thread")

        worker = Worker()
        worker.start()

        # Wait for the worker to finish and process events
        qtbot.waitUntil(lambda: len(received_data) > 0, timeout=2000)

        assert received_data[0] == "from_bg_thread"

    def test_error_resilience(self, bus):
        """Verify that one crashing listener doesn't stop the whole bus."""

        def buggy_listener(_):
            raise RuntimeError("Boom!")

        cb_healthy = MagicMock()

        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, buggy_listener)
        bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, cb_healthy)

        # Should not crash the emitter
        bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, "data")

        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        cb_healthy.assert_called_once()


def test_event_bus_first_built_off_the_gui_thread_lives_on_the_gui_thread(qapp, monkeypatch):
    """The async plugin loader can be the first to touch the bus. A bus owned
    by that short-lived thread would dispatch every event there, or not at all.
    """
    import threading

    from karcytics.core import event_bus as event_bus_module

    monkeypatch.setattr(event_bus_module, "_event_bus_instance", None)
    built = []
    thread = threading.Thread(target=lambda: built.append(event_bus_module.get_event_bus()))
    thread.start()
    thread.join()

    assert built[0].thread() is qapp.thread()
