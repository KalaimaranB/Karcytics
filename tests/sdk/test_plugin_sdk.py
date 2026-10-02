"""Tests for karcytics.core.plugin_sdk module."""

from dataclasses import dataclass
from typing import Any

from karcytics_sdk.plugin import (
    AnalysisBase,
    AnalysisWorker,
    PluginBase,
    PluginSignals,
    PluginState,
    StepIndicator,
    WizardPanel,
    WizardStep,
)
from PyQt6.QtWidgets import QLabel, QWidget

# Tests for PluginState


@dataclass
class DummyState(PluginState):
    """Test state class."""

    counter: int = 0
    name: str = ""
    data: list | None = None

    def __post_init__(self):
        if self.data is None:
            self.data = []


@dataclass
class ComplexState(PluginState):
    """Complex state with nested data."""

    image_path: str = ""
    threshold: float = 0.5
    results: dict | None = None

    def __post_init__(self):
        if self.results is None:
            self.results = {}


# Tests for PluginState


class TestPluginState:
    """Test PluginState serialization."""

    def test_simple_state_to_dict(self):
        state = DummyState(counter=42, name="test")
        state_dict = state.to_dict()

        assert state_dict["counter"] == 42
        assert state_dict["name"] == "test"
        assert isinstance(state_dict, dict)

    def test_state_from_dict(self):
        data = {"counter": 99, "name": "loaded", "data": [1, 2, 3]}
        state = DummyState.from_dict(data)

        assert state.counter == 99
        assert state.name == "loaded"
        assert state.data == [1, 2, 3]

    def test_state_roundtrip(self):
        original = DummyState(counter=50, name="original", data=[1, 2])
        state_dict = original.to_dict()
        restored = DummyState.from_dict(state_dict)

        assert original.counter == restored.counter
        assert original.name == restored.name
        assert original.data == restored.data

    def test_complex_state_serialization(self):
        state = ComplexState(
            image_path="/path/to/image.tiff", threshold=0.75, results={"bands": 5, "lanes": 3}
        )
        state_dict = state.to_dict()
        restored = ComplexState.from_dict(state_dict)

        assert restored.image_path == "/path/to/image.tiff"
        assert restored.threshold == 0.75
        assert restored.results == {"bands": 5, "lanes": 3}


# Tests for PluginSignals


class TestPluginSignals:
    """Test PluginSignals."""

    def test_signals_exist(self):
        signals = PluginSignals()

        # Check all expected signals exist
        assert hasattr(signals, "status_message")
        assert hasattr(signals, "state_changed")
        assert hasattr(signals, "analysis_started")
        assert hasattr(signals, "analysis_complete")
        assert hasattr(signals, "analysis_error")
        assert hasattr(signals, "undo_available")
        assert hasattr(signals, "redo_available")

    def test_signal_emit(self, qtbot):
        signals = PluginSignals()
        received = []

        signals.status_message.connect(lambda msg: received.append(msg))
        signals.status_message.emit("Test message")

        assert "Test message" in received


# Tests for AnalysisBase


class TestAnalysisBase:
    """Test AnalysisBase."""

    class DummyAnalyzer(AnalysisBase):
        """Simple analyzer for testing."""

        def run(self, state: PluginState | None = None) -> dict[str, Any]:
            assert isinstance(state, DummyState)
            if not hasattr(state, "counter"):
                raise ValueError("No counter in state")
            return {"result": state.counter * 2}

        def validate(self, state: PluginState) -> tuple[bool, str]:
            if hasattr(state, "counter") and state.counter < 0:
                return False, "Counter must be positive"
            return True, ""

    def test_analyzer_run(self):
        analyzer = self.DummyAnalyzer("test")
        state = DummyState(counter=10)

        result = analyzer.run(state)
        assert result["result"] == 20

    def test_analyzer_validation_pass(self):
        analyzer = self.DummyAnalyzer("test")
        state = DummyState(counter=5)

        is_valid, msg = analyzer.validate(state)
        assert is_valid is True

    def test_analyzer_validation_fail(self):
        analyzer = self.DummyAnalyzer("test")
        state = DummyState(counter=-5)

        is_valid, msg = analyzer.validate(state)
        assert is_valid is False
        assert "positive" in msg.lower()

    def test_analyzer_signals(self):
        analyzer = self.DummyAnalyzer("test")
        assert hasattr(analyzer.signals, "status_message")


# Tests for WizardStep


class TestWizardStep:
    """Test WizardStep base class."""

    class TestStep(WizardStep):
        """Concrete WizardStep for testing."""

        label = "Test Step"
        is_terminal = False

        def build_page(self, panel) -> QWidget:
            """
            Build the widget displayed for this wizard step.

            Parameters:
                panel: The wizard panel containing the step.

            Returns:
                QWidget: An empty widget for the step page.
            """
            page = QWidget()
            return page  # noqa: RET504

        def on_next(self, panel) -> bool:
            return True

    def test_step_has_label(self):
        step = self.TestStep()
        assert step.label == "Test Step"

    def test_step_on_next(self):
        step = self.TestStep()
        result = step.on_next(None)
        assert result is True

    def test_step_row_helper(self, qtbot):
        step = self.TestStep()
        widget = QLabel("Test")
        layout = step._row("Label:", widget, label_width=150)

        assert layout.count() >= 2

    def test_step_scroll_wrapper(self, qtbot):
        step = self.TestStep()
        page = QWidget()
        scroll = step._scroll(page)

        from PyQt6.QtWidgets import QScrollArea

        assert isinstance(scroll, QScrollArea)


