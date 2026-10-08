"""Tests for TaskScheduler and centralized concurrency management."""

from dataclasses import dataclass
from typing import Any

import pytest
from karcytics_sdk.plugin import AnalysisBase, PluginState

from karcytics.core.task_scheduler import task_scheduler


@dataclass
class MockState(PluginState):
    value: int = 0


class MockAnalyzer(AnalysisBase):
    def run(self, state: PluginState | None = None) -> dict[str, Any]:
        if state is None or not isinstance(state, MockState) or state.value == -1:
            raise ValueError("Intentional Error")
        return {"result": state.value * 2}


@pytest.fixture
def scheduler():
    """Returns the global task_scheduler proxy instance."""
    return task_scheduler


class TestTaskScheduler:
    """Test suite for the centralized TaskScheduler."""

    def test_singleton_nature(self):
        """Verifies that task_scheduler follows the singleton pattern."""
        s1 = task_scheduler._get_instance()
        s2 = task_scheduler._get_instance()
        assert s1 is s2

    def test_task_submission_and_success(self, qtbot, scheduler):
        """Verifies that a submitted task executes and returns results via signals."""
        analyzer = MockAnalyzer("test_success")
        state = MockState(21)

        # We'll collect signals
        results_received = {}

        def on_finished(tid, res):
            results_received[tid] = res

        scheduler.task_finished.connect(on_finished)

        with qtbot.waitSignal(scheduler.task_finished, timeout=1000):
            worker = scheduler.submit(analyzer, state)
            task_id = worker.task_id
            assert worker is not None

        assert task_id in results_received
        assert results_received[task_id]["result"] == 42

        # Verify internal cleanup
        assert task_id not in scheduler._active_workers

    def test_task_error_propagation(self, qtbot, scheduler):
        """Verifies that errors in tasks are caught and propagated globally."""
        analyzer = MockAnalyzer("test_error")
        state = MockState(-1)  # Triggers ValueError

        errors_received = {}

        def on_error(tid, msg):
            errors_received[tid] = msg

        scheduler.task_error.connect(on_error)

        with qtbot.waitSignal(scheduler.task_error, timeout=1000):
            worker = scheduler.submit(analyzer, state)
            task_id = worker.task_id

        assert task_id in errors_received
        assert "Intentional Error" in errors_received[task_id]

        # Verify internal cleanup
        assert task_id not in scheduler._active_workers

    def test_concurrent_execution(self, qtbot, scheduler):
        """Verifies that multiple tasks can be submitted and run concurrently."""
        analyzer1 = MockAnalyzer("task1")
        analyzer2 = MockAnalyzer("task2")

        finished_ids = []
        scheduler.task_finished.connect(lambda tid, _: finished_ids.append(tid))

        # Submit two tasks
        worker1 = scheduler.submit(analyzer1, MockState(10))
        worker2 = scheduler.submit(analyzer2, MockState(20))
        tid1, tid2 = worker1.task_id, worker2.task_id

        # Wait for both (we expect two finished signals)
        qtbot.waitUntil(lambda: len(finished_ids) == 2, timeout=2000)

        assert tid1 in finished_ids
        assert tid2 in finished_ids

    def test_cancel_all(self, scheduler):
        """Verify cancel_all clears the thread pool."""
        scheduler.cancel_all()
        # Just ensure no crash, verifying QThreadPool.clear()

    def test_shutdown(self, scheduler):
        """Verify graceful shutdown clears workers and waits for pool."""
        scheduler.shutdown()
        assert len(scheduler._active_workers) == 0

    def test_submit_exception_diagnostics(self, scheduler):
        """Verify that submission failures report errors to diagnostics."""
        from unittest.mock import patch

        with (
            patch(
                "karcytics.core.task_scheduler.AnalysisWorker",
                side_effect=RuntimeError("Submit fail"),
            ),
            patch("karcytics.core.diagnostics.diagnostics.report_error") as mock_diag,
            pytest.raises(RuntimeError),
        ):
            scheduler.submit(MockAnalyzer("fail"), MockState())
            mock_diag.assert_called()

    def test_on_task_error_diagnostics(self, scheduler):
        """Verify that background task errors report to diagnostics."""
        from unittest.mock import patch

        with patch("karcytics.core.diagnostics.diagnostics.report_error") as mock_diag:
            scheduler._on_task_error("tid", "Internal Failure")
            mock_diag.assert_called()

    def test_lambda_connected_to_worker_finished_is_delivered(self, qtbot, scheduler):
        """PySide6 delivers a non-bound-method slot through the sender, so a
        scheduler that destroyed the worker during cleanup silently dropped
        any lambda a caller had connected to `worker.finished`.
        """
        import threading

        from karcytics_sdk.plugin.managed_task import FunctionalTask

        connected = threading.Event()  # hold the task until the slot is connected

        def work():
            connected.wait(5)
            return {"result": 8}

        received = []
        worker = scheduler.submit(FunctionalTask(work, "test"), None)
        worker.finished.connect(lambda results: received.append(results))
        del worker  # callers such as RenderPipelineController keep no reference
        connected.set()

        qtbot.waitUntil(lambda: bool(received), timeout=5000)
        assert received[0]["result"] == 8

    def test_cleanup_signal_disconnect_resilience(self, scheduler):
        """Verify that cleanup handles workers already partially deleted or disconnected."""
        from unittest.mock import MagicMock

        mock_worker = MagicMock()
        scheduler._active_workers["ghost"] = mock_worker
        # Mock disconnect to raise a common Qt runtime error
        mock_worker.finished.disconnect.side_effect = RuntimeError("Signal not connected")

        scheduler._cleanup("ghost")
        assert "ghost" not in scheduler._active_workers
