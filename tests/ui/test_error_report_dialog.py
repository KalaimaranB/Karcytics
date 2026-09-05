"""Tests for ErrorReportDialog's consent-aware "send this report" control.

Uses the same style as test_loader_theme_sync.py: a real qapp fixture, real
widgets, but crash_reporting itself monkeypatched so nothing touches
preferences.json or a real Sentry client.
"""

from karcytics.ui.dialogs.error_report import ErrorReportDialog


def test_send_report_control_is_hidden_when_no_dsn_is_configured(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.get_configured_dsn", lambda: None
    )

    dialog = ErrorReportDialog({"message": "boom"})

    assert dialog.send_report_btn is None
    assert dialog.consent_checkbox is None


def test_send_report_button_is_enabled_when_dsn_configured_and_not_fatal(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.is_consent_given", lambda: None
    )

    dialog = ErrorReportDialog({"message": "boom", "fatal": False})

    assert dialog.send_report_btn is not None
    assert dialog.send_report_btn.isEnabled()
    assert dialog.send_report_btn.text() == "Send This Report"


def test_send_report_button_shows_already_sent_for_a_fatal_error_with_prior_consent(
    qapp,
    monkeypatch,  # noqa: ARG001
):
    """A fatal error with consent already True was already auto-sent by
    DiagnosticEngine.report_error() before this dialog ever opened —
    offering to send it again would be misleading.
    """
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.is_consent_given", lambda: True
    )

    dialog = ErrorReportDialog({"message": "boom", "fatal": True})

    assert dialog.send_report_btn is not None
    assert not dialog.send_report_btn.isEnabled()
    assert dialog.send_report_btn.text() == "Report Sent Automatically"


def test_clicking_send_report_grants_consent_and_sends(qapp, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.is_consent_given", lambda: None
    )
    consent_calls = []
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.set_consent", consent_calls.append
    )
    sent = []
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.capture_error_data",
        lambda data: sent.append(data) or True,
    )

    error_data = {"message": "boom", "fatal": False, "plugin_id": "flow_cytometry"}
    dialog = ErrorReportDialog(error_data)
    dialog.send_report_btn.click()

    assert consent_calls == [True]
    assert sent == [error_data]
    assert dialog.send_report_btn.text() == "Report Sent — Thank You"
    assert not dialog.send_report_btn.isEnabled()


def test_clicking_send_report_does_not_regrant_consent_when_already_checked(qapp, monkeypatch):  # noqa: ARG001
    """Consent was already given (checkbox starts checked) — clicking the
    button must not toggle it off-then-on again, which would fire a
    redundant set_consent(True) call the checkbox's own toggled signal
    already covers once, at construction time it's already True so no
    toggled signal fires at all.
    """
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.get_configured_dsn",
        lambda: "https://example.invalid/1",
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.is_consent_given", lambda: True
    )
    consent_calls = []
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.set_consent", consent_calls.append
    )
    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.capture_error_data",
        lambda data: True,  # noqa: ARG005
    )

    # Non-fatal + prior consent: button is active (not "already auto-sent").
    dialog = ErrorReportDialog({"message": "boom", "fatal": False})
    dialog.send_report_btn.click()

    assert consent_calls == []
