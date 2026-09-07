import pytest
from PyQt6.QtWidgets import QApplication

from karcytics.ui.dialogs.error_report import ErrorReportDialog


def test_clicking_send_report_success(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    sent: list[tuple[dict, str]] = []

    def mock_send(data: dict, comments: str) -> bool:
        sent.append((data, comments))
        return True

    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.send_user_report",
        mock_send,
    )

    error_data = {"message": "boom", "fatal": False, "plugin_id": "flow_cytometry"}
    dialog = ErrorReportDialog(error_data)

    dialog.comments_area.setPlainText("It crashed!")
    dialog.send_btn.click()

    assert dialog.send_btn.text() == "Sending..."
    assert not dialog.send_btn.isEnabled()

    dialog.worker.wait()
    qapp.processEvents()

    assert sent == [(error_data, "It crashed!")]
    assert dialog.send_btn.text() == "Sent!"
    assert not dialog.send_btn.isEnabled()


def test_clicking_send_report_failure(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    sent: list[tuple[dict, str]] = []

    def mock_send(data: dict, comments: str) -> bool:
        sent.append((data, comments))
        return False

    monkeypatch.setattr(
        "karcytics.ui.dialogs.error_report.crash_reporting.send_user_report",
        mock_send,
    )

    error_data = {"message": "boom", "fatal": False}
    dialog = ErrorReportDialog(error_data)
    dialog.send_btn.click()

    dialog.worker.wait()
    qapp.processEvents()

    assert len(sent) == 1
    assert dialog.send_btn.text() == "Send Failed"
    assert dialog.send_btn.isEnabled()
