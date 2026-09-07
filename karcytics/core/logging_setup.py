"""Karcytics Logging Setup.

Splits application logging into three separate, rotating log files instead
of one undifferentiated ``karcytics.log``:

- ``logs/core.log`` — the Hub's own code (UI, module manager, diagnostics, ...).
- ``logs/ipc.log`` — core<->plugin transport traffic: the msgpack frame
  protocol in ``karcytics_sdk.plugin.daemon``/``ui_daemon_runtime`` and the
  ``CoreServicesServer`` RPC calls isolated workers make back into the Hub.
- ``logs/plugins/<plugin_id>.log`` — a plugin's own log output: records from
  an in-process plugin's ``self.logger`` (``BasePlugin``, logger name
  ``plugin.<id>``), plus an isolated plugin's relayed stderr, which is
  content the plugin itself wrote, not transport metadata.

Routing is done with `logging.Filter`s keyed on logger name (and, for
relayed worker stderr, the ``log_event`` extra already attached in
``daemon.py``) rather than on `plugin_id` alone, since the daemon's own
transport-layer records carry `plugin_id` too and must stay out of that
plugin's content log.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

# Host-side loggers that only ever carry core<->plugin transport traffic
# (frame send/receive, ready handshakes, RPC dispatch) rather than a
# plugin's own log content.
_IPC_LOGGER_NAMES = (
    "karcytics_sdk.plugin.daemon",
    "karcytics_sdk.plugin.ui_daemon_runtime",
    "karcytics.host.core_services",
)

_PLUGIN_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _is_relayed_worker_output(record: logging.LogRecord) -> bool:
    return getattr(record, "log_event", None) == "worker_stderr" and bool(
        getattr(record, "plugin_id", None)
    )


def _is_plugin_content(record: logging.LogRecord) -> bool:
    return record.name.startswith("plugin.") or _is_relayed_worker_output(record)


def _is_ipc_traffic(record: logging.LogRecord) -> bool:
    return record.name in _IPC_LOGGER_NAMES and not _is_relayed_worker_output(record)


class _CoreRecordFilter(logging.Filter):
    """Accepts everything except IPC transport traffic and plugin content."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (_is_ipc_traffic(record) or _is_plugin_content(record))


class _IpcRecordFilter(logging.Filter):
    """Accepts only core<->plugin transport traffic."""

    def filter(self, record: logging.LogRecord) -> bool:
        return _is_ipc_traffic(record)


class PerPluginFileHandler(logging.Handler):
    """Fans plugin-content records out to one rotating file handler per plugin_id.

    Handlers are created lazily the first time a given plugin logs, since
    plugins are discovered/installed dynamically and their ids aren't known
    up front.
    """

    def __init__(self, plugins_log_dir: Path) -> None:
        """Initialize with the directory per-plugin log files are written into."""
        super().__init__()
        self.plugins_log_dir = plugins_log_dir
        self._handlers: dict[str, logging.handlers.RotatingFileHandler] = {}

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        return _is_plugin_content(record)

    def _plugin_id_for(self, record: logging.LogRecord) -> str:
        plugin_id = getattr(record, "plugin_id", None)
        if not plugin_id and record.name.startswith("plugin."):
            plugin_id = record.name.removeprefix("plugin.")
        return _PLUGIN_ID_SAFE_RE.sub("_", plugin_id or "unknown")

    def _handler_for(self, plugin_id: str) -> logging.handlers.RotatingFileHandler:
        handler = self._handlers.get(plugin_id)
        if handler is None:
            self.plugins_log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                self.plugins_log_dir / f"{plugin_id}.log",
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(self.formatter)
            self._handlers[plugin_id] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            self._handler_for(self._plugin_id_for(record)).emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:  # noqa: D102
        for handler in self._handlers.values():
            handler.close()
        super().close()


def configure_logging(app_data_dir: Path) -> Path:
    """Configure root logging with separate core/ipc/per-plugin log files.

    Returns:
        Path: The core log file, kept as the return value for backward
        compatibility with callers that surface "the log file" to the user.
    """
    logs_dir = app_data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    core_log_file = logs_dir / "core.log"

    standard_fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    detailed_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s"
    )

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(standard_fmt)

    core_handler = logging.handlers.RotatingFileHandler(
        core_log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    core_handler.setLevel(logging.INFO)
    core_handler.setFormatter(detailed_fmt)
    core_handler.addFilter(_CoreRecordFilter())

    ipc_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "ipc.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    ipc_handler.setLevel(logging.DEBUG)
    ipc_handler.setFormatter(detailed_fmt)
    ipc_handler.addFilter(_IpcRecordFilter())

    plugin_handler = PerPluginFileHandler(logs_dir / "plugins")
    plugin_handler.setLevel(logging.DEBUG)
    plugin_handler.setFormatter(detailed_fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    for handler in (console, core_handler, ipc_handler, plugin_handler):
        root.addHandler(handler)

    for noisy_logger, level in (
        ("numba", logging.CRITICAL),
        ("matplotlib", logging.WARNING),
        ("PIL", logging.WARNING),
    ):
        lg = logging.getLogger(noisy_logger)
        lg.setLevel(level)
        lg.propagate = False

    logging.info("--- KARCYTICS BOOTLOADER INITIALIZED ---")
    return core_log_file
