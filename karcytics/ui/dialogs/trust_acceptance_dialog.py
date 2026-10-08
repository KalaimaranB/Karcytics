"""A high-visibility security dialog for accepting untrusted developer identities."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from karcytics.ui.theme import Colors, theme_manager


class TrustAcceptanceDialog(QDialog):
    """Dialogue for manually adding a developer to local trusted roots."""

    def __init__(self, plugin_id: str, developer_name: str, pub_key_hex: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Security Warning: Untrusted Developer")
        self.setMinimumSize(450, 300)
        theme_manager.apply_style(
            self, f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY};"
        )

        self.plugin_id = plugin_id
        self.developer_name = developer_name
        self.pub_key_hex = pub_key_hex
        self._accepted = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Icon and Title
        header = QHBoxLayout()
        icon_lbl = QLabel("⚠️")
        theme_manager.apply_style(icon_lbl, "font-size: 32px;")
        header.addWidget(icon_lbl)

        title_lbl = QLabel("Independent Developer")
        theme_manager.apply_style(
            title_lbl, f"font-size: 20px; font-weight: 800; color: {Colors.ACCENT_WARNING};"
        )
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        # Description
        desc_lbl = QLabel(
            f"The plugin '<b>{self.plugin_id}</b>' is signed by <b>{self.developer_name}</b>, "
            "but this developer is not currently in your trusted circle."
        )
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Warning Box
        warn_box = QFrame()
        theme_manager.apply_style(
            warn_box,
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.ACCENT_WARNING}55; border-radius: 8px;",
        )
        warn_layout = QVBoxLayout(warn_box)

        key_header = QLabel("PUBLIC KEY IDENTITY")
        theme_manager.apply_style(
            key_header, f"font-size: 9px; font-weight: 800; color: {Colors.FG_SECONDARY};"
        )
        warn_layout.addWidget(key_header)

        key_lbl = QLabel(self.pub_key_hex)
        key_lbl.setWordWrap(True)
        theme_manager.apply_style(
            key_lbl, f"font-family: monospace; font-size: 11px; color: {Colors.FG_PRIMARY};"
        )
        warn_layout.addWidget(key_lbl)

        layout.addWidget(warn_box)

        # Risk Explanation
        risk_lbl = QLabel(
            "Trusting this developer will allow all of their plugins to run on your machine. "
            "Only proceed if you know and trust the source of this code."
        )
        theme_manager.apply_style(risk_lbl, f"font-size: 11px; color: {Colors.FG_SECONDARY};")
        risk_lbl.setWordWrap(True)
        layout.addWidget(risk_lbl)

        layout.addStretch()

        # Buttons
        btns = QHBoxLayout()
        cancel_btn = QPushButton("Not Now")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_manager.apply_style(
            cancel_btn,
            f"background: {Colors.BG_MEDIUM}; border: 1px solid {Colors.BORDER}; padding: 8px 20px; border-radius: 4px;",
        )
        cancel_btn.clicked.connect(self.reject)

        self.trust_btn = QPushButton("Trust this Developer")
        self.trust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_manager.apply_style(
            self.trust_btn,
            f"background: {Colors.ACCENT_SUCCESS}; color: white; font-weight: bold; padding: 8px 24px; border-radius: 4px;",
        )
        self.trust_btn.clicked.connect(self._on_trust_clicked)

        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(self.trust_btn)
        layout.addLayout(btns)

    def _on_trust_clicked(self):
        """Perform the trust save flow."""
        try:
            from karcytics_sdk.host import TrustManager

            manager = TrustManager()
            if manager.trust_developer(self.developer_name, self.pub_key_hex):
                self._accepted = True
                self.accept()
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Error trusting developer: {e}", exc_info=True)
            # Simple error state
            self.trust_btn.setText("Error!")
            self.trust_btn.setEnabled(False)

    def is_accepted(self) -> bool:
        return self._accepted
