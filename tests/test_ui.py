import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication


class TestKarcyticsUI(unittest.TestCase):
    """Smoke tests for UI window instantiation."""

    @classmethod
    def setUpClass(cls):
        # We need exactly one QApplication instance for all UI tests
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def test_hub_instantiation(self):
        """Verify the Project Hub window can be created without crashing."""
        from karcytics.ui.windows.project_launcher import ProjectLauncherWindow

        # Mock dependencies
        mock_mm = MagicMock()
        mock_updater = MagicMock()
        mock_mm.get_available_modules.return_value = []

        try:
            window = ProjectLauncherWindow(
                module_manager=mock_mm,
                updater=mock_updater,
                store_callback=lambda: None,
                hub_callback=lambda: None,
            )
            self.assertIsNotNone(window)
            window.close()
        except Exception as e:
            self.fail(f"ProjectLauncherWindow failed to instantiate: {e}")

    def test_workspace_instantiation(self):
        """Verify the main Workspace window can be created without crashing."""
        from karcytics.ui.windows.workspace_window import WorkspaceWindow

        # Mock dependencies
        mock_pm = MagicMock()
        mock_mm = MagicMock()
        mock_updater = MagicMock()

        mock_pm.data = {"project_name": "Test Project"}
        mock_mm.get_available_modules.return_value = []

        try:
            window = WorkspaceWindow(
                project_manager=mock_pm,
                module_manager=mock_mm,
                updater=mock_updater,
                store_callback=lambda _: None,
                hub_callback=lambda: None,
            )
            self.assertIsNotNone(window)
            window.close()
        except Exception as e:
            self.fail(f"WorkspaceWindow failed to instantiate: {e}")


if __name__ == "__main__":
    unittest.main()
