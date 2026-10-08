import sys
from pathlib import Path
from typing import Any

import pytest

# Test-specific timeout constant for smoke test validation
TEST_SMOKE_TIMEOUT_MS = 100


class _MockModuleManager:
    """Minimal `module_manager` double for `_run_smoke_test_in_process`,
    which only ever calls `load_module_ui` on it — unlike `_run_smoke_test`
    itself, it never touches `.modules`/`reload_modules()` (see
    tests/test_boot_cli_dispatch.py for coverage of that routing layer).
    """

    def __init__(self, panel_class: type) -> None:
        self._panel_class = panel_class

    def load_module_ui(self, module_id: str) -> type:  # noqa: ARG002
        return self._panel_class


def test_smoke_test_timeout_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the in-process smoke test returns failure when data_ready signal never emits."""
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QApplication, QWidget

    # Mock panel class that has data_ready but never emits it
    class MockPanel(QWidget):
        data_ready = Signal()

        def __init__(self) -> None:
            super().__init__()

        def load_workflow(self, *args: Any, **kwargs: Any) -> None:
            # Simulate loading but never emit data_ready
            pass

    monkeypatch.setattr("karcytics.__main__.SMOKE_TEST_TIMEOUT_MS", TEST_SMOKE_TIMEOUT_MS)

    try:
        from karcytics.__main__ import _run_smoke_test_in_process

        exit_code = _run_smoke_test_in_process(
            _MockModuleManager(MockPanel), "test_plugin", "/tmp/test_data.fcs"
        )

        # Should return 1 because data_ready never emitted
        assert exit_code == 1
    finally:
        # Clean up QApplication instance
        app = QApplication.instance()
        if app:
            app.quit()


def test_smoke_test_panel_ready_without_data_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the in-process smoke test succeeds when panel_ready emits but data_ready is absent."""
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtWidgets import QApplication, QWidget

    # Track load_workflow invocations
    load_workflow_calls: list[Any] = []

    # Mock panel class that has panel_ready but NOT data_ready
    class MockPanel(QWidget):
        panel_ready = Signal()

        def __init__(self) -> None:
            super().__init__()

        def begin_async_init(self) -> None:
            # Emit panel_ready asynchronously to test race condition fix
            QTimer.singleShot(0, self.panel_ready.emit)

        def load_workflow(self, *args: Any, **kwargs: Any) -> None:
            load_workflow_calls.append((args, kwargs))

    monkeypatch.setattr("karcytics.__main__.SMOKE_TEST_TIMEOUT_MS", TEST_SMOKE_TIMEOUT_MS)

    try:
        from karcytics.__main__ import _run_smoke_test_in_process

        exit_code = _run_smoke_test_in_process(
            _MockModuleManager(MockPanel), "test_plugin", "/tmp/test_data.fcs"
        )

        # Should return 0 because panel_ready emitted and load_workflow was called
        assert exit_code == 0
        # load_workflow should have been called exactly once
        assert len(load_workflow_calls) == 1
    finally:
        # Clean up QApplication instance
        app = QApplication.instance()
        if app:
            app.quit()


def test_smoke_test_panel_ready_load_workflow_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify failure when load_workflow raises on a panel lacking data_ready."""
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtWidgets import QApplication, QWidget

    # Mock panel class that has panel_ready but NOT data_ready, and load_workflow raises
    class MockPanel(QWidget):
        panel_ready = Signal()

        def __init__(self) -> None:
            super().__init__()

        def begin_async_init(self) -> None:
            # Emit panel_ready asynchronously to test race condition fix
            QTimer.singleShot(0, self.panel_ready.emit)

        def load_workflow(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Simulated load_workflow failure")

    monkeypatch.setattr("karcytics.__main__.SMOKE_TEST_TIMEOUT_MS", TEST_SMOKE_TIMEOUT_MS)

    try:
        from karcytics.__main__ import _run_smoke_test_in_process

        exit_code = _run_smoke_test_in_process(
            _MockModuleManager(MockPanel), "test_plugin", "/tmp/test_data.fcs"
        )

        # Should return 1 because load_workflow raised an exception
        assert exit_code == 1
    finally:
        # Clean up QApplication instance
        app = QApplication.instance()
        if app:
            app.quit()


def test_ai_server_cli_mode(monkeypatch):
    """Verify that the 'ai-server' command is correctly handled in __main__.py."""
    import importlib
    import types

    import karcytics.__main__

    mock_main_called = False

    mock_lib = types.ModuleType("llama_cpp")
    mock_server = types.ModuleType("llama_cpp.server")
    mock_main = types.ModuleType("llama_cpp.server.__main__")

    def mock_main_fn():
        nonlocal mock_main_called
        mock_main_called = True

    mock_main.main = mock_main_fn

    # Mock both the parent and the leaf to satisfy the 'import x.y.z' chain
    monkeypatch.setitem(sys.modules, "llama_cpp", mock_lib)
    monkeypatch.setitem(sys.modules, "llama_cpp.server", mock_server)
    monkeypatch.setitem(sys.modules, "llama_cpp.server.__main__", mock_main)

    # Setup sys.argv
    original_argv = sys.argv
    sys.argv = ["karcytics", "ai-server", "--model", "test.gguf"]

    try:
        # Reload to ensure we have the version with ai-server handling
        importlib.reload(karcytics.__main__)
        # We need to mock setup_logging to avoid creating files
        monkeypatch.setattr("karcytics.__main__.setup_logging", lambda: Path("/tmp/karcytics.log"))

        karcytics.__main__.main()
    except SystemExit:
        pass
    finally:
        sys.argv = original_argv

    assert mock_main_called is True


def test_sdk_cli_mode(monkeypatch):
    """Verify that the 'sdk' command is correctly handled in __main__.py."""
    mock_sdk_main_called = False

    class MockSDKModule:
        @staticmethod
        def main():
            nonlocal mock_sdk_main_called
            mock_sdk_main_called = True

    monkeypatch.setitem(sys.modules, "karcytics_sdk.sdk_cli", MockSDKModule)

    original_argv = sys.argv
    sys.argv = ["karcytics", "sdk", "test"]

    try:
        from karcytics.__main__ import main

        monkeypatch.setattr("karcytics.__main__.setup_logging", lambda: Path("/tmp/karcytics.log"))
        main()
    except SystemExit:
        pass
    finally:
        sys.argv = original_argv

    assert mock_sdk_main_called is True
