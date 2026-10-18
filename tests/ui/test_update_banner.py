"""Qt smoke tests for UpdateBannerWidget.

Written RED-first (TDD). These verify the banner's visual contract:
  - Starts hidden
  - Appears when the CORE_UPDATE_AVAILABLE event fires
  - Hides (but does not skip) on the X close button
  - Persists skip + hides on the Skip button
  - Opens browser on the Download button
"""

from unittest.mock import MagicMock, patch

import pytest

from karcytics.core.event_bus import KarcyticsEvent, get_event_bus


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Ensure a clean event bus for each test."""
    bus = get_event_bus()
    # Clear all listeners between tests
    bus._listeners.clear()
    yield
    bus._listeners.clear()


@pytest.fixture
def mock_update_checker():
    checker = MagicMock()
    checker.is_version_skipped.return_value = False
    return checker


@pytest.fixture
def banner(qtbot, mock_update_checker):
    from karcytics.ui.components.update_banner import UpdateBannerWidget

    widget = UpdateBannerWidget(update_checker=mock_update_checker)
    qtbot.addWidget(widget)
    return widget


@pytest.mark.qt
class TestUpdateBannerWidget:
    """Verifies the visual and interaction contract of UpdateBannerWidget."""

    def test_banner_hidden_by_default(self, banner):
        """Banner must be invisible until the update event fires."""
        assert banner.isHidden()

    def test_banner_shows_on_update_event(self, banner, qtbot):
        """Emitting CORE_UPDATE_AVAILABLE must make the banner visible."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com/release")

        # Process pending Qt events
        qtbot.wait(100)

        assert banner.isVisible()

    def test_banner_stores_version_on_event(self, banner, qtbot):
        """Banner must remember which version triggered it for skip."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com/release")
        qtbot.wait(100)

        assert banner._remote_version == "2.0.0"
        assert banner._download_url == "https://example.com/release"

    def test_banner_sets_notes_tooltip(self, banner, qtbot):
        """When notes are provided, the label's tooltip must carry the changelog text."""
        bus = get_event_bus()
        bus.emit(
            KarcyticsEvent.CORE_UPDATE_AVAILABLE,
            "2.0.0",
            "https://example.com/release",
            "- fix: something",
        )
        qtbot.wait(100)

        assert banner.lbl_message.toolTip() == "- fix: something"

    def test_close_button_hides_banner(self, banner, qtbot):
        """The X button hides the banner without persisting a skip."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com")
        qtbot.wait(100)

        qtbot.mouseClick(
            banner.btn_close, pytest.importorskip("PySide6.QtCore").Qt.MouseButton.LeftButton
        )

        assert banner.isHidden()

    def test_close_button_does_not_skip(self, banner, mock_update_checker, qtbot):
        """Closing via X must NOT call skip_version — only 'Skip This Version' does."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com")
        qtbot.wait(100)

        qtbot.mouseClick(
            banner.btn_close, pytest.importorskip("PySide6.QtCore").Qt.MouseButton.LeftButton
        )

        mock_update_checker.skip_version.assert_not_called()

    def test_skip_button_hides_banner(self, banner, qtbot):
        """Skip This Version must hide the banner."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com")
        qtbot.wait(100)

        qtbot.mouseClick(
            banner.btn_skip, pytest.importorskip("PySide6.QtCore").Qt.MouseButton.LeftButton
        )

        assert banner.isHidden()

    def test_skip_button_persists_skip(self, banner, mock_update_checker, qtbot):
        """Skip This Version must call update_checker.skip_version() with the current version."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com")
        qtbot.wait(100)

        qtbot.mouseClick(
            banner.btn_skip, pytest.importorskip("PySide6.QtCore").Qt.MouseButton.LeftButton
        )

        mock_update_checker.skip_version.assert_called_once_with("2.0.0")

    def test_download_button_opens_browser(self, banner, qtbot):
        """Download Now must open the download URL in a browser."""
        bus = get_event_bus()
        bus.emit(KarcyticsEvent.CORE_UPDATE_AVAILABLE, "2.0.0", "https://example.com/dl")
        qtbot.wait(100)

        with patch("webbrowser.open") as mock_open:
            qtbot.mouseClick(
                banner.btn_download, pytest.importorskip("PySide6.QtCore").Qt.MouseButton.LeftButton
            )
            mock_open.assert_called_once_with("https://example.com/dl")
