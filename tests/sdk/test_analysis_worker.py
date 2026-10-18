"""Tests for AnalysisWorker and background analysis execution."""

from dataclasses import dataclass

from karcytics_sdk.plugin import AnalysisBase, AnalysisWorker, PluginState
from PySide6.QtCore import QObject, QThread


@dataclass
class MockState(PluginState):
    """Simple mock state for testing."""

    value: int = 0


class MockAnalyzer(AnalysisBase):
    """Simple analyzer that produces results or errors."""

    def run(self, state):
        if state.value == -999:
            raise ValueError("Triggered failure")

        # Emit progress to test proxying
        self.signals.analysis_progress.emit(50)
        return {"multiplied": state.value * 2}


class TestAnalysisWorker:
    """Test suite for AnalysisWorker signals and proxying."""

    def test_worker_initialization(self):
        """Verifies worker stores analyzer and state correctly."""
        analyzer = MockAnalyzer("test_id")
        state = MockState(42)
        worker = AnalysisWorker(analyzer, state)

        assert worker.analyzer == analyzer
        assert worker.state == state
        assert isinstance(worker, QObject)

    def test_worker_success_flow(self, qtbot):
        """Verifies result emission on successful analysis run."""
        analyzer = MockAnalyzer("test")
        state = MockState(10)
        worker = AnalysisWorker(analyzer, state)

        results = []
        worker.finished.connect(lambda r: results.append(r))

        # We call run() directly for unit testing (synchronous)
        worker.run()

        assert len(results) == 1
        assert results[0]["multiplied"] == 20

    def test_worker_error_catch(self, qtbot):
        """Verifies that exceptions in the analyzer are caught and emitted via signal."""
        analyzer = MockAnalyzer("err")
        state = MockState(-999)  # Triggers exception
        worker = AnalysisWorker(analyzer, state)

        errors = []
        worker.error.connect(lambda e: errors.append(e))

        worker.run()

        assert len(errors) == 1
        assert "Triggered failure" in errors[0]

    def test_progress_signal_proxy(self, qtbot):
        """Verifies that progress signals from the analyzer are proxied by the worker."""
        analyzer = MockAnalyzer("prog")
        state = MockState(5)
        worker = AnalysisWorker(analyzer, state)

        progress_values = []
        worker.progress.connect(lambda p: progress_values.append(p))

        worker.run()

        # Now that we connected the signals in AnalysisWorker.__init__, this should work
        assert 50 in progress_values

    def test_worker_thread_integration(self, qtbot):
        """Verifies worker works correctly when moved to a secondary thread."""
        analyzer = MockAnalyzer("thread")
        state = MockState(5)
        worker = AnalysisWorker(analyzer, state)

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        # Use qtbot to wait for the finished signal
        with qtbot.waitSignal(worker.finished, timeout=1000):
            thread.start()

        thread.quit()
        thread.wait()
        assert not thread.isRunning()
