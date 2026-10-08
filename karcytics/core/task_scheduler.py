"""Centralized Task Scheduler for Karcytics.

Manages a global thread pool to execute long-running analysis tasks,
preventing thread exhaustion and ensuring UI responsiveness.
"""

import logging
import uuid
from functools import partial
from typing import Any

from karcytics_sdk.plugin import AnalysisBase, AnalysisRunnable, AnalysisWorker, PluginState
from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class TaskScheduler(QObject):
    """Singleton manager for background computations.

    Provides a central point for task submission, monitoring, and
    resource management. Integration with Karcytics's Nervous System
    via task lifecycle signals.
    """

    # Lifecycle signals for global monitoring and debugging
    task_started = Signal(str)  # task_id
    task_finished = Signal(str, object)  # task_id, results
    task_error = Signal(str, str)  # task_id, error_message
    task_progress = Signal(str, int)  # task_id, progress (0-100)

    def __init__(self) -> None:
        """Initialize the scheduler with the global thread pool and active-worker tracking."""
        super().__init__()
        self.pool: Any = QThreadPool.globalInstance()
        assert self.pool is not None

        # Retain references to active workers to prevent Python's GC
        # from reclaiming them while the C++ thread is still running.
        self._active_workers: dict[str, AnalysisWorker] = {}

        logger.info(f"TaskScheduler initialized. Thread pool limit: {self.pool.maxThreadCount()}")

    def submit(self, analyzer: AnalysisBase, state: PluginState | None = None) -> AnalysisWorker:
        """Submit an analysis task to the central thread pool.

        Args:
            analyzer: Instance of AnalysisBase subclass containing the logic.
            state: Instance of PluginState containing parameters (optional).

        Returns:
            The AnalysisWorker instance for signal connection.
        """
        try:
            task_id = str(uuid.uuid4())

            # 1. Create the worker (The QObject that does the work and talks to the UI)
            worker = AnalysisWorker(analyzer, state, parent=self)
            worker.task_id = task_id  # type: ignore[attr-defined]  # Attach ID for tracking

            # 2. Bridge worker signals to the global scheduler signals
            worker.finished.connect(partial(self._on_task_finished, task_id))
            worker.error.connect(partial(self._on_task_error, task_id))
            worker.progress.connect(partial(self.task_progress.emit, task_id))

            # Connect to deleteLater to schedule safe automatic cleanup
            worker.finished.connect(worker.deleteLater)
            worker.error.connect(worker.deleteLater)
            worker.cancelled.connect(worker.deleteLater)

            # 3. Track active workers (releases on completion via _cleanup)
            self._active_workers[task_id] = worker

            # 4. Wrap and schedule
            runnable = AnalysisRunnable(worker)
            self.task_started.emit(task_id)
            self.pool.start(runnable)

            logger.debug(f"Submitted task {task_id} ({analyzer.plugin_id}) to pool.")
            return worker
        except Exception as e:
            logger.error(f"Failed to submit task to scheduler: {e}")
            raise e

    def cancel_all(self) -> None:
        """Attempt to stop all pending tasks in the pool."""
        self.pool.clear()
        logger.warning("Task pool cleared. Pending tasks cancelled.")

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler after clearing pending tasks."""
        logger.info("TaskScheduler shutting down...")
        self.pool.clear()
        # Wait up to 2 seconds for active threads to finish or abort safely
        self.pool.waitForDone(2000)
        self._active_workers.clear()

    @Slot(str, object)
    def _on_task_finished(self, task_id: str, results: dict) -> Any:
        """Handle successful task completion by emitting results and releasing workers."""
        self.task_finished.emit(task_id, results)
        self._cleanup(task_id)

    @Slot(str, str)
    def _on_task_error(self, task_id: str, error_msg: str) -> Any:
        """Emit a task error signal and release the associated worker reference.

        Parameters:
            task_id (str): Identifier of the failed task.
            error_msg (str): Description of the task failure.
        """
        self.task_error.emit(task_id, error_msg)
        logger.error(f"Background task {task_id} failed: {error_msg}")

        if "failed ready handshake" in error_msg or "Daemon call failed" in error_msg:
            from karcytics.core.event_bus import ErrorEventPayload, KarcyticsEvent, event_bus

            # Emit typed recovery event, keeping existing recovery guidance
            payload: ErrorEventPayload = {
                "title": "Plugin Virtual Environment Error",
                "message": (
                    "A critical error occurred while attempting to connect to the plugin's "
                    f"virtual environment.\n\n{error_msg}\n\nTry going to the Hub -> Help menu "
                    "and clicking 'Clear App Data...' to reset your environment."
                ),
            }
            event_bus.emit(KarcyticsEvent.ERROR_OCCURRED, payload)

        self._cleanup(task_id)

    def _cleanup(self, task_id: str) -> Any:
        """Release the scheduler's reference to a completed worker.

        Parameters:
            task_id (str): Identifier of the task whose worker reference should be released.
        """
        if task_id in self._active_workers:
            # We explicitly do NOT call worker.finished.disconnect() here because
            # this method is called *during* the finished signal emission.
            # Disconnecting it would instantly clear the connection list, preventing
            # downstream slots (like deleteLater and local UI callbacks) from executing.
            worker = self._active_workers[task_id]
            try:
                import shiboken6

                if shiboken6.isValid(worker):
                    worker.setParent(None)
            except (ImportError, AttributeError, RuntimeError):
                pass
            finally:
                del self._active_workers[task_id]


class TaskSchedulerProxy:
    """Lazy proxy wrapper to defer C++ QObject creation until first access.

    Prevents PySide6 crashes on Windows when imported before a QCoreApplication
    instance is fully initialized.
    """

    def __init__(self) -> None:
        """Initialize the proxy without creating the scheduler instance."""
        self._instance: TaskScheduler | None = None

    def _get_instance(self) -> TaskScheduler:
        """Return the lazily initialized task scheduler instance.

        Returns:
            TaskScheduler: The shared task scheduler instance.
        """
        if self._instance is None:
            self._instance = TaskScheduler()
        return self._instance

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the lazily initialized task scheduler instance.

        Parameters:
            name (str): Name of the attribute to retrieve.

        Returns:
            Any: Value of the requested attribute.
        """
        return getattr(self._get_instance(), name)


# Singleton proxy instance for application-wide use
task_scheduler: TaskScheduler = TaskSchedulerProxy()  # type: ignore[assignment]
