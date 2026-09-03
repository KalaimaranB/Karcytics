from unittest.mock import MagicMock, patch

import pytest

from karcytics.core import crash_reporting


class _FakePreferences:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Every test gets its own fake preferences store and a reset
    module-level `_initialized` flag, so consent/init state from one test
    never leaks into the next.
    """
    monkeypatch.setattr(crash_reporting, "core_preferences", _FakePreferences())
    monkeypatch.setattr(crash_reporting, "_initialized", False)
    monkeypatch.setattr(crash_reporting, "_module_manager", None)
    yield
    monkeypatch.setattr(crash_reporting, "_initialized", False)


class TestConsent:
    def test_consent_defaults_to_undecided(self):
        assert crash_reporting.is_consent_given() is None

    def test_set_consent_true_persists_and_is_read_back(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "get_configured_dsn", lambda: None)
        crash_reporting.set_consent(True)
        assert crash_reporting.is_consent_given() is True

    def test_set_consent_false_persists_and_is_read_back(self):
        crash_reporting.set_consent(False)
        assert crash_reporting.is_consent_given() is False


class TestGetConfiguredDsn:
    def test_returns_none_when_not_frozen_regardless_of_env(self, monkeypatch):
        """Source-tree runs must never return a DSN, even if the env var is set."""
        monkeypatch.setenv("KARCYTICS_SENTRY_DSN", "https://example.invalid/1")
        # sys.frozen is not set in test runs — get_configured_dsn must return None.
        assert crash_reporting.get_configured_dsn() is None

    def test_returns_env_value_when_frozen(self, monkeypatch):
        monkeypatch.setenv("KARCYTICS_SENTRY_DSN", "https://example.invalid/1")
        monkeypatch.setattr(crash_reporting.sys, "frozen", True, raising=False)
        assert crash_reporting.get_configured_dsn() == "https://example.invalid/1"

    def test_returns_none_when_frozen_but_env_unset(self, monkeypatch):
        monkeypatch.delenv("KARCYTICS_SENTRY_DSN", raising=False)
        monkeypatch.setattr(crash_reporting.sys, "frozen", True, raising=False)
        assert crash_reporting.get_configured_dsn() is None


class TestInitCrashReporting:
    def test_noop_without_a_configured_dsn(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "get_configured_dsn", lambda: None)
        crash_reporting.set_consent(True)

        assert crash_reporting.init_crash_reporting() is False
        assert crash_reporting.is_active() is False

    def test_noop_without_consent(self, monkeypatch):
        monkeypatch.setattr(
            crash_reporting, "get_configured_dsn", lambda: "https://example.invalid/1"
        )

        assert crash_reporting.init_crash_reporting() is False
        assert crash_reporting.is_active() is False

    def test_initializes_sentry_when_dsn_and_consent_both_present(self, monkeypatch):
        monkeypatch.setattr(
            crash_reporting, "get_configured_dsn", lambda: "https://example.invalid/1"
        )
        crash_reporting.core_preferences.set(crash_reporting.CONSENT_PREFERENCE_KEY, True)

        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            assert crash_reporting.init_crash_reporting() is True

        assert crash_reporting.is_active() is True
        mock_sentry.init.assert_called_once()
        kwargs = mock_sentry.init.call_args.kwargs
        assert kwargs["dsn"] == "https://example.invalid/1"
        assert kwargs["send_default_pii"] is False
        assert kwargs["include_local_variables"] is False
        assert kwargs["release"].startswith("karcytics@")
        assert kwargs["traces_sample_rate"] == 0.0
        assert kwargs["max_breadcrumbs"] == 50
        assert "environment" in kwargs

    def test_set_consent_true_triggers_init_when_dsn_configured(self, monkeypatch):
        monkeypatch.setattr(
            crash_reporting, "get_configured_dsn", lambda: "https://example.invalid/1"
        )
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.set_consent(True)

        assert crash_reporting.is_active() is True

    def test_set_consent_false_shuts_down_an_active_client(self, monkeypatch):
        monkeypatch.setattr(
            crash_reporting, "get_configured_dsn", lambda: "https://example.invalid/1"
        )
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.set_consent(True)
            assert crash_reporting.is_active() is True

            crash_reporting.set_consent(False)

        assert crash_reporting.is_active() is False


class TestScrubbing:
    def test_scrubs_home_directory_occurrences(self):
        from pathlib import Path

        home = str(Path.home())
        result = crash_reporting._scrub_value(f"loaded from {home}/projects/x")
        assert home not in result
        assert "<home>" in result

    def test_scrubs_absolute_path_ending_in_data_extension(self):
        result = crash_reporting._scrub_value("failed to parse /Volumes/Data/PatientX_Sample3.fcs")
        assert "PatientX_Sample3.fcs" not in result
        assert "<redacted-file>" in result

    def test_leaves_unrelated_strings_untouched(self):
        assert crash_reporting._scrub_value("division by zero") == "division by zero"

    def test_recurses_into_nested_dicts_and_lists(self):
        from pathlib import Path

        home = str(Path.home())
        event = {
            "message": "boom",
            "extra": {"path": f"{home}/data.fcs"},
            "breadcrumbs": [{"message": f"{home}/other.csv"}],
        }

        result = crash_reporting._scrub_value(event)

        assert home not in result["extra"]["path"]
        assert home not in result["breadcrumbs"][0]["message"]
        assert result["message"] == "boom"

    def test_before_send_applies_scrubbing(self):
        from pathlib import Path

        home = str(Path.home())
        event = {"message": f"error in {home}/sample.fcs"}

        result = crash_reporting._before_send(event, {})

        assert home not in result["message"]


class TestPluginVersion:
    def test_returns_none_without_a_registered_module_manager(self):
        assert crash_reporting._plugin_version("flow_cytometry") is None

    def test_returns_none_for_an_unknown_plugin_id(self, monkeypatch):
        mock_manager = MagicMock()
        mock_manager.modules = {}
        monkeypatch.setattr(crash_reporting, "_module_manager", mock_manager)

        assert crash_reporting._plugin_version("flow_cytometry") is None

    def test_resolves_version_from_the_module_manager(self, monkeypatch):
        mock_manager = MagicMock()
        mock_manager.modules = {"flow_cytometry": {"version": "1.4.0"}}
        monkeypatch.setattr(crash_reporting, "_module_manager", mock_manager)

        assert crash_reporting._plugin_version("flow_cytometry") == "1.4.0"

    def test_set_module_manager_registers_it(self):
        # Calls the real function rather than monkeypatching the attribute
        # directly — safe to leave set after this test, since the autouse
        # fixture above resets it to None at the *start* of every test
        # regardless of what the previous one left behind.
        mock_manager = MagicMock()
        mock_manager.modules = {"flow_cytometry": {"version": "2.0.0"}}

        crash_reporting.set_module_manager(mock_manager)

        assert crash_reporting._plugin_version("flow_cytometry") == "2.0.0"


class TestCaptureError:
    """Tests for the unified capture_error() function (and its capture_fatal_error wrapper)."""

    def test_noop_when_not_active(self):
        # is_active() is False by default in this isolated fixture — must
        # not raise or try to import sentry_sdk at all.
        crash_reporting.capture_error("boom", None, None, None)

    def test_captures_live_exception_when_available(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        exc = ValueError("nope")
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_error("bad transform", exc, "flow_cytometry", None)

        mock_scope.set_tag.assert_called_once_with("plugin_id", "flow_cytometry")
        mock_sentry.capture_exception.assert_called_once_with(exc)
        mock_sentry.capture_message.assert_not_called()

    def test_uses_provided_level_for_message_capture(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_error("info msg", None, None, None, level="warning")

        mock_sentry.capture_message.assert_called_once_with("info msg", level="warning")

    def test_capture_fatal_error_delegates_with_fatal_level(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_fatal_error(
                "remote failure", None, "flow_cytometry", "Traceback..."
            )

        mock_scope.set_extra.assert_called_once_with("traceback", "Traceback...")
        mock_sentry.capture_message.assert_called_once_with("remote failure", level="fatal")
        mock_sentry.capture_exception.assert_not_called()

    def test_tags_plugin_version_when_resolvable(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_manager = MagicMock()
        mock_manager.modules = {"flow_cytometry": {"version": "1.4.0"}}
        monkeypatch.setattr(crash_reporting, "_module_manager", mock_manager)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_error(
                "bad transform", ValueError("nope"), "flow_cytometry", None
            )

        mock_scope.set_tag.assert_any_call("plugin_id", "flow_cytometry")
        mock_scope.set_tag.assert_any_call("plugin_version", "1.4.0")

    def test_capture_error_nonfatal_uses_error_level_by_default(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_error("bad transform", None, None, "tb...", level="error")

        mock_sentry.capture_message.assert_called_once_with("bad transform", level="error")


class TestCaptureErrorData:
    def test_returns_false_and_sends_nothing_when_not_active(self):
        sent = crash_reporting.capture_error_data({"message": "boom"})
        assert sent is False

    def test_sends_message_and_traceback_from_error_data_dict(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        error_data = {
            "message": "bad transform",
            "plugin_id": "flow_cytometry",
            "traceback": "Traceback (most recent call last):\n...",
            "fatal": False,
        }
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            sent = crash_reporting.capture_error_data(error_data)

        assert sent is True
        mock_scope.set_tag.assert_called_once_with("plugin_id", "flow_cytometry")
        mock_scope.set_extra.assert_called_once_with(
            "traceback", "Traceback (most recent call last):\n..."
        )
        mock_sentry.capture_message.assert_called_once_with("bad transform", level="error")

    def test_omits_plugin_tag_and_traceback_extra_when_absent(self, monkeypatch):
        monkeypatch.setattr(crash_reporting, "_initialized", True)
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.new_scope.return_value.__enter__.return_value = mock_scope

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            crash_reporting.capture_error_data({"message": "core-only failure"})

        mock_scope.set_tag.assert_not_called()
        mock_scope.set_extra.assert_not_called()
        mock_sentry.capture_message.assert_called_once_with("core-only failure", level="error")
