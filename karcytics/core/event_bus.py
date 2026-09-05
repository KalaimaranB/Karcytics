"""Karcytics Event Bus (The Nervous System).

Provides a global, thread-safe EventManager for decoupled communication
between core components and UI. Built on PyQt6 signals.
"""

import logging
from collections.abc import Callable
from enum import Enum, auto
from typing import Any, TypedDict

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ErrorEventPayload(TypedDict):
    """Strict payload type for ERROR_OCCURRED events."""

    title: str
    message: str


class KarcyticsEvent(Enum):
    """Enumeration of all system-wide events."""

    # Plugin Lifecycle
    PLUGIN_INSTALLED = auto()  # args: (plugin_id: str)
    PLUGIN_REMOVED = auto()  # args: (plugin_id: str)
    PLUGIN_UPDATED = auto()  # args: (plugin_id: str)

    # Project Lifecycle
    PROJECT_LOADED = auto()  # args: (project_path: str)
    PROJECT_CLOSED = auto()  # args: ()

    # System Events
    THEME_CHANGED = auto()  # args: (theme_name: str)
    ERROR_OCCURRED = auto()  # args: (error_data: dict)
    SYSTEM_WARNING = auto()  # args: (message: str)
    CORE_UPDATE_AVAILABLE = auto()  # args: (remote_version: str, download_url: str)

    # Academy & Tutorial Engine
    ACADEMY_STEP_CHANGED = auto()  # args: (step: BaseStep)
    ACADEMY_COURSE_COMPLETED = auto()  # args: (course_id: str, badge_reward: str)
    ACADEMY_SUBTASK_COMPLETED = auto()  # args: (subtask_id: str, remaining_count: int)
    ACADEMY_CHECKPOINT_SAVED = auto()  # args: (course_id: str, checkpoint_path: str)
    ACADEMY_COURSE_PREPARE_PROJECT = auto()  # args: (course_id: str)

    # User action events (used by WaitForEventStep in the tutorial engine)
    STORE_OPENED = auto()  # args: () — Marketplace dialog was opened
    STORE_CLOSED = auto()  # args: () — Marketplace dialog was closed
    STORE_MODULE_DETAILS_OPENED = auto()  # args: () - Store module details dialog opened
    STORE_MODULE_DETAILS_CLOSED = auto()  # args: () - Store module details dialog closed
    MODULE_OPENED = auto()  # args: (module_id: str) — analysis panel loaded
    FILE_IMPORTED = auto()  # args: (file_path: str) — a file was imported into a module
    WORKFLOW_SAVED = auto()  # args: (filename: str) — a workflow was saved
    PREFERENCES_OPENED = auto()  # args: () — Preferences dialog was opened
    PREFERENCES_CLOSED = auto()  # args: () — Preferences dialog was closed


class EventManager(QObject):
    """Central event coordinator.

    Use the global 'event_bus' instance for most operations.
    """

    # Internal signal used to route all events through the Qt event loop
    _internal_bus = pyqtSignal(KarcyticsEvent, tuple, dict)

    def __init__(self) -> None:
        """Initialize the event manager and connect its internal event bus to dispatch events."""
        super().__init__()
        self._listeners: dict[KarcyticsEvent, list[Callable[..., Any]]] = {}
        self._internal_bus.connect(self._dispatch)

    def subscribe(self, event_type: KarcyticsEvent, callback: Callable[..., Any]) -> None:
        """Register a callback for a specific event.

        Args:
            event_type (KarcyticsEvent): The type of event to listen for.
            callback (callable): The function to call when the event occurs.
                                Must accept the arguments emitted by the event.
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []

        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type.name}: {callback}")

    def unsubscribe(self, event_type: KarcyticsEvent, callback: Callable[..., Any]) -> None:
        """Unregister a callback.

        Args:
            event_type (KarcyticsEvent): The type of event to unsubscribe from.
            callback (callable): The previously registered function to remove.
        """
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)
            logger.debug(f"Unsubscribed from {event_type.name}: {callback}")

    def emit(self, event_type: KarcyticsEvent, *args: Any, **kwargs: Any) -> None:
        """Broadcast an event to all subscribers.

        Safe to call from any thread. Payloads are automatically routed
        to the main UI thread for thread-safe processing.

        Args:
            event_type (KarcyticsEvent): The event to broadcast.
            *args: Positional arguments to pass to listeners.
            **kwargs: Keyword arguments to pass to listeners.
        """
        # We use the internal signal to ensure that if this is called from a
        # background thread, it gets queued and dispatched on the thread
        # where the EventManager lives (typically the Main UI Thread).
        self._internal_bus.emit(event_type, args, kwargs)

    def _dispatch(
        self, event_type: KarcyticsEvent, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> None:
        """Invoke all listeners for the given event."""
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in listener for {event_type.name}: {e}", exc_info=True)


# Internal singleton instance
_event_bus_instance = None


def get_event_bus() -> EventManager:
    """Get the global application event bus (Nervous System)."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventManager()
    return _event_bus_instance


# For backward compatibility and convenience
# Note: This will still trigger instantiation if imported directly,
# but we can now use get_event_bus() in sensitive areas.
event_bus = get_event_bus()
