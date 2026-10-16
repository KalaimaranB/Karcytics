"""Tests for Shared UI Components (Overlays, Workflow Tabs)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from karcytics.ui.components.cards import DetailedWorkflowCard
from karcytics.ui.components.overlays import BioLoadingOverlay
from karcytics.ui.tabs.workflows_tab import WorkflowsTab


class TestSharedUI:
    @pytest.fixture
    def parent_widget(self, qtbot):
        """Standardized parent widget for testing overlays and tabs."""
        w = QWidget()
        qtbot.addWidget(w)
        w.show()
        return w

    def test_loading_overlay_lifecycle(self, parent_widget, qtbot):
        """Verifies start/stop and text updates for the loading overlay."""
        overlay = BioLoadingOverlay(parent_widget)
        qtbot.addWidget(overlay)

        overlay.set_text("Analyzing...")
        assert overlay.lbl_text.text() == "Analyzing..."

        overlay.start()
        # isHidden is more reliable than isVisible in headless tests
        assert not overlay.isHidden()
        assert overlay.timer.isActive() is True

        overlay.stop()
        assert overlay.isHidden() is True
        assert overlay.timer.isActive() is False

    def test_workflows_tab_population(self, parent_widget, qtbot):
        """Verifies that workflows from ProjectManager are rendered and filtered."""
        mock_pm = MagicMock()
        mock_pm.list_workflows.return_value = [
            {"name": "W1", "description": "Desc 1", "tags": ["tag1"], "module": "m1"},
            {"name": "Other", "description": "Secret", "tags": ["tag2"], "module": "m2"},
        ]

        mock_cb = MagicMock()
        tab = WorkflowsTab(mock_pm, mock_cb)
        tab.setParent(parent_widget)
        qtbot.addWidget(tab)

        # Initial load
        tab.refresh_list()

        # Check cards (including hidden ones)
        # Use wait_until because deleteLater() takes an event loop cycle
        qtbot.wait_until(lambda: len(tab.findChildren(DetailedWorkflowCard)) == 2)

        # Test filtering
        tab.search_bar.setText("W1")

        # Ensure only 1 is visible
        def check_visible():
            visible = [c for c in tab.findChildren(DetailedWorkflowCard) if not c.isHidden()]
            return len(visible) == 1

        qtbot.wait_until(check_visible)

        # Test tag filtering
        tab.search_bar.setText("#tag2")

        def check_tag_filter():
            visible = [c for c in tab.findChildren(DetailedWorkflowCard) if not c.isHidden()]
            return len(visible) == 1 and visible[0].metadata["name"] == "Other"

        qtbot.wait_until(check_tag_filter)

    def test_card_load_callback(self, qtbot):
        """Verify the 'Open Workflow' button triggers the callback."""
        meta = {"name": "Test", "module": "mod"}
        mock_cb = MagicMock()
        card = DetailedWorkflowCard(meta, mock_cb)
        qtbot.addWidget(card)

        card.btn_load.clicked.emit()
        mock_cb.assert_called_once_with(meta)
