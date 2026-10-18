"""Tests for Karcytics theme engine."""

import json
from pathlib import Path

import pytest

from karcytics.ui.theme import Colors, ThemeManager


class TestThemeEngine:
    @pytest.fixture
    def manager(self):
        return ThemeManager()

    def test_colors_defaults(self):
        """Verify default GitHub Dark colors are present."""
        assert Colors.BG_DARKEST == "#0d1117"
        assert Colors.ACCENT_PRIMARY == "#2f81f7"

    def test_load_valid_theme(self, manager, tmp_path):
        """Test loading a valid theme.json file."""
        theme_data = {"name": "Ocean Blue", "BG_DARKEST": "#000033", "ACCENT_PRIMARY": "#00ffff"}
        theme_file = tmp_path / "ocean.json"
        theme_file.write_text(json.dumps(theme_data))

        # Track signal
        signal_received = []
        manager.theme_changed.connect(lambda: signal_received.append(True))

        success = manager.load_theme(theme_file)

        assert success is True
        assert manager.current_theme_name == "Ocean Blue"
        assert Colors.BG_DARKEST == "#000033"
        assert Colors.ACCENT_PRIMARY == "#00ffff"
        assert len(signal_received) == 1

    def test_load_invalid_json(self, manager, tmp_path):
        """Test loading a corrupted JSON file."""
        theme_file = tmp_path / "bad.json"
        theme_file.write_text("{ broken json ...")

        success = manager.load_theme(theme_file)
        assert success is False

    def test_load_missing_file(self, manager):
        """Test loading a nonexistent file."""
        success = manager.load_theme(Path("/nonexistent/theme.json"))
        assert success is False

    def test_partial_theme_load(self, manager, tmp_path):
        """Test loading a theme with only some keys defined."""
        # Reset defaults for test consistency
        Colors.BG_DARKEST = "#0d1117"

        theme_data = {"BG_DARKEST": "#990000"}
        theme_file = tmp_path / "partial.json"
        theme_file.write_text(json.dumps(theme_data))

        manager.load_theme(theme_file)
        assert Colors.BG_DARKEST == "#990000"
        # Other colors should remain unchanged (e.g. DNA_PRIMARY which we didn't touch)
        assert Colors.DNA_PRIMARY == "#00f2ff"

    def test_get_tamil_font_family_success(self, monkeypatch, tmp_path):
        import karcytics.ui.theme

        karcytics.ui.theme._tamil_font_family = None

        def mock_resource_path(path):
            p = tmp_path / "NotoSansTamil-Variable.ttf"
            p.write_text("fake font")
            return p

        monkeypatch.setattr("karcytics.core.resource_manager.resource_path", mock_resource_path)

        class MockQFontDatabase:
            @staticmethod
            def addApplicationFont(path):  # noqa: N802
                return 1

            @staticmethod
            def applicationFontFamilies(id):  # noqa: N802, A002
                return ["Mock Tamil Font"]

        monkeypatch.setattr("PySide6.QtGui.QFontDatabase", MockQFontDatabase)

        family = karcytics.ui.theme.get_tamil_font_family()
        assert family == "Mock Tamil Font"

    def test_get_tamil_font_family_missing_resource(self, monkeypatch, tmp_path):
        import karcytics.ui.theme

        karcytics.ui.theme._tamil_font_family = None

        def mock_resource_path(path):
            return tmp_path / "missing.ttf"

        monkeypatch.setattr("karcytics.core.resource_manager.resource_path", mock_resource_path)

        family = karcytics.ui.theme.get_tamil_font_family()
        assert family == "Noto Sans Tamil"

    def test_get_tamil_font_family_empty_families(self, monkeypatch, tmp_path):
        import karcytics.ui.theme

        karcytics.ui.theme._tamil_font_family = None

        def mock_resource_path(path):
            p = tmp_path / "NotoSansTamil-Variable.ttf"
            p.write_text("fake font")
            return p

        monkeypatch.setattr("karcytics.core.resource_manager.resource_path", mock_resource_path)

        class MockQFontDatabase:
            @staticmethod
            def addApplicationFont(path):  # noqa: N802
                return 1

            @staticmethod
            def applicationFontFamilies(id):  # noqa: N802, A002
                return []

        monkeypatch.setattr("PySide6.QtGui.QFontDatabase", MockQFontDatabase)

        family = karcytics.ui.theme.get_tamil_font_family()
        assert family == "Noto Sans Tamil"
