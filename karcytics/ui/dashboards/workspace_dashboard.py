"""Workspace Dashboard (Home Screen inside Workspace) for Karcytics."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from karcytics.ui.components.cards import DashboardWorkflowCard as WorkflowCard
from karcytics.ui.components.cards import ModuleCard
from karcytics.ui.theme import Colors, Fonts, theme_manager
from karcytics.ui.widgets.dna_loader import ProgrammaticLoader


class WorkspaceDashboard(QWidget):
    """Welcome / dashboard screen."""

    module_selected = Signal(object)  # Passes manifest
    workflow_selected = Signal(str, str)  # Passes (module_id, filename)
    workflow_settings_requested = Signal(str, str)  # Passes (module_id, filename)
    open_academy_for_module_requested = Signal(str)  # Passes module_id

    return_to_hub_requested = Signal()
    open_store_requested = Signal()
    open_ai_requested = Signal()
    open_academy_requested = Signal()
    trust_module_requested = Signal(str)  # Passes module_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Hero banner ───────────────────────────────────────────────
        hero = QWidget()
        hero.setObjectName("heroWidget")
        theme_manager.apply_style(
            hero,
            f"QWidget#heroWidget {{ background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER}; }}",
        )

        # FIX: Changed from Fixed to Minimum to allow the container to grow with the new text elements
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        hero_layout = QVBoxLayout(hero)
        # FIX: Generous margins and spacing to prevent vertical crowding
        hero_layout.setContentsMargins(56, 48, 56, 40)
        hero_layout.setSpacing(12)

        # 1. Title Row (Logo + Buttons)
        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Replacing static logo with high-fidelity DNA animation
        self.logo_animation = ProgrammaticLoader()
        self.logo_animation.setFixedSize(100, 100)  # Compact for the header
        title_row.addWidget(self.logo_animation)

        name = QLabel("Karcytics™")
        theme_manager.apply_style(
            name,
            f"font-size: 34px; font-weight: 800; color: {Colors.FG_PRIMARY}; background: transparent; letter-spacing: -1px;",
        )
        title_row.addWidget(name)
        title_row.addStretch()

        title_row.addSpacing(20)
        self.btn_store = QPushButton("☁️ Store")
        self.btn_store.setObjectName("btn_store")
        theme_manager.apply_style(
            self.btn_store,
            f"QPushButton {{ background: transparent; border: 1px solid {Colors.BORDER}; border-radius: 5px; padding: 6px 14px; color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px; }}"
            f"QPushButton:hover {{ background: {Colors.BG_MEDIUM}; border-color: {Colors.ACCENT_PRIMARY}; }}",
        )
        self.btn_store.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_store.clicked.connect(self.open_store_requested.emit)
        title_row.addWidget(self.btn_store)

        # AI Chat feature is currently in the works - UI hidden for now
        # title_row.addSpacing(10)
        # self.btn_ai = QPushButton("🧠 AI Chat")
        # self.btn_ai.setObjectName("btn_ai")
        # theme_manager.apply_style(
        #     self.btn_ai,
        #     f"QPushButton {{ background: transparent; border: 1px solid {Colors.BORDER}; border-radius: 5px; padding: 6px 14px; color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px; }}"
        #     f"QPushButton:hover {{ background: {Colors.BG_MEDIUM}; border-color: {Colors.ACCENT_PRIMARY}; }}",
        # )
        # self.btn_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.btn_ai.clicked.connect(self.open_ai_requested.emit)
        # title_row.addWidget(self.btn_ai)

        title_row.addSpacing(10)
        self.btn_academy = QPushButton("🎓 Academy")
        self.btn_academy.setObjectName("btn_academy")
        theme_manager.apply_style(
            self.btn_academy,
            f"QPushButton {{ background: transparent; border: 1px solid {Colors.BORDER}; border-radius: 5px; padding: 6px 14px; color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px; }}"
            f"QPushButton:hover {{ background: {Colors.BG_MEDIUM}; border-color: #58a6ff; }}",
        )
        self.btn_academy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_academy.clicked.connect(self.open_academy_requested.emit)
        title_row.addWidget(self.btn_academy)

        self.btn_return_hub = QPushButton("🏠 Return to Project Hub")
        theme_manager.apply_style(
            self.btn_return_hub,
            f"QPushButton {{"
            f"  background: {Colors.BG_MEDIUM}; border: 1px solid {Colors.BORDER};"
            f"  border-radius: 5px; padding: 6px 14px; margin-left: 20px;"
            f"  color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST};"
            f"}}",
        )
        self.btn_return_hub.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_return_hub.clicked.connect(self.return_to_hub_requested.emit)
        title_row.addWidget(self.btn_return_hub)

        hero_layout.addLayout(title_row)

        # 2. Greeting Row
        # Added intentional spacing between the title row and the greeting
        hero_layout.addSpacing(4)

        self.lbl_greeting = QLabel("Good morning.")
        theme_manager.apply_style(
            self.lbl_greeting,
            f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 600; color: {Colors.FG_PRIMARY};",
        )
        hero_layout.addWidget(self.lbl_greeting)

        # 3. Tagline Row
        self.lbl_tagline = QLabel("Bio Analysis Made Simple — designed for modern lab workflows")
        theme_manager.apply_style(
            self.lbl_tagline,
            f"font-size: {Fonts.SIZE_NORMAL}px; color: {Colors.FG_SECONDARY}; background: transparent;",
        )
        hero_layout.addWidget(self.lbl_tagline)

        # 4. Stats Pill Row
        stats_layout = QHBoxLayout()
        self.stat_modules = QLabel("0 Modules Active")
        theme_manager.apply_style(
            self.stat_modules,
            f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; border: 1px solid {Colors.BORDER}; "
            f"padding: 4px 10px; border-radius: 12px; background: {Colors.BG_DARKEST}; font-size: 11px;",
        )
        stats_layout.addWidget(self.stat_modules)
        stats_layout.addStretch()
        hero_layout.addLayout(stats_layout)

        root.addWidget(hero)

        # Call the update text method to apply Galactic overrides or time-based greeting
        self._update_dashboard_text()

        # ── Dashboard Content (Scrollable Area) ───────────────────────────────
        content = QWidget()
        theme_manager.apply_style(content, f"background: {Colors.BG_DARKEST};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(56, 36, 56, 36)
        content_layout.setSpacing(30)

        from karcytics.ui.layouts.flow_layout import FlowLayout

        scroll_style = """
            QScrollArea { background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; margin-left: 2px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); border-radius: 4px; min-height: 40px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """

        # New Analysis Section
        new_lbl = QLabel("Start New Analysis")
        theme_manager.apply_style(
            new_lbl,
            f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 600; color: {Colors.FG_PRIMARY};",
        )
        content_layout.addWidget(new_lbl)

        self.modules_inner = QWidget()
        self.modules_layout = FlowLayout(self.modules_inner, margin=0, spacing=24)
        content_layout.addWidget(self.modules_inner)

        # Recent Workflows Section
        self.workflows_container = QWidget()
        self.workflows_container.setObjectName("workflows_container")
        wf_layout = QVBoxLayout(self.workflows_container)
        wf_layout.setContentsMargins(0, 20, 0, 0)
        wf_layout.setSpacing(14)

        wf_lbl = QLabel("Recent Sessions")
        theme_manager.apply_style(
            wf_lbl,
            f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 600; color: {Colors.FG_PRIMARY};",
        )
        wf_layout.addWidget(wf_lbl)

        self.workflows_inner = QWidget()
        self.workflows_layout = FlowLayout(self.workflows_inner, margin=0, spacing=20)
        wf_layout.addWidget(self.workflows_inner)

        content_layout.addWidget(self.workflows_container)
        content_layout.addStretch()

        # Wrap content in a main scroll area
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll.setWidget(content)
        theme_manager.apply_style(self.main_scroll, scroll_style)

        root.addWidget(self.main_scroll, stretch=1)

    # ── Population Methods ──

    def populate_modules(self, manifests: list[dict]) -> None:
        """
        Dynamically rebuild the module selection grid from installed module manifests.

        Parameters:
            manifests (list[dict]): Module manifests containing display and trust information for each installed module.
        """
        while self.modules_layout.count():
            item = self.modules_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not manifests:
            lbl = QLabel("No analysis modules installed. Use the Store to download plugins.")
            theme_manager.apply_style(lbl, f"color: {Colors.FG_DISABLED}; font-style: italic;")
            self.modules_layout.addWidget(lbl)
            return

        self.stat_modules.setText(f"📡 {len(manifests)} Modules Active")  # Update the stat

        for _i, manifest in enumerate(manifests):
            card = ModuleCard(
                icon=manifest.get("icon", "📦"),
                title=manifest.get("display_name", "Unknown Module"),
                description=manifest.get("description", ""),
                badge="Installed",
                enabled=True,
                trust_level=manifest.get("trust_level", "verified"),
                trust_path=manifest.get("trust_path", []),
                developer_name=manifest.get("developer_name"),
                developer_key=manifest.get("developer_key"),
            )
            card.clicked.connect(lambda *args, m=manifest: self.module_selected.emit(m))  # noqa: ARG005
            mid_val = manifest.get("id")
            card.trust_requested.connect(
                lambda *args, mid=mid_val: self.trust_module_requested.emit(mid)  # noqa: ARG005
            )
            self.modules_layout.addWidget(card)

    def populate_workflows(self, workflows: list[dict]) -> None:
        """
        Populate the recent sessions grid with workflow cards.

        Parameters:
                workflows (list[dict]): Workflow records used to create the session cards.
        """
        # Lazy import to avoid circular dependency at module level
        from karcytics.core.tutorial_manager import global_tutorial_manager

        while self.workflows_layout.count():
            item = self.workflows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not workflows:
            self.workflows_container.setVisible(False)
            return

        self.workflows_container.setVisible(True)

        for _i, wf in enumerate(workflows):
            filename = wf.get("filename", "")
            module_id = wf.get("module_id", "Unknown")

            # Make the module ID prettier (e.g., "western_blot" -> "Western Blot")
            pretty_mod = module_id.replace("_", " ").title()

            title = wf.get("name", filename.replace(".json", ""))
            date_str = wf.get("timestamp", "Unknown Date")
            desc = wf.get("description", "")
            tags = wf.get("tags", [])

            # Check if the module has Academy courses registered
            courses = global_tutorial_manager.get_courses_for_module(module_id)
            has_academy = len(courses) > 0
            course_count = len(courses)

            card = WorkflowCard(
                title=title,
                date_str=date_str,
                module_name=pretty_mod,
                description=desc,
                tags=tags,
                has_academy=has_academy,
                course_count=course_count,
                academy=wf.get("academy"),
            )

            # THE LAMBDA FIX: We are now explicitly locking 't=title' into memory!
            card.clicked.connect(
                lambda *args, mid=module_id, fn=filename: self.workflow_selected.emit(mid, fn)  # noqa: ARG005
            )
            card.settings_requested.connect(
                lambda *args, mid=module_id, fn=filename: self.workflow_settings_requested.emit(  # noqa: ARG005
                    mid, fn
                )
            )
            card.academy_requested.connect(
                lambda *args, mid=module_id: self.open_academy_for_module_requested.emit(mid)  # noqa: ARG005
            )

            self.workflows_layout.addWidget(card)

    def _update_dashboard_text(self):
        import datetime

        from karcytics.ui.theme import Strings, theme_manager

        hour = datetime.datetime.now().hour

        is_sw = "Galactic" in theme_manager.current_theme_name

        if is_sw:
            greeting = Strings.GREETING
            theme_manager.apply_style(
                self.lbl_greeting,
                f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 900; color: {Colors.ACCENT_PRIMARY}; text-transform: uppercase;",
            )
        else:
            greeting = (
                "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
            )
            theme_manager.apply_style(
                self.lbl_greeting,
                f"font-size: {Fonts.SIZE_LARGE}px; font-weight: 600; color: {Colors.FG_PRIMARY};",
            )

        self.lbl_greeting.setText(f"{greeting}.")
        self.lbl_tagline.setText(Strings.TAGLINE)
