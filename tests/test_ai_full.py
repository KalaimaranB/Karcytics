from karcytics_sdk.host import AIAssistant, AIServerManager
from PySide6.QtCore import Qt

from karcytics.ui.components.ai_panel import AIChatWindow

# --- Backend Tests ---


def test_ai_assistant_history(monkeypatch):
    """Ensure the assistant correctly maintains conversation history."""

    # Mock requests.post in the karcytics.sdk.core.ai module
    class MockResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "I am Gemma 4"}}]}

    monkeypatch.setattr(
        "karcytics_sdk.host.ai.requests.post", lambda *args, **kwargs: MockResponse()
    )

    assistant = AIAssistant()
    assert len(assistant.history) == 0

    # First query includes context/instruction
    assistant.ask_question("Hello", include_core=True)
    assert len(assistant.history) == 2  # User + Assistant
    assert assistant.history[0]["role"] == "user"
    assert "Instruction:" in assistant.history[0]["content"]

    # Second query should be simple user role
    assistant.ask_question("How are you?")
    assert len(assistant.history) == 4
    assert assistant.history[2]["content"] == "How are you?"
    assert "Instruction:" not in assistant.history[2]["content"]


def test_ai_server_manager_port_check(monkeypatch):
    """Test that the manager reuses an existing server if port 8080 is bound."""
    manager = AIServerManager()

    class MockSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def connect_ex(self, addr):
            return 0  # Simulate port taken

        def settimeout(self, timeout):
            pass

    monkeypatch.setattr("socket.socket", lambda *args: MockSocket())

    class MockResponse:
        status_code = 200

        def json(self):
            return {}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    # Mock model existence
    monkeypatch.setattr("os.path.exists", lambda path: True)

    manager.start_server()
    assert manager.is_running() is True
    assert manager._process is None  # Should not have spawned a new process


# --- UI Tests ---


def test_ai_chat_window_context_defaults(qtbot, monkeypatch):
    """Verify that context checkboxes change based on the active module."""
    monkeypatch.setattr("karcytics.ui.components.ai_panel.ai_manager.is_running", lambda: True)
    # Scenario 1: No module (Project Launcher)
    window_no_mod = AIChatWindow(current_module_id=None)
    qtbot.addWidget(window_no_mod)
    assert window_no_mod.chk_module.isChecked() is False
    assert window_no_mod.chk_module.isEnabled() is False
    assert window_no_mod.chk_core.isChecked() is True

    # Scenario 2: Active module
    window_mod = AIChatWindow(current_module_id="test_plugin")
    qtbot.addWidget(window_mod)
    assert window_mod.chk_module.isChecked() is True
    assert window_mod.chk_core.isChecked() is False


def test_ai_chat_window_clear_logic(qtbot, monkeypatch):
    """Test that the Clear button resets both UI and backend history."""
    monkeypatch.setattr("karcytics.ui.components.ai_panel.ai_manager.is_running", lambda: True)
    window = AIChatWindow()
    qtbot.addWidget(window)

    # Add some fake history
    window.assistant.history = [{"role": "user", "content": "test"}]
    window._append_chat("Test Message")

    # Click clear
    qtbot.mouseClick(window.btn_clear, Qt.MouseButton.LeftButton)

    assert len(window.assistant.history) == 0
    assert "Conversation cleared" in window.chat_history.toPlainText()


def test_ai_chat_window_send_logic(qtbot, monkeypatch):
    """Ensure the send button triggers the background task correctly."""
    monkeypatch.setattr("karcytics.ui.components.ai_panel.ai_manager.is_running", lambda: True)
    window = AIChatWindow()
    qtbot.addWidget(window)
    window.show()

    # Mock the thread so it doesn't actually run
    from PySide6.QtCore import QObject, Signal

    class MockThread(QObject):
        chunk_received = Signal(str)
        finished = Signal(object)
        error = Signal(str)

        def start(self):
            pass

    monkeypatch.setattr(window.service, "get_streaming_thread", lambda *args: MockThread())

    window.input_field.setText("Tell me about the event bus")
    qtbot.mouseClick(window.btn_send, Qt.MouseButton.LeftButton)

    assert window.ai_thread is not None
    assert window.thinking_indicator.isVisible()
    assert window.btn_send.isEnabled() is False
