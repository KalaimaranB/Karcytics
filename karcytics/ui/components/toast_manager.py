"""Toast notifications for the Hub.

The toast widget itself (`ToastNotification`) and its stacking/positioning
logic (`ToastManager` as a plain, reusable class) now live in the SDK — see
`karcytics_sdk.plugin.toast` — so plugins can raise the exact same UI for
their own purposes (e.g. an update notice) without depending on the Hub's
event bus. This module keeps only what's genuinely Hub-specific: the
singleton wiring `KarcyticsEvent.SYSTEM_WARNING` to that shared toast UI.
"""

import logging

from karcytics_sdk.plugin.toast import STYLE_WARNING, ToastNotification  # noqa: F401 (re-exported)
from karcytics_sdk.plugin.toast import ToastManager as _SdkToastManager

from karcytics.core.event_bus import KarcyticsEvent, event_bus

logger = logging.getLogger(__name__)


class ToastManager:
    """Singleton that renders `SYSTEM_WARNING` events as toasts via the SDK's shared toast UI."""

    _instance = None

    def __new__(cls):
        """
        Create and return the shared instance of the manager.

        Returns:
            ToastManager: The singleton manager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the toast manager and subscribe it to system warning events.
        """
        if self._initialized:
            return

        self._sdk_manager = _SdkToastManager()
        event_bus.subscribe(KarcyticsEvent.SYSTEM_WARNING, self._on_system_warning)
        self._initialized = True
        logger.info("ToastManager initialized.")

    def _on_system_warning(
        self,
        message: str,
        icon: str | None = None,
        color: str | None = None,
        duration_ms: int = 4000,
    ):
        """Display a system warning as a bottom-right toast notification, stacking it above visible toasts."""
        default_icon, default_color = STYLE_WARNING
        self._sdk_manager.show(
            message,
            icon=icon or default_icon,
            color=color or default_color,
            duration_ms=duration_ms,
        )


# Singleton accessor
toast_manager = ToastManager()
