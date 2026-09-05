import logging

import pytest

from karcytics.core.logging_setup import configure_logging


def _read(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """configure_logging() replaces all root handlers process-wide.

    Left unrestored, that permanently strips whatever handlers other code
    (e.g. DiagnosticEngine's AutoReportHandler) had already attached to the
    root logger, breaking unrelated tests that run later in the same
    session. Save and restore around each test here instead.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        yield
    finally:
        for h in root.handlers[:]:
            root.removeHandler(h)
            h.close()
        for h in original_handlers:
            root.addHandler(h)
        root.setLevel(original_level)


def test_configure_logging_routes_core_ipc_and_plugin_records(tmp_path):
    core_log = configure_logging(tmp_path)
    logs_dir = tmp_path / "logs"

    assert core_log == logs_dir / "core.log"

    core_logger = logging.getLogger("karcytics.core.module_manager")
    ipc_logger = logging.getLogger("karcytics_sdk.plugin.daemon")
    core_services_logger = logging.getLogger("karcytics.host.core_services")
    plugin_logger = logging.getLogger("plugin.my_plugin")

    core_logger.info("core startup message")
    ipc_logger.debug("ready handshake ok", extra={"plugin_id": "my_plugin"})
    core_services_logger.debug("CoreServicesServer: dispatching method")
    plugin_logger.info("plugin did a thing", extra={"plugin_id": "my_plugin"})
    ipc_logger.debug(
        "relayed worker output",
        extra={"plugin_id": "my_plugin", "log_event": "worker_stderr"},
    )

    for handler in logging.getLogger().handlers:
        handler.flush()

    core_content = _read(logs_dir / "core.log")
    ipc_content = _read(logs_dir / "ipc.log")
    plugin_content = _read(logs_dir / "plugins" / "my_plugin.log")

    assert "core startup message" in core_content
    assert "ready handshake ok" not in core_content
    assert "CoreServicesServer: dispatching method" not in core_content
    assert "plugin did a thing" not in core_content
    assert "relayed worker output" not in core_content

    assert "ready handshake ok" in ipc_content
    assert "CoreServicesServer: dispatching method" in ipc_content
    assert "plugin did a thing" not in ipc_content
    assert "relayed worker output" not in ipc_content

    assert "plugin did a thing" in plugin_content
    assert "relayed worker output" in plugin_content
    assert "ready handshake ok" not in plugin_content


def test_configure_logging_separates_multiple_plugins(tmp_path):
    configure_logging(tmp_path)
    logs_dir = tmp_path / "logs"

    logging.getLogger("plugin.plugin_a").info("a's message", extra={"plugin_id": "plugin_a"})
    logging.getLogger("plugin.plugin_b").info("b's message", extra={"plugin_id": "plugin_b"})

    for handler in logging.getLogger().handlers:
        handler.flush()

    a_content = _read(logs_dir / "plugins" / "plugin_a.log")
    b_content = _read(logs_dir / "plugins" / "plugin_b.log")

    assert "a's message" in a_content
    assert "b's message" not in a_content
    assert "b's message" in b_content
    assert "a's message" not in b_content
