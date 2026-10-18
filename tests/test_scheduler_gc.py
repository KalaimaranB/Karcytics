import gc
import weakref

from karcytics_sdk.plugin import AnalysisBase, PluginState
from PySide6.QtCore import QCoreApplication

from karcytics.core.task_scheduler import task_scheduler


class MockState(PluginState):
    def to_dict(self) -> dict:
        return {}

    def from_dict(self, data: dict) -> None:  # type: ignore[override]
        pass


class MockAnalyzer(AnalysisBase):
    def run(self, state) -> dict:  # type: ignore[override]
        return {"status": "success"}


def test_task_scheduler_worker_gc(qapp):
    """Verify that background workers are cleanly deleted and garbage collected."""
    analyzer = MockAnalyzer("test_gc_plugin")
    state = MockState()

    # 1. Submit task to task scheduler
    worker = task_scheduler.submit(analyzer, state)
    task_id = worker.task_id  # type: ignore[attr-defined]

    # Create a weak reference to the worker to track its lifecycle
    worker_ref = weakref.ref(worker)

    # 2. Ensure worker is currently tracked and alive
    assert task_id in task_scheduler._active_workers
    assert task_scheduler._active_workers[task_id] is worker

    # 3. Wait for the thread pool to finish execution
    task_scheduler.pool.waitForDone()

    # 4. Process deferred signals (finished -> deleteLater)
    for _ in range(3):
        QCoreApplication.processEvents()

    # 5. Ensure the task is removed from active dictionary tracking
    assert task_id not in task_scheduler._active_workers

    # 6. Delete our strong reference and trigger GC
    del worker
    gc.collect()

    # Print referrers if it fails
    if worker_ref() is not None:
        print("\n=== LINGER REFS ===")
        for ref in gc.get_referrers(worker_ref()):
            print(f"Type: {type(ref)}")
            if isinstance(ref, dict):
                print(f"Keys: {list(ref.keys())[:10]}")
            else:
                print(f"Str: {str(ref)[:100]}")

    # 7. Assert that worker is fully garbage collected and released from memory
    assert worker_ref() is None
