"""Tests for the formal Karcytics Plugin Contract (Track 1)."""

from unittest.mock import patch

import pytest
from karcytics_sdk.host.trust_manager import TrustManager
from karcytics_sdk.plugin import KarcyticsPlugin, PluginBase
from PySide6.QtWidgets import QWidget

from karcytics.core.module_manager import ModuleManager


class MockValidPlugin:
    """A module-like object that satisfies the KarcyticsPlugin Protocol."""

    __version__ = "1.0.0"
    __plugin_id__ = "test_mod"

    @staticmethod
    def get_panel_class():
        return QWidget

    def cleanup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class MockInvalidPlugin:
    """A module-like object that fails the KarcyticsPlugin Protocol (missing get_panel_class)."""

    __version__ = "1.0.0"
    __plugin_id__ = "bad_mod"


class MockOverrides:
    def trust_current_state(self, module_id, hashes):
        pass


class PermissiveTrustManager(TrustManager):
    """A trust manager for tests that allows everything."""

    def __init__(self) -> None:
        self.overrides = MockOverrides()  # type: ignore[assignment]

    def verify_plugin(self, path):
        class FakeResult:
            success = True
            trust_level = "verified_mock"
            calculated_hashes = {}

        return FakeResult()

    def _get_cache(self):
        return None


class TestPluginContract:
    def test_protocol_runtime_check(self):
        """Verifies that runtime_checkable protocol works on modules and classes."""
        assert isinstance(MockValidPlugin, KarcyticsPlugin)  # type: ignore[arg-type]
        assert not isinstance(MockInvalidPlugin, KarcyticsPlugin)  # type: ignore[arg-type]

    def test_plugin_base_satisfies_contract(self):
        """Verifies that the SDK's PluginBase satisfies the protocol."""

        class MyPlugin(PluginBase):
            def get_state(self):
                return None

            def set_state(self, s):
                pass

            def cleanup(self):
                pass

            def shutdown(self):
                pass

        # The class itself should satisfy it (via get_panel_class classmethod)
        assert isinstance(MyPlugin, KarcyticsPlugin)  # type: ignore[arg-type]

    @patch("karcytics.core.plugins.loader.importlib.import_module")
    def test_module_manager_validation_pass(self, mock_import, tmp_path):
        """Verifies that ModuleManager allows loading valid plugins."""
        mm = ModuleManager(trust_manager=PermissiveTrustManager())

        # Create dummy venv to pass dependency check
        import sys

        venv_bin = tmp_path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
        venv_bin.mkdir(parents=True)
        (venv_bin / ("python.exe" if sys.platform == "win32" else "python3")).touch()

        mm.modules["mod_a"] = {
            "package_name": "mod_a",
            "loaded": False,
            "trust_level": "verified_mock",
            "path": tmp_path,
            "manifest": {"name": "Test Module A"},
        }

        mock_import.return_value = MockValidPlugin

        # Should not raise exception
        ui_class = mm.load_module_ui("mod_a")
        assert ui_class == QWidget
        assert mm.modules["mod_a"]["loaded"] is True

    @patch("karcytics.core.plugins.loader.importlib.import_module")
    def test_module_manager_validation_fail(self, mock_import, tmp_path):
        """Verifies that ModuleManager rejects invalid plugins."""
        mm = ModuleManager(trust_manager=PermissiveTrustManager())

        # Create dummy venv to pass dependency check
        import sys

        venv_bin = tmp_path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
        venv_bin.mkdir(parents=True, exist_ok=True)
        (venv_bin / ("python.exe" if sys.platform == "win32" else "python3")).touch()

        mm.modules["bad_mod"] = {
            "package_name": "bad_mod",
            "loaded": False,
            "trust_level": "verified_mock",
            "path": tmp_path,
            "manifest": {"name": "Bad Module"},
        }

        mock_import.return_value = MockInvalidPlugin

        # Should raise TypeError during validation
        with pytest.raises(TypeError) as exc:
            mm.load_module_ui("bad_mod")

        assert "failed interface validation. Missing required hooks" in str(exc.value)
        assert mm.modules["bad_mod"]["loaded"] is False
