# karcytics/ui/workflows_tab.py
from PySide6.QtWidgets import QLineEdit, QScrollArea, QVBoxLayout, QWidget

from karcytics.ui.components.cards import DetailedWorkflowCard as WorkflowCard
from karcytics.ui.theme import theme_manager


class WorkflowsTab(QWidget):
    """Searchable list of saved work sessions."""

    def __init__(self, project_manager, on_workflow_selected):
        super().__init__()
        self.pm = project_manager
        self.on_workflow_selected = on_workflow_selected
        self.all_workflows = []

        layout = QVBoxLayout(self)

        # ── Search Bar ──────────────────────────────────────────────
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search by name or #tag...")
        self.search_bar.textChanged.connect(self.refresh_list)
        layout.addWidget(self.search_bar)

        # ── Scrollable Area ──────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        theme_manager.apply_style(
            self.scroll, "QScrollArea { border: none; background: transparent; }"
        )

        self.container = QWidget()
        # Use a standard QVBoxLayout instead of the missing QFlowLayout
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 10, 0, 10)
        self.card_layout.setSpacing(10)

        # This stretch at the bottom keeps cards pushed to the top
        self.card_layout.addStretch()

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh_list(self):
        """Reloads workflows from disk and filters based on search text."""
        # 1. Clear current cards (but leave the stretch at the end!)
        while self.card_layout.count() > 1:
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 2. Get fresh list from ProjectManager
        if not self.pm:
            return

        self.all_workflows = self.pm.list_workflows()
        query = self.search_bar.text().lower().strip()

        # 3. Filter and Add
        for meta in self.all_workflows:
            # Simple search logic
            match = (
                not query
                or query in meta.get("name", "").lower()
                or query in meta.get("description", "").lower()
                or any(query.lstrip("#") in t.lower() for t in meta.get("tags", []))
            )

            if match:
                card = WorkflowCard(meta, self.on_workflow_selected)
                # Insert at index 0 so newest ones appear at the top
                self.card_layout.insertWidget(0, card)
