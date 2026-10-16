from karcytics_sdk.host.ai import AIAssistant
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from karcytics.ui.theme import Colors, theme_manager


class ContextPanel(QWidget):
    """Integrated sidebar for managing AI context."""

    selection_changed = Signal(list)

    def __init__(self, parent, assistant: AIAssistant):
        super().__init__(parent)
        self.assistant = assistant
        self.plugin_id: str | None = None
        self.include_core = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header
        header = QLabel("DOCUMENT CONTEXT")
        theme_manager.apply_style(
            header,
            f"font-weight: bold; color: {Colors.ACCENT_PRIMARY}; font-size: 10px; letter-spacing: 1px;",
        )
        layout.addWidget(header)

        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter docs...")
        theme_manager.apply_style(
            self.search_bar,
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 4px; font-size: 11px;",
        )
        self.search_bar.textChanged.connect(self._filter_files)
        layout.addWidget(self.search_bar)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        theme_manager.apply_style(
            self.scroll, "QScrollArea { border: none; background: transparent; }"
        )

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(2)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        # Footer
        self.stats_lbl = QLabel("Usage: 0KB / 20KB (0%)")
        theme_manager.apply_style(self.stats_lbl, f"color: {Colors.FG_SECONDARY}; font-size: 10px;")
        layout.addWidget(self.stats_lbl)

    def refresh(self, plugin_id: str, include_core: bool):
        """Populate the sidebar with available documentation files.

        Args:
            plugin_id (str): The ID of the currently active plugin.
            include_core (bool): Whether to show core system documentation.
        """
        self.plugin_id = plugin_id
        self.include_core = include_core

        # Clear current
        for i in reversed(range(self.container_layout.count())):
            item = self.container_layout.takeAt(i)
            if item:
                w = item.widget()
                if w:
                    w.deleteLater()

        # Discover all
        _, docs = self.assistant._gather_context("", plugin_id, include_core, discover_only=True)

        core_docs = [d for d in docs if d["type"] == "core"]
        plugin_docs = [d for d in docs if d["type"] == "plugin"]

        def add_group(title: str, docs_list: list):
            if not docs_list:
                return
            lbl = QLabel(title)
            theme_manager.apply_style(
                lbl,
                f"color: {Colors.ACCENT_PRIMARY}; font-size: 9px; font-weight: bold; margin-top: 5px; background: {Colors.BG_DARKEST}; padding: 2px;",
            )
            self.container_layout.addWidget(lbl)

            pinned = ["01_User_Guide.md", "02_Getting_Started.md", "README.md"]
            for d in sorted(docs_list, key=lambda x: x["name"]):
                name = d["name"]
                size_kb = d["size"] / 1024
                cb = QCheckBox(f"{name} ({size_kb:.1f} KB)")
                cb.setProperty("filename", name)
                cb.setProperty("file_size", d["size"])
                cb.setChecked(name.lower() in [p.lower() for p in pinned])
                theme_manager.apply_style(
                    cb,
                    f"QCheckBox {{ color: {Colors.FG_PRIMARY}; font-size: 11px; padding: 1px; }}",
                )
                cb.stateChanged.connect(self._on_selection_changed)
                self.container_layout.addWidget(cb)

        add_group("🏛 CORE SYSTEM", core_docs)
        add_group(f"🔌 PLUGIN: {plugin_id.upper() if plugin_id else 'NONE'}", plugin_docs)

        self.container_layout.addStretch()
        self._on_selection_changed()
        self.container.adjustSize()

    def _filter_files(self, text):
        text = text.lower()
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, QCheckBox):
                    fn = widget.property("filename")
                    if fn:
                        widget.setVisible(text in fn.lower())

    def _on_selection_changed(self):
        selected_filenames = []
        total_bytes = 0
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, QCheckBox) and widget.isChecked():
                    fn = widget.property("filename")
                    fs = widget.property("file_size")
                    if fn:
                        selected_filenames.append(fn)
                    if fs:
                        total_bytes += fs

        kb_used = total_bytes / 1024
        percent = min(100, (total_bytes / 20000) * 100)
        self.stats_lbl.setText(f"Usage: {kb_used:.1f}KB / 20KB ({percent:.0f}%)")
        theme_manager.apply_style(
            self.stats_lbl,
            f"color: {Colors.ACCENT_PRIMARY if percent < 90 else 'red'}; font-size: 10px;",
        )
        self.selection_changed.emit(selected_filenames)

    def get_selected_files(self):
        """Return a list of filenames currently checked in the UI.

        Returns:
            list[str]: List of filenames to be included in the AI context.
        """
        selected = []
        for i in range(self.container_layout.count()):
            item = self.container_layout.itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, QCheckBox) and widget.isChecked():
                    fn = widget.property("filename")
                    if fn:
                        selected.append(fn)
        return selected
