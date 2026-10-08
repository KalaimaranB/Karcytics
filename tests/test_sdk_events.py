from karcytics_sdk.plugin import CentralEventBus
from PySide6.QtCore import QCoreApplication, QObject


class MockSubscriber(QObject):
    def __init__(self):
        super().__init__()
        self.received_data = None

    def handle_event(self, data):
        self.received_data = data


def test_event_bus_singleton():
    bus1 = CentralEventBus._get_bus()
    bus2 = CentralEventBus._get_bus()
    assert bus1 is bus2


def test_event_bus_publish_subscribe(qapp):
    # qapp fixture is usually provided by pytest-qt
    subscriber = MockSubscriber()

    CentralEventBus.subscribe("test_topic", subscriber.handle_event)
    CentralEventBus.publish("test_topic", {"key": "value"})

    # Process events since it's asynchronous
    QCoreApplication.processEvents()

    assert subscriber.received_data == {"key": "value"}
