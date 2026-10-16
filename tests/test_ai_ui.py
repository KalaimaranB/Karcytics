from PySide6.QtCore import QObject, Qt, Signal

from karcytics.ui.components.ai_panel import AIChatWindow


def test_ai_chat_window_initialization(qtbot):
    """Ensure the AI Chat Window initializes and has the refactored methods."""
    window = AIChatWindow()
    qtbot.addWidget(window)

    assert hasattr(window, "_send_message")
    assert hasattr(window, "_on_ai_chunk")
    assert hasattr(window, "_render_chat")
    assert hasattr(window, "service")

    assert window.windowTitle() == "Karcytics AI Assistant"


def test_ai_chat_window_ui_elements(qtbot):
    """Check that UI elements are present."""
    window = AIChatWindow()
    qtbot.addWidget(window)

    assert window.input_field is not None
    assert window.btn_send is not None
    assert window.chat_history is not None
    assert window.context_sidebar is not None


def test_ai_chat_window_send_message(qtbot, monkeypatch):
    """Test that sending a message updates the history."""
    window = AIChatWindow()
    qtbot.addWidget(window)

    # Mock the thread so it doesn't actually run
    class MockThread(QObject):
        chunk_received = Signal(str)
        finished = Signal(object)
        error = Signal(str)

        def start(self):
            pass

    monkeypatch.setattr(window.service, "get_streaming_thread", lambda *args: MockThread())

    window.input_field.setText("Tell me a joke")
    qtbot.mouseClick(window.btn_send, Qt.MouseButton.LeftButton)

    assert window.input_field.text() == ""
    assert "**You:** Tell me a joke" in window.service.full_chat_md