# Tests for StepIndicator


class TestStepIndicator:
    """Test StepIndicator widget."""

    def test_indicator_creation(self, qtbot):
        steps = ["Step 1", "Step 2", "Step 3"]
        indicator = StepIndicator(steps)

        assert indicator._steps == steps
        assert len(indicator._circles) == 3

    def test_indicator_step_clicked_signal(self, qtbot):
        steps = ["Step 1", "Step 2"]
        indicator = StepIndicator(steps)

        received = []
        indicator.step_clicked.connect(lambda idx: received.append(idx))

        # Emit click signal
        indicator.step_clicked.emit(1)
        assert 1 in received


# Tests for WizardPanel


class TestWizardPanel:
    """Test WizardPanel."""

    class SimpleStep(WizardStep):
        label = "Simple"

        def build_page(self, panel):
            return QWidget()

        def on_next(self, panel):
            return True

    def test_panel_creation(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps, title="Test Wizard")

        assert panel._steps == steps
        assert panel._idx == 0

    def test_panel_navigation_forward(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps)

        assert panel._idx == 0
        panel.go_next()
        assert panel._idx == 1
        panel.go_next()
        assert panel._idx == 2

    def test_panel_navigation_backward(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps)
        panel._idx = 1

        panel.go_back()
        assert panel._idx == 0

    def test_panel_back_disabled_at_start(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps)

        assert panel._btn_back.isEnabled() is False

    def test_panel_back_enabled_after_advance(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps)
        panel.go_next()

        assert panel._btn_back.isEnabled() is True

    def test_panel_current_step(self, qtbot):
        steps = [self.SimpleStep(), self.SimpleStep()]
        panel = WizardPanel(steps)

        assert panel.current_step == steps[0]
        panel.go_next()
        assert panel.current_step == steps[1]


# Tests for PluginBase


class TestPluginBase:
    """Test PluginBase."""

    class MockPlugin(PluginBase):
        def __init__(self):
            super().__init__("test_plugin")
            self.state = DummyState()

        def get_state(self) -> PluginState:
            return self.state

        def set_state(self, state: PluginState) -> None:
            self.state = state

    def test_plugin_creation(self, qtbot):
        plugin = self.MockPlugin()
        assert plugin.plugin_id == "test_plugin"
        assert plugin.undo_history is not None

    def test_plugin_push_state(self, qtbot):
        plugin = self.MockPlugin()
        # First push sets the baseline; second push creates an undoable step.
        plugin.state.counter = 42
        plugin.push_state()
        plugin.state.counter = 99
        plugin.push_state()

        assert plugin.undo_history.can_undo()

    def test_plugin_undo(self, qtbot):
        plugin = self.MockPlugin()

        # Push two states
        plugin.state.counter = 10
        plugin.push_state()
        plugin.state.counter = 20
        plugin.push_state()

        # Undo once
        plugin.undo()
        assert plugin.state.counter == 10

    def test_plugin_redo(self, qtbot):
        plugin = self.MockPlugin()

        # Push two states
        plugin.state.counter = 10
        plugin.push_state()
        plugin.state.counter = 20
        plugin.push_state()

        # Undo and redo
        plugin.undo()
        plugin.redo()
        assert plugin.state.counter == 20

    def test_plugin_can_undo(self, qtbot):
        plugin = self.MockPlugin()
        assert plugin.can_undo() is False

        plugin.state.counter = 42
        plugin.push_state()
        plugin.state.counter = 43
        plugin.push_state()
        assert plugin.can_undo() is True

    def test_plugin_can_redo(self, qtbot):
        plugin = self.MockPlugin()
        plugin.state.counter = 10
        plugin.push_state()
        plugin.state.counter = 20
        plugin.push_state()

        assert plugin.can_redo() is False
        plugin.undo()
        assert plugin.can_redo() is True


# Tests for AnalysisWorker


class TestAnalysisWorker:
    """Test AnalysisWorker."""

    class SimpleAnalyzer(AnalysisBase):
        def run(self, state: PluginState | None = None) -> dict[str, Any]:
            assert isinstance(state, DummyState)
            return {"computed": state.counter * 3}

    def test_worker_creation(self):
        analyzer = self.SimpleAnalyzer("test")
        state = DummyState(counter=5)
        worker = AnalysisWorker(analyzer, state)

        assert worker.analyzer == analyzer
        assert worker.state == state

    def test_worker_signals(self):
        analyzer = self.SimpleAnalyzer("test")
        state = DummyState()
        worker = AnalysisWorker(analyzer, state)

        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")
        assert hasattr(worker, "progress")
