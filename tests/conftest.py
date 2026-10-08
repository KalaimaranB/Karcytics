"""Test configuration and shared fixtures."""

import logging
import os
import sys
from pathlib import Path

import pytest

# Force Qt headless mode for CI and macOS test environments.
# This must be set before PySide6 is imported by any test module.
if os.environ.get("QT_QPA_PLATFORM") is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Early WebEngine and OpenGL Context setup to avoid QApplication import order errors
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
import PySide6.QtWebEngineWidgets  # noqa: F401, E402

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s")


# Pytest markers
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "qt: mark test as requiring Qt/QApplication")


def pytest_sessionfinish(session, exitstatus):
    """Exit cleanly to avoid PySide6 teardown segfaults on macOS.

    PySide6 on macOS can segfault during cleanup when destroying the QApplication.
    This hook lets pytest exit before C++ destructors run.
    """
    # os._exit(exitstatus)
    pass


# Fixtures for common test setup


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Provide a temporary config directory for tests."""
    config_dir = tmp_path / ".karcytics" / "plugin_configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Mock the config directory location
    monkeypatch.setenv("HOME", str(tmp_path.parent))

    yield config_dir


@pytest.fixture
def cleanup_plugin_configs():
    """Clean up plugin configs after test."""
    yield

    # Cleanup: remove test config files
    config_base = Path.home() / ".karcytics" / "plugin_configs"
    if config_base.exists():
        for file in config_base.glob("*test*.json"):
            file.unlink(missing_ok=True)
