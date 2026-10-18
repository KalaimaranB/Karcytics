import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def test_help_center_initialization(qtbot):
    """Verifies that the Help Center can be initialized without crashing.
    This specifically checks for the 'QtWebEngineWidgets must be imported before QApplication' error.
    """
    # 1. Ensure WebEngine attribute is set (matches karcytics/__main__.py)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # 2. Import the dialog (this is where the crash usually happens)
    try:
        from karcytics.ui.dialogs.help_dialog import HelpCenterDialog
    except ImportError as e:
        pytest.fail(f"Failed to import HelpCenterDialog: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during import: {e}")

    # 3. Try to instantiate
    dialog = HelpCenterDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Karcytics Help Center"
    assert dialog.tree.topLevelItemCount() >= 0
    assert dialog.viewer is not None
