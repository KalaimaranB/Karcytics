"""Timeline-style dialog for visualizing the Trust Chain of a plugin."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from karcytics.ui.theme import Colors, theme_manager


class TrustTimelineDialog(QDialog):
    """A sleek dialog showing the hierarchical path of trust."""

    def __init__(self, plugin_name: str, trust_path: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Trust Verification: {plugin_name}")
        self.setMinimumSize(450, 500)
        # Dialog styles handled globally

        self._setup_ui(plugin_name, trust_path)

    def _setup_ui(self, plugin_name: str, trust_path: list):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        # Header
        header = QLabel("🛡️ Path of Trust")
        header.setObjectName("TrustHeader")
        layout.addWidget(header)

        sub = QLabel(f"Verified chain for {plugin_name}")
        sub.setObjectName("TrustSub")
        layout.addWidget(sub)

        # Scroll Area for the Timeline
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("TransparentScroll")

        container = QWidget()
        container.setObjectName("TransparentContainer")
        timeline_layout = QVBoxLayout(container)
        timeline_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)

        # Build Timeline Nodes
        for i, node in enumerate(trust_path):
            node_widget = self._create_node(node, is_last=(i == len(trust_path) - 1))
            timeline_layout.addWidget(node_widget)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 24, 0, 0)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.accept)

        footer.addStretch()
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _create_node(self, node: dict, is_last: bool) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Left Side: Icon and vertical line
        left_col = QVBoxLayout()
        left_col.setSpacing(0)

        icon_lbl = QLabel(self._get_icon_for_status(node["status"]))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setObjectName("TrustIcon")
        theme_manager.apply_style(
            icon_lbl, f"background: {self._get_color_for_status(node['status'])};"
        )

        left_col.addWidget(icon_lbl)

        if not is_last:
            line = QFrame()
            line.setFixedWidth(2)
            line.setObjectName("TrustLine")
            left_col.addWidget(line)
        else:
            left_col.addStretch()

        layout.addLayout(left_col)

        # Right Side: Content
        content = QVBoxLayout()
        content.setContentsMargins(0, 4, 0, 24)
        content.setSpacing(2)

        name_lbl = QLabel(node["name"])
        name_lbl.setObjectName("TrustName")
        content.addWidget(name_lbl)

        status_lbl = QLabel(node["status"].upper())
        status_lbl.setObjectName("TrustStatus")
        theme_manager.apply_style(
            status_lbl, f"color: {self._get_color_for_status(node['status'])};"
        )
        content.addWidget(status_lbl)

        if "key" in node:
            key_lbl = QLabel(f"Key: {node['key'][:16]}...")
            key_lbl.setObjectName("TrustKey")
            content.addWidget(key_lbl)

        content.addStretch()
        layout.addLayout(content)

        return widget

    def _get_icon_for_status(self, status: str) -> str:
        if status == "root":
            return "🏛️"
        if status == "anchor":
            return "⚓"
        if status == "verified":
            return "🛡️"
        return "❓"

    def _get_color_for_status(self, status: str) -> str:
        if status == "root":
            return Colors.ACCENT_PRIMARY
        if status == "anchor":
            return Colors.ACCENT_SUCCESS
        if status == "verified":
            return Colors.ACCENT_SUCCESS
        return Colors.FG_DISABLED
