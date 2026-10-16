from karcytics_sdk.host.ai import AIAssistant
from PySide6.QtCore import QThread, Signal


class StreamingAIThread(QThread):
    """Worker thread for streaming AI responses."""

    chunk_received = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        assistant: AIAssistant,
        prompt: str,
        plugin_id: str,
        include_core: bool,
        selected_files: list,
    ):
        super().__init__()
        self.assistant = assistant
        self.prompt = prompt
        self.plugin_id = plugin_id
        self.include_core = include_core
        self.selected_files = selected_files

    def run(self):
        try:
            result = self.assistant.ask_question(
                prompt=self.prompt,
                plugin_id=self.plugin_id,
                include_core=self.include_core,
                selected_files=self.selected_files,
                stream=True,
                callback=self.chunk_received.emit,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AIService:
    """Orchestrates AI interactions and session state."""

    from karcytics.core.config import AppConfig

    def __init__(self, assistant: AIAssistant | None = None):
        self.assistant = assistant or AIAssistant()
        self.full_chat_md = ""
        self.selected_context_files: list[str] = []

    def clear_history(self):
        self.assistant.history = []
        self.full_chat_md = "\n\n*Conversation cleared.*\n\n"

    def get_streaming_thread(self, prompt, plugin_id, include_core):
        return StreamingAIThread(
            self.assistant, prompt, plugin_id, include_core, self.selected_context_files
        )
