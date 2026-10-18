"""Reusable UI Cards for Karcytics."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from karcytics.ui.theme import Colors, Fonts, theme_manager


class ModuleCard(QFrame):
    """Clickable card representing one analysis module."""

    clicked = Signal()
    trust_requested = Signal()
    trust_visual_requested = Signal()

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        badge: str = "",
        enabled: bool = True,
        trust_level: str = "verified",
        trust_path: list | None = None,
        developer_name: str | None = None,
        developer_key: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._enabled = enabled
        self._trust_level = trust_level
        self._trust_path = trust_path
        self._developer_name = developer_name
        self._developer_key = developer_key
        self._title = title
        self.setObjectName("moduleCard")
        # Generate a unique tutorial_id based on the title so specific cards can be spotlighted
        safe_title = title.lower().replace(" ", "_")
        self.setProperty("tutorial_id", f"module_card_{safe_title}")

        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.setMinimumSize(260, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        theme_manager.apply_style(icon_lbl, "font-size: 26px; background: transparent;")
        top_row.addWidget(icon_lbl)
        top_row.addStretch()

        if badge:
            badge_lbl = QLabel(badge)
            theme_manager.apply_style(
                badge_lbl,
                f"background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST}; border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: 700;",
            )
            top_row.addWidget(badge_lbl)

        # Add Trust Indicator
        self.lock_btn = QPushButton()
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_btn.clicked.connect(self._on_lock_clicked)
        self._update_trust_ui()
        top_row.addWidget(self.lock_btn)

        if not enabled:
            soon_lbl = QLabel("Coming soon")
            theme_manager.apply_style(
                soon_lbl,
                f"background: {Colors.BG_LIGHT}; color: {Colors.FG_DISABLED}; border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: 600;",
            )
            top_row.addWidget(soon_lbl)

        layout.addLayout(top_row)

        self.title_lbl = QLabel(title)
        theme_manager.apply_style(
            self.title_lbl,
            f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 700; color: {Colors.FG_PRIMARY if enabled else Colors.FG_DISABLED}; background: transparent;",
        )
        self.title_lbl.setWordWrap(True)
        layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(description)
        theme_manager.apply_style(
            self.desc_lbl,
            f"font-size: {Fonts.SIZE_SMALL}px; color: {Colors.FG_SECONDARY}; background: transparent;",
        )
        self.desc_lbl.setWordWrap(True)
        layout.addWidget(self.desc_lbl)

        layout.addStretch()
        self._apply_style(False)

    def _update_trust_ui(self):
        """Update the lock icon and style based on trust level."""
        if self._trust_level in ["verified_developer", "verified_cache", "verified_project"]:
            self.lock_btn.setText("🛡️")
            self.lock_btn.setToolTip("Verified via Trust Tree. Click to view chain.")
            theme_manager.apply_style(
                self.lock_btn, "background: transparent; border: none; font-size: 14px;"
            )
        elif self._trust_level == "verified_local":
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("Verified Local Override (Manual Lock). Click to view.")
            theme_manager.apply_style(
                self.lock_btn,
                f"background: transparent; border: none; font-size: 14px; color: {Colors.ACCENT_SUCCESS};",
            )
        else:
            self.lock_btn.setText("⚠️")
            self.lock_btn.setToolTip("Modified or Untrusted! Click to verify and lock.")
            theme_manager.apply_style(
                self.lock_btn,
                f"background: transparent; border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px; font-size: 14px;",
            )

    def _on_lock_clicked(self):
        """Logic for when the trust icon is clicked."""
        if self._trust_level == "untrusted":
            if self._developer_key and self._developer_name:
                from karcytics.ui.dialogs.trust_acceptance_dialog import TrustAcceptanceDialog

                dialog = TrustAcceptanceDialog(
                    self._title, self._developer_name, self._developer_key, self
                )
                if dialog.exec() and dialog.is_accepted():
                    # Update card state instantly
                    self._trust_level = "verified_local"
                    self._trust_path = [
                        {"name": "Local System User", "status": "root", "key": "Manual Override"},
                        {
                            "name": "Security Check Bypassed",
                            "status": "anchor",
                            "key": "Local Machine Policy",
                        },
                    ]
                    self._update_trust_ui()
                    self._apply_style(False)
            else:
                self.trust_requested.emit()
        else:
            # Show the visual tree!
            from karcytics.ui.dialogs.trust_dialog import TrustTimelineDialog

            dialog = TrustTimelineDialog(self._title, self._trust_path or [], self)
            dialog.exec()

    def _apply_style(self, hovered: bool) -> None:
        """
        Apply the card's visual styling for its enabled, disabled, hovered, and trust states.

        Parameters:
            hovered (bool): Whether the card is currently hovered.
        """
        if not self._enabled:
            theme_manager.apply_style(
                self,
                f"QFrame#moduleCard {{ background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 10px; }}",
            )
            return

        # Highlight border if untrusted
        if self._trust_level == "untrusted":
            border = Colors.ACCENT_DANGER if hovered else Colors.ACCENT_DANGER + "88"
        else:
            border = Colors.ACCENT_PRIMARY if hovered else Colors.BORDER

        bg = Colors.BG_MEDIUM if hovered else Colors.BG_DARK
        theme_manager.apply_style(
            self,
            f"QFrame#moduleCard {{ background: {bg}; border: 1.5px solid {border}; border-radius: 10px; }}",
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        """Apply the hovered style when the card is enabled."""
        if self._enabled:
            self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """
        Restore the card's default styling when the pointer leaves it.
        """
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """
        Emit the card's click signal when the card is enabled.

        Parameters:
                event: The mouse press event to pass to the base widget implementation.
        """
        if self._enabled:
            self.clicked.emit()
        super().mousePressEvent(event)


def academy_workflow_label(academy: dict | None) -> str | None:
    """The 🎓 pill text for an Academy workflow, from its metadata's ``academy`` block.

    A plugin running Academy courses inside a workflow keeps that block in
    the workflow's metadata (state, course number, progress), so the Hub
    can show where the learner is without starting the plugin. None for an
    ordinary workflow.
    """
    if not isinstance(academy, dict):
        return None
    state = academy.get("state")
    number = academy.get("course_number")
    count = academy.get("course_count")
    if state in ("running", "paused"):
        total = academy.get("step_total") or 0
        percent = f" · {round(100 * (academy.get('step_number') or 0) / total)}%" if total else ""
        status = "In progress" if state == "running" else "Paused"
        return f"🎓 Course {number} · {status}{percent}" if number else f"🎓 Academy · {status}"
    if state == "between_courses":
        done = academy.get("completed_count") or len(academy.get("completed_courses") or [])
        return f"🎓 {done} of {count} courses done" if count else "🎓 Academy"
    if state == "graduated":
        return "🎓 Academy · all courses done"
    return "🎓 Academy"


class DashboardWorkflowCard(QFrame):
    """Clickable card representing a saved workflow with a settings button.

    When ``has_academy=True`` the card shows a 🎓 pill badge and a subtle blue
    left-border accent.  Clicking the pill emits ``academy_requested`` (independent
    from the card's main ``clicked`` signal).

    An Academy workflow (``academy`` is its metadata's ``academy`` block)
    shows its course status instead — "🎓 Course 2 · Paused · 38%" — in
    place of the course-count pill, with the same accent.
    """

    clicked = Signal()
    settings_requested = Signal()
    academy_requested = Signal()
    rename_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()

    def __init__(
        self,
        title: str,
        date_str: str,
        module_name: str,
        description: str = "",
        tags: list[str] = None,
        has_academy: bool = False,
        course_count: int = 0,
        academy: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        academy_label = academy_workflow_label(academy)
        self._has_academy = has_academy or academy_label is not None
        self.setObjectName("workflowCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Top row: Module Name, Academy pill (optional), and Settings Button
        top_row = QHBoxLayout()
        mod_lbl = QLabel(module_name)
        theme_manager.apply_style(
            mod_lbl,
            f"font-size: 10px; font-weight: bold; color: {Colors.ACCENT_PRIMARY}; background: transparent; text-transform: uppercase;",
        )
        top_row.addWidget(mod_lbl)
        top_row.addStretch()

        # Academy badge pill — shown only when courses are registered for this module
        self._academy_btn: QPushButton | None = None
        self.academy_status_lbl: QLabel | None = None
        if academy_label is not None:
            self.academy_status_lbl = QLabel(academy_label)
            self.academy_status_lbl.setObjectName("workflowAcademyStatus")
            course_title = academy.get("course_title") if isinstance(academy, dict) else None
            self.academy_status_lbl.setToolTip(
                f"Academy workflow — {course_title}" if course_title else "Academy workflow"
            )
            theme_manager.apply_style(
                self.academy_status_lbl,
                "background: rgba(31, 111, 235, 0.18); color: #79c0ff;"
                " border: 1px solid #1f6feb; border-radius: 8px;"
                " padding: 1px 7px; font-size: 10px; font-weight: bold;",
            )
            top_row.addWidget(self.academy_status_lbl)
        elif has_academy:
            label = (
                f"🎓 {course_count} course" if course_count == 1 else f"🎓 {course_count} courses"
            )
            self._academy_btn = QPushButton(label)
            self._academy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            theme_manager.apply_style(
                self._academy_btn,
                "QPushButton {"
                "  background: rgba(31, 111, 235, 0.18);"
                "  color: #79c0ff;"
                "  border: 1px solid #1f6feb;"
                "  border-radius: 8px;"
                "  padding: 1px 7px;"
                "  font-size: 10px;"
                "  font-weight: bold;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(31, 111, 235, 0.35);"
                "}",
            )
            self._academy_btn.clicked.connect(self._on_academy_clicked)
            top_row.addWidget(self._academy_btn)

        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setFixedSize(24, 24)
        theme_manager.apply_style(
            self.btn_settings,
            f"""
            QPushButton {{ background: transparent; border: none; border-radius: 4px; font-size: 14px; }}
            QPushButton:hover {{ background: {Colors.BG_LIGHT}; border: 1px solid {Colors.BORDER}; }}
        """,
        )
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        top_row.addWidget(self.btn_settings)
        layout.addLayout(top_row)

        self.title_lbl = QLabel(title)
        theme_manager.apply_style(
            self.title_lbl,
            f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 700; color: {Colors.FG_PRIMARY}; background: transparent;",
        )
        self.title_lbl.setWordWrap(True)
        layout.addWidget(self.title_lbl)

        if description:
            self.desc_lbl = QLabel(description)
            theme_manager.apply_style(
                self.desc_lbl,
                f"font-size: 11px; color: {Colors.FG_SECONDARY}; background: transparent;",
            )
            self.desc_lbl.setWordWrap(True)
            layout.addWidget(self.desc_lbl)

        if tags:
            tag_str = "  ".join([f"#{t}" for t in tags])
            self.tag_lbl = QLabel(tag_str)
            theme_manager.apply_style(
                self.tag_lbl,
                f"color: {Colors.FG_SECONDARY}; font-size: 11px; font-style: italic; background: transparent;",
            )
            self.tag_lbl.setWordWrap(True)
            layout.addWidget(self.tag_lbl)

        self.date_lbl = QLabel(f"Saved: {date_str}")
        theme_manager.apply_style(
            self.date_lbl,
            f"font-size: 10px; color: {Colors.FG_SECONDARY}; background: transparent;",
        )
        layout.addWidget(self.date_lbl)

        layout.addStretch()
        self._apply_style(False)

    def _on_settings_clicked(self) -> None:
        self.settings_requested.emit()

    def _on_academy_clicked(self) -> None:
        """Emits academy_requested without also triggering the card's main click."""
        self.academy_requested.emit()

    def _apply_style(self, hovered: bool) -> None:
        """Apply the card's background and border styling for its hover state."""
        if self._has_academy:
            # Blue left-border accent when academy courses are available
            border_left = "#1f6feb"
            border = "#1f6feb" if hovered else "#1f6feb88"
            bg = Colors.BG_MEDIUM if hovered else Colors.BG_DARK
            theme_manager.apply_style(
                self,
                f"QFrame#workflowCard {{"
                f"  background: {bg};"
                f"  border: 1px solid {border};"
                f"  border-left: 3px solid {border_left};"
                f"  border-radius: 8px;"
                f"}}",
            )
        else:
            border = Colors.FG_SECONDARY if hovered else Colors.BORDER
            bg = Colors.BG_MEDIUM if hovered else Colors.BG_DARK
            theme_manager.apply_style(
                self,
                f"QFrame#workflowCard {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}",
            )

    def enterEvent(self, event) -> None:  # noqa: N802
        """
        Apply the hovered styling when the pointer enters the card.

        Parameters:
                event: The pointer-enter event.
        """
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """
        Restore the card's default styling when the pointer leaves it.
        """
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Handle card clicks while excluding clicks on overlay buttons.

        Only left-button presses emit ``clicked``; right-button presses are
        left to ``contextMenuEvent`` so the context menu never also opens the
        workflow.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.position().toPoint()
        # Ignore clicks on overlay buttons — they handle their own signals
        if self.btn_settings.geometry().contains(pos):
            super().mousePressEvent(event)
            return
        if self._academy_btn and self._academy_btn.geometry().contains(pos):
            super().mousePressEvent(event)
            return
        self.clicked.emit()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Show a right-click context menu with Rename, Duplicate, and Delete actions.

        Parameters:
            event: The context-menu event carrying the global cursor position.
        """
        menu = QMenu(self)
        theme_manager.apply_style(
            menu,
            f"""
            QMenu {{
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 4px 0px;
                color: {Colors.FG_PRIMARY};
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Colors.BORDER};
                margin: 3px 8px;
            }}
            """,
        )

        act_rename = QAction("✏️  Rename", self)
        act_rename.triggered.connect(self.rename_requested.emit)
        menu.addAction(act_rename)

        act_duplicate = QAction("📋  Duplicate Workflow", self)
        act_duplicate.triggered.connect(self.duplicate_requested.emit)
        menu.addAction(act_duplicate)

        menu.addSeparator()

        act_delete = QAction("🗑️  Delete Workflow", self)
        act_delete.triggered.connect(self.delete_requested.emit)
        menu.addAction(act_delete)

        menu.exec(event.globalPos())


class DetailedWorkflowCard(QFrame):
    """A visual card representing a saved workflow with tags and load button."""

    def __init__(self, metadata: dict, on_load_callback):
        super().__init__()
        self.metadata = metadata
        self.setFrameShape(QFrame.Shape.StyledPanel)

        theme_manager.apply_style(
            self,
            f"QFrame {{ "
            f"  background-color: {Colors.BG_MEDIUM}; "
            f"  border: 1px solid {Colors.BORDER}; "
            f"  border-radius: 8px; "
            f"  margin: 4px; "
            f"}}",
        )

        layout = QVBoxLayout(self)

        # Header: Name and Module Tag
        header = QHBoxLayout()
        name_lbl = QLabel(metadata.get("name", "Untitled"))
        theme_manager.apply_style(
            name_lbl,
            f"font-weight: bold; font-size: 14px; color: {Colors.FG_PRIMARY}; border: none;",
        )

        mod_lbl = QLabel(metadata.get("module", "").replace("_", " ").upper())
        theme_manager.apply_style(
            mod_lbl,
            f"color: {Colors.ACCENT_PRIMARY}; "
            f"font-size: 10px; "
            f"font-weight: bold; "
            f"border: 1px solid {Colors.ACCENT_PRIMARY}; "
            f"border-radius: 4px; "
            f"padding: 2px 4px;",
        )

        header.addWidget(name_lbl)
        header.addStretch()
        header.addWidget(mod_lbl)
        layout.addLayout(header)

        # Description
        desc = QLabel(metadata.get("description", "No description provided."))
        desc.setWordWrap(True)
        theme_manager.apply_style(desc, f"color: {Colors.FG_SECONDARY}; border: none;")
        layout.addWidget(desc)

        # Tags
        tags = metadata.get("tags", [])
        if tags:
            tag_str = "  ".join([f"#{t}" for t in tags])
            tag_lbl = QLabel(tag_str)
            theme_manager.apply_style(
                tag_lbl,
                f"color: {Colors.FG_SECONDARY}; font-size: 11px; font-style: italic; border: none;",
            )
            layout.addWidget(tag_lbl)

        # Load Button
        self.btn_load = QPushButton("Open Workflow")
        self.btn_load.setCursor(header.itemAt(0).widget().cursor())  # Safety for cursor
        self.btn_load.clicked.connect(lambda: on_load_callback(metadata))
        layout.addWidget(self.btn_load)
