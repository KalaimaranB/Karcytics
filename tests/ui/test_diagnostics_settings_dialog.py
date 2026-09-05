from karcytics.ui.dialogs.diagnostics_settings_dialog import DiagnosticsSettingsDialog


def test_consent_checkbox_disabled_and_unchecked_when_no_dsn_configured(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: None,
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: None,
    )

    dialog = DiagnosticsSettingsDialog()

    assert not dialog.consent_checkbox.isEnabled()
    assert not dialog.consent_checkbox.isChecked()


def test_consent_checkbox_reflects_existing_consent(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: True,
    )

    dialog = DiagnosticsSettingsDialog()

    assert dialog.consent_checkbox.isEnabled()
    assert dialog.consent_checkbox.isChecked()


def test_toggling_checkbox_calls_set_consent(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: False,
    )
    calls = []
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.set_consent",
        calls.append,
    )

    dialog = DiagnosticsSettingsDialog()
    dialog.consent_checkbox.setChecked(True)

    assert calls == [True]


def test_send_test_event_button_disabled_until_consent_is_checked(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: False,
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.set_consent",
        lambda _enabled: None,
    )

    dialog = DiagnosticsSettingsDialog()
    assert not dialog.send_test_btn.isEnabled()

    dialog.consent_checkbox.setChecked(True)
    assert dialog.send_test_btn.isEnabled()


def test_send_test_event_calls_capture_error_data(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: True,
    )
    sent = []
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.capture_error_data",
        lambda data: sent.append(data) or True,
    )

    dialog = DiagnosticsSettingsDialog()
    dialog.send_test_btn.click()

    assert len(sent) == 1
    assert sent[0]["message"] == "Karcytics test event — safe to ignore."
    assert dialog.send_test_btn.text() == "Test Event Sent!"


def test_send_test_event_reports_when_nothing_was_actually_sent(qapp, monkeypatch):  # noqa: ARG001
    """capture_error_data() can return False even with the button enabled —
    e.g. consent was revoked in another window between enabling this button
    and clicking it. Must not claim success it didn't achieve.
    """
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.is_consent_given",
        lambda: True,
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.capture_error_data",
        lambda _data: False,
    )

    dialog = DiagnosticsSettingsDialog()
    dialog.send_test_btn.click()

    assert dialog.send_test_btn.text() == "Nothing To Send"


def test_copy_diagnostic_report_writes_json_to_clipboard(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: None,
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.diagnostics.get_full_diagnostic_report",
        lambda: {"timestamp": "now", "history": []},
    )

    dialog = DiagnosticsSettingsDialog()
    dialog._copy_diagnostic_report()

    from PyQt6.QtWidgets import QApplication

    clipboard_text = QApplication.clipboard().text()
    assert '"timestamp": "now"' in clipboard_text
    assert dialog.copy_report_btn.text() == "Copied!"


def test_open_logs_folder_creates_the_directory(qapp, monkeypatch, tmp_path):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.crash_reporting.get_configured_dsn",
        lambda: None,
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.AppConfig.APP_DATA_DIR", tmp_path
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.diagnostics_settings_dialog.QDesktopServices.openUrl", lambda *_: None
    )

    dialog = DiagnosticsSettingsDialog()
    dialog._open_logs_folder()

    assert (tmp_path / "logs").is_dir()
