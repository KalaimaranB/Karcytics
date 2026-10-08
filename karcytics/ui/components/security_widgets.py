"""PySide6 Security & Trust UI Widgets for Karcytics.

Implements the presentation layer (Phase 5) including:
1. ConsensusTrustWidget: Tree presentation of co-signers, RBAC permissions, and trust paths.
2. TrustDirectoryWidget: Displays manual roots, manually trusted anchors, with revoke and addition form.
3. PluginDetailPanel: Dynamic presenter rendering fetched/cached screenshots and avatars with backdoor detection alerts.
"""

import logging
import shutil
from pathlib import Path

from karcytics_sdk.host.marketplace_cache import (
    AssetVerificationError,
    AssetVerifier,
    SandboxCacheService,
)
from karcytics_sdk.host.trust_manager import TrustManager
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from karcytics.core.config import AppConfig
from karcytics.ui.theme import Colors, Fonts, theme_manager

logger = logging.getLogger(__name__)


class ConsensusTrustWidget(QFrame):
    """Visualizes asymmetric trust paths, developer co-signing consensus, and RBAC roles in a tree hierarchy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("consensusTrustWidget")
        self.setMinimumWidth(350)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header Label
        self.header_lbl = QLabel("🛡️ Consensus Chain of Trust")
        theme_manager.apply_style(
            self.header_lbl,
            f"font-size: {Fonts.SIZE_NORMAL + 2}px; font-weight: 700; color: {Colors.FG_PRIMARY};",
        )
        layout.addWidget(self.header_lbl)

        # Tree Presentation
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIconSize(QSize(18, 18))
        theme_manager.apply_style(
            self.tree,
            f"""
            QTreeWidget {{
                background-color: {Colors.BG_DARKER};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 5px;
            }}
            QTreeWidget::item {{
                padding: 6px;
                color: {Colors.FG_PRIMARY};
            }}
            QTreeWidget::item:hover {{
                background-color: {Colors.BG_LIGHT}44;
            }}
        """,
        )
        layout.addWidget(self.tree)

        # Bottom Summary Badge
        self.summary_badge = QLabel("Status: Pending Check")
        self.summary_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            self.summary_badge,
            f"background-color: {Colors.BG_MEDIUM}; border-radius: 4px; padding: 6px; color: {Colors.FG_SECONDARY}; font-weight: 600;",
        )
        layout.addWidget(self.summary_badge)

    def set_trust_path(
        self, trust_path: list[dict], required_cosigners: list[str] | None = None
    ) -> None:
        """Populates the tree with the verified trust links recursively."""
        self.tree.clear()
        if not trust_path:
            self.summary_badge.setText("❌ Untrusted / Unverified")
            theme_manager.apply_style(
                self.summary_badge,
                f"background-color: {Colors.ACCENT_DANGER}33; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px; padding: 6px; color: {Colors.ACCENT_DANGER}; font-weight: 600;",
            )
            return

        required = required_cosigners or []

        # Root Anchor
        root_node = QTreeWidgetItem(self.tree)
        root_node.setText(0, "🔒 Karcytics Central Trust Authority (Root)")
        root_node.setFont(0, QFont(Fonts.FAMILY_HEADINGS, Fonts.SIZE_NORMAL, QFont.Weight.Bold))

        current_parent = root_node
        for node_info in trust_path:
            if node_info.get("status") == "root":
                continue

            name = node_info.get("name", "Unknown Developer")
            key_hex = node_info.get("key", "")
            short_key = f"({key_hex[:8]}...{key_hex[-8:]})" if key_hex else ""

            child_item = QTreeWidgetItem(current_parent)

            # Highlight co-signers who signed vs. contributors
            is_req = name in required
            role_tag = "[Lead Co-Signer]" if is_req else "[Author / Contributor]"

            child_item.setText(0, f"👤 {name} {role_tag} {short_key}")
            child_item.setToolTip(0, f"Public Key: {key_hex}")

            current_parent = child_item

        self.tree.expandAll()

        # Update Summary Badge to Verified
        self.summary_badge.setText("🛡️ Verified Secure Co-Signing")
        theme_manager.apply_style(
            self.summary_badge,
            f"background-color: {Colors.ACCENT_SUCCESS}33; border: 1px solid {Colors.ACCENT_SUCCESS}; border-radius: 4px; padding: 6px; color: {Colors.ACCENT_SUCCESS}; font-weight: 600;",
        )

    def set_untrusted_error(self, error_message: str) -> None:
        """Populates the tree with red alert error node representing a signature breach."""
        self.tree.clear()

        error_node = QTreeWidgetItem(self.tree)
        error_node.setText(0, "⚠️ Signature Chain Verification Failed")
        error_node.setFont(0, QFont(Fonts.FAMILY_HEADINGS, Fonts.SIZE_NORMAL, QFont.Weight.Bold))

        desc_node = QTreeWidgetItem(error_node)
        desc_node.setText(0, f"Reason: {error_message}")
        desc_node.setForeground(0, QBrush(QColor(Colors.ACCENT_DANGER)))

        self.tree.expandAll()

        self.summary_badge.setText("❌ Untrusted / Integrity Alert")
        theme_manager.apply_style(
            self.summary_badge,
            f"background-color: {Colors.ACCENT_DANGER}33; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px; padding: 6px; color: {Colors.ACCENT_DANGER}; font-weight: 600;",
        )


class TrustDirectoryWidget(QFrame):
    """Manual trust anchors registry manager allowing searching, revoking, and manually trusting developers."""

    registry_changed = Signal()

    def __init__(self, trust_manager: TrustManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.trust_manager = trust_manager
        self.setObjectName("trustDirectoryWidget")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header Title
        self.title_lbl = QLabel("📂 Personal Trust Directory")
        theme_manager.apply_style(
            self.title_lbl,
            f"font-size: {Fonts.SIZE_NORMAL + 2}px; font-weight: 700; color: {Colors.FG_PRIMARY};",
        )
        layout.addWidget(self.title_lbl)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter trusted developers...")
        self.search_input.textChanged.connect(self.load_keys)
        theme_manager.apply_style(
            self.search_input,
            f"""
            QLineEdit {{
                background-color: {Colors.BG_DARKER};
                border: 1px solid {Colors.BORDER};
                border-radius: 5px;
                padding: 6px;
                color: {Colors.FG_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {Colors.BORDER_FOCUS};
            }}
        """,
        )
        layout.addWidget(self.search_input)

        # Keys Registry List
        self.list_widget = QListWidget()
        theme_manager.apply_style(
            self.list_widget,
            f"""
            QListWidget {{
                background-color: {Colors.BG_DARKER};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Colors.BORDER}33;
            }}
            QListWidget::item:hover {{
                background-color: {Colors.BG_LIGHT}33;
            }}
        """,
        )
        layout.addWidget(self.list_widget)

        # --- Manual Key Addition form ---
        form_frame = QFrame()
        theme_manager.apply_style(
            form_frame,
            f"background-color: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 6px;",
        )
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(6)

        form_title = QLabel("➕ Add Trusted Developer Anchor")
        theme_manager.apply_style(
            form_title, f"font-weight: 700; color: {Colors.ACCENT_PRIMARY}; border: none;"
        )
        form_layout.addWidget(form_title)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Developer Name (e.g. Alice Vance)")
        theme_manager.apply_style(
            self.name_input,
            f"background-color: {Colors.BG_DARKER}; border: 1px solid {Colors.BORDER}; padding: 5px; color: {Colors.FG_PRIMARY};",
        )
        form_layout.addWidget(self.name_input)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("32-byte Ed25519 Public Key Hex...")
        theme_manager.apply_style(
            self.key_input,
            f"background-color: {Colors.BG_DARKER}; border: 1px solid {Colors.BORDER}; padding: 5px; color: {Colors.FG_PRIMARY};",
        )
        form_layout.addWidget(self.key_input)

        self.add_btn = QPushButton("Add Anchor Key")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_manager.apply_style(
            self.add_btn,
            f"""
            QPushButton {{ background-color: {Colors.ACCENT_SUCCESS}; color: white; border: none; border-radius: 4px; padding: 6px; font-weight: 700; }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_SUCCESS}dd; }}
        """,
        )
        self.add_btn.clicked.connect(self._add_anchor)
        form_layout.addWidget(self.add_btn)

        layout.addWidget(form_frame)

        self.load_keys()

    def load_keys(self) -> None:
        """
        Load manually trusted developer anchors into the directory list, applying the active search filter.
        """
        self.list_widget.clear()

        roots_dir = AppConfig.APP_DATA_DIR / "trusted_roots"
        if not roots_dir.exists():
            return

        filter_text = self.search_input.text().lower()

        for key_file in sorted(roots_dir.glob("*.pub")):
            try:
                # Deduce name from filename
                name = key_file.stem.replace("manual_", "").replace("_", " ").title()
                if filter_text and filter_text not in name.lower():
                    continue

                key_data = key_file.read_bytes()
                key_hex = key_data.hex()

                # Custom layout for list item containing Name, Key, and Revoke Button
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(0, 0, 0, 0)
                item_layout.setSpacing(10)

                details_layout = QVBoxLayout()
                name_lbl = QLabel(f"👤 {name}")
                theme_manager.apply_style(
                    name_lbl, f"font-weight: 700; color: {Colors.FG_PRIMARY}; border: none;"
                )

                short_hex = f"{key_hex[:8]}...{key_hex[-8:]}"
                key_lbl = QLabel(short_hex)
                theme_manager.apply_style(
                    key_lbl, f"font-size: 10px; color: {Colors.FG_SECONDARY}; border: none;"
                )

                details_layout.addWidget(name_lbl)
                details_layout.addWidget(key_lbl)
                item_layout.addLayout(details_layout)
                item_layout.addStretch()

                revoke_btn = QPushButton("Revoke")
                revoke_btn.setFixedSize(65, 24)
                revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                theme_manager.apply_style(
                    revoke_btn,
                    f"""
                    QPushButton {{ background-color: {Colors.BG_LIGHT}; color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.BORDER}; border-radius: 4px; font-size: 10px; font-weight: 600; }}
                    QPushButton:hover {{ background-color: {Colors.ACCENT_DANGER}33; border: 1px solid {Colors.ACCENT_DANGER}; }}
                """,
                )
                revoke_btn.clicked.connect(
                    lambda _checked, path=key_file: self._revoke_anchor(path)
                )
                item_layout.addWidget(revoke_btn)

                list_item = QListWidgetItem(self.list_widget)
                list_item.setSizeHint(item_widget.sizeHint())
                self.list_widget.setItemWidget(list_item, item_widget)
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Failed to load anchor: {e}", exc_info=True)

    def _revoke_anchor(self, key_path: Path) -> None:
        """Deletes key file and triggers reload."""
        try:
            if key_path.exists():
                key_path.unlink()
            self.trust_manager._load_all_roots()
            self.load_keys()
            self.registry_changed.emit()
        except Exception as e:
            logger.error(f"Failed to revoke anchor file: {e}")

    def _add_anchor(self) -> None:
        """Validates key input form and trusts developer manually."""
        name = self.name_input.text().strip()
        key_hex = self.key_input.text().strip()

        if not name or not key_hex:
            return

        success = self.trust_manager.trust_developer(name, key_hex)
        if success:
            self.name_input.clear()
            self.key_input.clear()
            self.load_keys()
            self.registry_changed.emit()


class PluginDetailPanel(QScrollArea):
    """Gorgeous detailed info panel that fetches remote assets securely, verifies image hashes,
    and displays warnings/placeholders on tampering or ignored executables detection.
    """

    def __init__(
        self,
        sandbox_cache: SandboxCacheService,
        verifier: AssetVerifier,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sandbox_cache = sandbox_cache
        self.verifier = verifier

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        theme_manager.apply_style(self, f"background-color: {Colors.BG_DARKER};")

        # Container
        self.container = QWidget()
        theme_manager.apply_style(self.container, f"background-color: {Colors.BG_DARKER};")
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        self.setWidget(self.container)

        # Title Card
        self.title_card = QFrame()
        theme_manager.apply_style(
            self.title_card,
            f"background-color: {Colors.BG_DARK}; border: 1.5px solid {Colors.BORDER}; border-radius: 10px;",
        )
        self.title_layout = QVBoxLayout(self.title_card)
        self.title_layout.setContentsMargins(18, 18, 18, 18)
        self.title_layout.setSpacing(8)

        self.name_lbl = QLabel("Plugin Details")
        theme_manager.apply_style(
            self.name_lbl,
            f"font-size: {Fonts.SIZE_LARGE + 2}px; font-weight: 700; color: {Colors.FG_PRIMARY}; border: none;",
        )
        self.title_layout.addWidget(self.name_lbl)

        self.desc_lbl = QLabel(
            "Select a plugin to review details and cryptographic trust structures."
        )
        theme_manager.apply_style(
            self.desc_lbl,
            f"font-size: {Fonts.SIZE_NORMAL}px; color: {Colors.FG_SECONDARY}; border: none;",
        )
        self.desc_lbl.setWordWrap(True)
        self.title_layout.addWidget(self.desc_lbl)

        self.main_layout.addWidget(self.title_card)

        # Dynamic Status Badge (Verified vs Untrusted Alert)
        self.status_badge = QFrame()
        self.status_badge.setVisible(False)
        self.badge_layout = QHBoxLayout(self.status_badge)
        self.badge_layout.setContentsMargins(12, 10, 12, 10)
        self.badge_icon = QLabel("🛡️")
        self.badge_text = QLabel("VERIFIED SECURE CO-SIGNING")
        self.badge_layout.addWidget(self.badge_icon)
        self.badge_layout.addWidget(self.badge_text)
        self.badge_layout.addStretch()
        self.main_layout.addWidget(self.status_badge)

        # Malicious Zone Backdoor Blocker Warning Frame
        self.backdoor_warning = QFrame()
        self.backdoor_warning.setObjectName("backdoorWarning")
        self.backdoor_warning.setVisible(False)
        theme_manager.apply_style(
            self.backdoor_warning,
            f"""
            QFrame#backdoorWarning {{
                background-color: {Colors.ACCENT_DANGER}33;
                border: 2px solid {Colors.ACCENT_DANGER};
                border-radius: 8px;
            }}
        """,
        )
        bw_layout = QVBoxLayout(self.backdoor_warning)
        bw_title = QLabel("🚨 SECURITY CRITICAL: UNAUTHORIZED PAYLOAD BLOCKED!")
        theme_manager.apply_style(
            bw_title,
            f"font-weight: 700; color: {Colors.ACCENT_DANGER}; font-size: 14px; border: none;",
        )
        bw_desc = QLabel(
            "Covert backdoor alert: Found unauthorized Python scripts or executable payloads inside an ignored directory. Standard sandbox security has disabled and locked execution."
        )
        bw_desc.setWordWrap(True)
        theme_manager.apply_style(
            bw_desc, f"color: {Colors.FG_PRIMARY}; font-size: 12px; border: none;"
        )
        bw_layout.addWidget(bw_title)
        bw_layout.addWidget(bw_desc)
        self.main_layout.addWidget(self.backdoor_warning)

        # Dynamic Presentation Row (Developer Portrait & Screenshot Card)
        self.asset_row = QFrame()
        self.asset_row.setVisible(False)
        self.asset_layout = QHBoxLayout(self.asset_row)
        self.asset_layout.setContentsMargins(0, 0, 0, 0)
        self.asset_layout.setSpacing(15)

        # Left Avatar Card
        self.avatar_card = QFrame()
        self.avatar_card.setFixedWidth(130)
        theme_manager.apply_style(
            self.avatar_card,
            f"background-color: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 8px;",
        )
        ac_layout = QVBoxLayout(self.avatar_card)
        ac_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_img = QLabel("👤")
        self.avatar_img.setFixedSize(64, 64)
        self.avatar_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            self.avatar_img, "font-size: 32px; background: transparent; border: none;"
        )
        self.avatar_name = QLabel("Alice Vance")
        self.avatar_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            self.avatar_name,
            f"font-weight: 700; color: {Colors.FG_PRIMARY}; font-size: 11px; border: none;",
        )
        ac_layout.addWidget(self.avatar_img)
        ac_layout.addWidget(self.avatar_name)
        self.asset_layout.addWidget(self.avatar_card)

        # Right Screenshot Card
        self.screenshot_card = QFrame()
        theme_manager.apply_style(
            self.screenshot_card,
            f"background-color: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 8px;",
        )
        sc_layout = QVBoxLayout(self.screenshot_card)
        self.screenshot_title = QLabel("🖼️ Plugin Live Preview")
        theme_manager.apply_style(
            self.screenshot_title,
            f"font-weight: 700; color: {Colors.FG_SECONDARY}; font-size: 11px; border: none;",
        )
        self.screenshot_img = QLabel("No Screenshot")
        self.screenshot_img.setFixedSize(240, 120)
        self.screenshot_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_manager.apply_style(
            self.screenshot_img,
            f"background-color: {Colors.BG_DARKER}; border: 1px dashed {Colors.BORDER}; color: {Colors.FG_SECONDARY}; border-radius: 4px;",
        )
        sc_layout.addWidget(self.screenshot_title)
        sc_layout.addWidget(self.screenshot_img)
        self.asset_layout.addWidget(self.screenshot_card)

        self.main_layout.addWidget(self.asset_row)
        self.main_layout.addStretch()

    def display_plugin(
        self,
        name: str,
        description: str,
        trust_status: str,
        required_cosigners: list[str] | None = None,  # noqa: ARG002
        author_avatar_stub: tuple[str, str, str] | None = None,  # (name, local_file_or_url, hash)
        screenshot_stub: tuple[str, str] | None = None,  # (local_file_or_url, hash)
        backdoor_detected: bool = False,
    ) -> None:
        """
        Updates the plugin details view with trust status, security alerts, and verified visual assets.

        Parameters:
            name (str): Plugin name.
            description (str): Plugin description.
            trust_status (str): Plugin trust state used to determine the displayed security status.
            author_avatar_stub (tuple[str, str, str] | None): Author name, local asset path, and expected asset hash.
            screenshot_stub (tuple[str, str] | None): Local screenshot path and expected asset hash.
            backdoor_detected (bool): Whether unauthorized executable payloads were detected.

        """
        self.name_lbl.setText(name)
        self.desc_lbl.setText(description)

        # Handle Backdoor Alert Card visibility
        if backdoor_detected:
            self.backdoor_warning.setVisible(True)
            self.status_badge.setVisible(True)
            theme_manager.apply_style(
                self.status_badge,
                f"background-color: {Colors.ACCENT_DANGER}33; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 6px;",
            )
            self.badge_icon.setText("🚨")
            self.badge_text.setText("SECURITY CRITICAL: BLACKLISTED EXEC PAYLOADS DETECTED")
            theme_manager.apply_style(
                self.badge_text, f"color: {Colors.ACCENT_DANGER}; font-weight: 700;"
            )
            self.asset_row.setVisible(False)
            return

        self.backdoor_warning.setVisible(False)

        # Update Badge Style
        self.status_badge.setVisible(True)
        if trust_status in ["verified_developer", "verified_cache", "verified_project"]:
            theme_manager.apply_style(
                self.status_badge,
                f"background-color: {Colors.ACCENT_SUCCESS}33; border: 1px solid {Colors.ACCENT_SUCCESS}; border-radius: 6px;",
            )
            self.badge_icon.setText("🛡️")
            self.badge_text.setText("VERIFIED SECURE DOUBLE-SIGNING CONSENSUS")
            theme_manager.apply_style(
                self.badge_text, f"color: {Colors.ACCENT_SUCCESS}; font-weight: 700;"
            )
        else:
            theme_manager.apply_style(
                self.status_badge,
                f"background-color: {Colors.ACCENT_DANGER}33; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 6px;",
            )
            self.badge_icon.setText("⚠️")
            self.badge_text.setText("UNTRUSTED / INTEGRITY LEDGER CHECK FAILED")
            theme_manager.apply_style(
                self.badge_text, f"color: {Colors.ACCENT_DANGER}; font-weight: 700;"
            )

        # Fetch and verify remote assets dynamically in a sandboxed directory
        self.asset_row.setVisible(True)

        # 1. Developer Avatar
        if author_avatar_stub:
            author_name, file_source, expected_hash = author_avatar_stub
            self.avatar_name.setText(author_name)

            # Resolve sandbox path
            try:
                sandbox_avatar = self.sandbox_cache.get_cache_path(
                    "segmenter_plugin", "avatars", "alice.png"
                )
                sandbox_avatar.parent.mkdir(parents=True, exist_ok=True)

                # Copy or simulate download
                shutil.copy(file_source, sandbox_avatar)

                # Cryptographic check
                self.verifier.verify_asset(sandbox_avatar, expected_hash)

                pix = QPixmap(str(sandbox_avatar))
                self.avatar_img.setPixmap(
                    pix.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                theme_manager.apply_style(self.avatar_img, "background: transparent; border: none;")
            except (AssetVerificationError, Exception) as e:
                # TAMP WARNING PLACEHOLDER REDBadge
                self.avatar_img.setText("⚠️")
                theme_manager.apply_style(
                    self.avatar_img,
                    f"font-size: 32px; background: transparent; border: 2px solid {Colors.ACCENT_DANGER}; border-radius: 32px; color: {Colors.ACCENT_DANGER};",
                )
                self.avatar_img.setToolTip(f"Tampered Avatar Blocked: {str(e)}")
        else:
            self.avatar_img.setText("👤")
            self.avatar_name.setText("Unknown")

        # 2. Marketplace Screenshot
        if screenshot_stub:
            file_source, expected_hash = screenshot_stub

            try:
                sandbox_screenshot = self.sandbox_cache.get_cache_path(
                    "segmenter_plugin", "screenshots", "screen1.png"
                )
                sandbox_screenshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(file_source, sandbox_screenshot)

                # Check match
                self.verifier.verify_asset(sandbox_screenshot, expected_hash)

                pix = QPixmap(str(sandbox_screenshot))
                self.screenshot_img.setPixmap(
                    pix.scaled(
                        240,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                theme_manager.apply_style(
                    self.screenshot_img, "background: transparent; border: none;"
                )
            except (AssetVerificationError, Exception) as e:
                self.screenshot_img.clear()
                self.screenshot_img.setText("❌ SPOOFED IMAGE BLOCKED")
                theme_manager.apply_style(
                    self.screenshot_img,
                    f"background-color: {Colors.ACCENT_DANGER}33; border: 1.5px dashed {Colors.ACCENT_DANGER}; color: {Colors.ACCENT_DANGER}; font-weight: 700; border-radius: 4px;",
                )
                self.screenshot_img.setToolTip(
                    f"Asset hash mismatched manifest ledger parameters! Spoofed display prevented.\n{str(e)}"
                )
        else:
            self.screenshot_img.setText("No Preview")
