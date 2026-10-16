import os
from typing import Any

from karcytics_sdk.host.ai import AIAssistant, AIServerManager
from PySide6.QtCore import QCoreApplication


class MockAIAssistant(AIAssistant):
    def ask_question(
        self,
        prompt: str,
        plugin_id: str | None = None,
        include_core: bool = False,
        selected_files: list[str] | None = None,
        stream: bool = False,
        callback: Any = None,
    ) -> dict[str, Any]:
        return {"result": f"Response to: {prompt}", "sources": []}


def test_ai_server_manager_initialization():
    from pathlib import Path

    manager = AIServerManager()
    assert manager.logger is not None
    expected_path = str(Path.home() / ".karcytics" / "models" / "gemma4.gguf")
    assert manager.model_path == expected_path


def test_ai_server_manager_download_prompt(qapp, monkeypatch):
    manager = AIServerManager()

    # Mock os.path.exists to simulate missing model
    monkeypatch.setattr("os.path.exists", lambda path: False)

    prompt_emitted = False

    def on_prompt_download():
        nonlocal prompt_emitted
        prompt_emitted = True

    manager.signals.prompt_download.connect(on_prompt_download)

    manager.start_server()
    QCoreApplication.processEvents()

    assert prompt_emitted is True


def test_ai_assistant_interface():
    assistant = MockAIAssistant()
    assert assistant.ask_question("Hello")["result"] == "Response to: Hello"


def test_model_path_persistence():
    """Verify that AIServerManager uses the persistent home directory path."""
    manager = AIServerManager()
    assert ".karcytics" in manager.model_path
    assert "models" in manager.model_path
    assert os.path.isabs(manager.model_path)


def test_start_server_absolute_path(monkeypatch):  # noqa: C901
    """Verify that start_server uses absolute paths for the model command."""
    manager = AIServerManager(model_path="relative/path/to/model.gguf")

    # Mock threading.Thread to run synchronously
    class MockThread:
        def __init__(self, target, *args, **kwargs):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr("threading.Thread", MockThread)

    # Mock time.sleep to run instantly
    monkeypatch.setattr("karcytics_sdk.host.ai.time.sleep", lambda x: None)

    # Mock os.path.exists to return True for our fake model
    monkeypatch.setattr("os.path.exists", lambda x: True)

    # Mock socket to simulate port 8080 is free
    class MockSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def connect_ex(self, addr):
            return 1  # Port free

    monkeypatch.setattr("socket.socket", lambda *args: MockSocket())

    # Capture subprocess.Popen calls
    popen_args = []

    def mock_popen(cmd, **kwargs):
        popen_args.append(cmd)

        # Return a mock process that is "running"
        class MockProcess:
            def __init__(self, cmd):
                self.args = cmd

            def poll(self):
                return None

            def terminate(self):
                pass

            def communicate(self, *args, **kwargs):
                return b"", b""

            def kill(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return MockProcess(cmd)

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    # Mock requests.get to simulate server ready
    class MockResponse:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    manager.start_server()

    # Verify that the model path in the command was made absolute
    assert len(popen_args) > 0
    cmd = next((c for c in popen_args if "--model" in c), None)
    assert cmd is not None, f"No command containing '--model' was found in: {popen_args}"

    model_arg_idx = cmd.index("--model") + 1
    assert os.path.isabs(cmd[model_arg_idx])
    assert "relative/path/to/model.gguf" in cmd[model_arg_idx]
