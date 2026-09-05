"""Karcytics Diagnostic & Error Management Engine.

Provides centralized error handling, black-box logging, and system health monitoring.
"""

import logging
import traceback
from collections import deque
from datetime import datetime
from typing import Any

from karcytics.core.event_bus import KarcyticsEvent, event_bus


class BlackBoxHandler(logging.Handler):
    """Memory-resident logging handler that keeps the last N records.

    Acts like an airplane's black box, allowing us to see what happened
    just before a crash.
    """

    def __init__(self, capacity: int = 100) -> None:  # noqa: D107
        """Initialize a log handler that retains up to ``capacity`` records."""
        super().__init__()
        self.capacity = capacity
        self.records: deque[dict[str, Any]] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        """Store a formatted log record in the in-memory history.

        Parameters:
                record: The log record to format and store.
        """
        try:
            msg = self.format(record)
            self.records.append(
                {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "name": record.name,
                    "message": msg,
                    "plugin_id": getattr(record, "plugin_id", None),
                }
            )
        except Exception:
            self.handleError(record)

    def get_history(self) -> list[dict[str, Any]]:
        """Return the captured history as a list of dicts."""
        return list(self.records)


class AutoReportHandler(logging.Handler):
    """Intercepts ERROR and CRITICAL logs to automatically route them to the DiagnosticEngine.

    This eliminates the need for manual `try/except: diagnostics.report_error()` blocks
    scattered throughout the codebase.
    """

    def __init__(self, engine: "DiagnosticEngine") -> None:  # noqa: D107
        """Initialize the handler to forward error-level records to a diagnostic engine.

        Parameters:
                engine (DiagnosticEngine): Diagnostic engine that receives reported errors.
        """
        super().__init__(level=logging.ERROR)
        self.engine = engine

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        # Prevent infinite recursion if the DiagnosticEngine itself logs an error
        """Forward a log record to the diagnostic engine for reporting.

        Records emitted by the diagnostic logger are ignored to prevent recursive
        reporting. Records from the event bus are also ignored: `event_bus.py`
        logs here when an `ERROR_OCCURRED` *listener itself* raises — reporting
        that as a new error would re-emit `ERROR_OCCURRED`, re-invoking the same
        broken listener, which logs again here, forever (this actually happened
        in production: a broken `setFont()` call in the error dialog listener
        caused an infinite report -> emit -> dispatch -> report cycle until the
        recursion limit was hit). A listener failure is a bug in that listener,
        not a new application error to broadcast through the same channel.
        """
        if record.name in ("karcytics.core.diagnostics", "karcytics.core.event_bus"):
            return

        try:
            msg = self.format(record)
            fatal = record.levelno >= logging.CRITICAL
            plugin_id = getattr(record, "plugin_id", None)

            # Auto-extract exception info if provided via exc_info=True
            exc = None
            if record.exc_info and record.exc_info[1]:
                exc = record.exc_info[1]

            self.engine.report_error(message=msg, exception=exc, plugin_id=plugin_id, fatal=fatal)
        except Exception:
            self.handleError(record)


class DiagnosticEngine:
    """Central nervous system for application health and error reporting."""

    _instance: "DiagnosticEngine | None" = None
    _initialized: bool = False

    def __new__(cls) -> "DiagnosticEngine":  # noqa: D102
        """Create and return the class's shared singleton instance.

        Returns:
            DiagnosticEngine: The shared instance of the class.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:  # noqa: D107
        """Initialize the diagnostic engine with logging handlers and error-reporting state."""
        if self._initialized:
            return

        self.black_box = BlackBoxHandler()
        self.black_box.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )

        # Attach black box to the root logger so it sees everything
        logging.getLogger().addHandler(self.black_box)

        # Attach AutoReportHandler to the root logger to catch and report all errors
        self.auto_reporter = AutoReportHandler(self)
        self.auto_reporter.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self.auto_reporter)

        # Throttling state
        self._last_error_sig: str | None = None
        self._last_error_time: float = 0.0

        self._initialized = True

    def report_error(  # noqa: PLR0913
        self,
        message: str,
        exception: BaseException | None = None,
        plugin_id: str | None = None,
        fatal: bool = False,
        exception_repr: str | None = None,
        traceback_str: str | None = None,
    ) -> None:
        """Report an error to the system.

        This will log the error and broadcast it via the Event Bus for UI display.

        `exception_repr`/`traceback_str` are for a caller with no live
        exception object to hand over — an isolated plugin process, whose
        error crosses an RPC/event boundary as an already-formatted string
        (see `core_services_bootstrap.py`'s `diagnostics.report_error`
        handler and `plugins/loader.py`'s `diagnostics_error` event
        forwarding). `exception`/`traceback.format_exc()` still win when a
        real exception is passed — this is only the fallback for the case
        `sys.exc_info()` in *this* process has nothing to offer.
        """
        import time

        now = time.time()
        error_sig = f"{message}|{str(exception)}"

        # Throttle identical errors to max 1 per 2 seconds to prevent dialog storms
        if self._last_error_sig == error_sig and (now - self._last_error_time) < 2.0:
            return

        self._last_error_sig = error_sig
        self._last_error_time = now

        tb = traceback.format_exc() if exception else traceback_str

        error_data = {
            "message": message,
            "exception": str(exception) if exception else exception_repr,
            "traceback": tb,
            "plugin_id": plugin_id,
            "fatal": fatal,
            "timestamp": datetime.now().isoformat(),
            "history": self.black_box.get_history(),
        }

        # Log it officially
        logger = logging.getLogger("karcytics.core.diagnostics")
        log_msg = f"Error Reported: {message}"
        if plugin_id:
            log_msg = f"[{plugin_id}] {log_msg}"

        if fatal:
            logger.critical(log_msg, extra={"plugin_id": plugin_id})

            from karcytics.core.crash_reporting import capture_fatal_error

            capture_fatal_error(
                message=message, exception=exception, plugin_id=plugin_id, traceback_str=tb
            )
        else:
            logger.error(log_msg, extra={"plugin_id": plugin_id})

            # Non-fatal errors are also auto-sent to Sentry when crash
            # reporting is active and consent has been given. The
            # ErrorReportDialog shown to the user displays what was sent
            # (unlike the fatal path, where we can't reliably show UI).
            from karcytics.core.crash_reporting import capture_error

            capture_error(
                message=message,
                exception=exception,
                plugin_id=plugin_id,
                traceback_str=tb,
                level="error",
            )

        # Broadcast to UI
        event_bus.emit(KarcyticsEvent.ERROR_OCCURRED, error_data)

    def get_full_diagnostic_report(self) -> dict[str, Any]:
        """Generate a complete snapshot of the system state for debugging."""
        return {
            "timestamp": datetime.now().isoformat(),
            "history": self.black_box.get_history(),
            # Future: add hardware stats, loaded plugins, etc.
        }


# Singleton accessor
diagnostics = DiagnosticEngine()
