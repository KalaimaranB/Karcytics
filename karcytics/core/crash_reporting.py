"""Consent-gated crash reporting via Sentry.

Nothing here ever sends anything without an explicit, persisted opt-in
(see `is_consent_given`/`set_consent`) — the tri-state default is
"undecided", not "on". A DSN also has to be configured out of band (baked
into the frozen binary by ``Karcytics.spec`` at build time via the
``KARCYTICS_SENTRY_DSN`` CI secret) **and** the app must be running as a
frozen production build (``sys.frozen``). Source-tree dev runs never send
crash reports, regardless of any environment variable.

`_before_send` exists because this app handles flow-cytometry data, where a
file path is very often also a sample/patient identifier
(`PatientX_Sample3.fcs`) — every string value in an outgoing event is
scrubbed for the user's home directory and any path-like token ending in a
known data-file extension before it leaves the machine. `init_crash_reporting`
additionally passes `include_local_variables=False` at init time, which is
the bigger leak this string scrub can't reach: a stack frame's local
variables can hold a raw DataFrame or file path no message-string regex
would ever see.

Every event carries the core version as Sentry's `release` field, and a
`plugin_version` tag alongside `plugin_id` whenever the error came from a
plugin currently resolvable via `set_module_manager` — otherwise a crash
report only tells you *what* broke, not *which build*.

What is sent in every Sentry event
-----------------------------------
- ``message``        – the error message string (file paths stripped)
- ``traceback``      – formatted stack trace (set as extra context)
- ``release``        – ``karcytics@<CORE_VERSION>``
- ``environment``    – ``"production"`` (only frozen builds can send)
- ``os.name``        – OS platform (set automatically by the Sentry SDK)
- ``plugin_id``      – Sentry tag, when the error came from a plugin
- ``plugin_version`` – Sentry tag, when resolvable from ModuleManager
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from karcytics.core.preferences import core_preferences

logger = logging.getLogger(__name__)

CONSENT_PREFERENCE_KEY = "diagnostics.crash_reporting_enabled"
_DSN_ENV_VAR = "KARCYTICS_SENTRY_DSN"

_DATA_FILE_EXTENSIONS = r"(?:fcs|csv|tsv|xlsx?|karcytics|png|jpe?g|tiff?|json)"
_PATH_LIKE_RE = re.compile(
    rf"(?:[A-Za-z]:\\|~?/)[^\s\"']*?\.{_DATA_FILE_EXTENSIONS}\b", re.IGNORECASE
)

_initialized = False
# Set once from _start_application after ModuleManager is constructed — see
# PluginUIDaemon.set_core_services for the same "set once, read elsewhere"
# shape used for the CoreServicesServer connection. Lets a crash report
# resolve which version of a plugin was actually installed when it fired,
# not just its id. None in headless contexts (tests, CLI tools) — plugin
# version is best-effort there, never required.
_module_manager: Any | None = None


def set_module_manager(module_manager: Any) -> None:
    """Register the live ModuleManager so crash reports can resolve plugin versions."""
    global _module_manager
    _module_manager = module_manager


def _plugin_version(plugin_id: str | None) -> str | None:
    if not plugin_id or _module_manager is None:
        return None
    mod_info = _module_manager.modules.get(plugin_id)
    return mod_info.get("version") if mod_info else None


def _tag_scope(scope: Any, plugin_id: str | None, message: str) -> None:
    if plugin_id:
        scope.set_tag("plugin_id", plugin_id)
        plugin_version = _plugin_version(plugin_id)
        if plugin_version:
            scope.set_tag("plugin_version", plugin_version)
    scope.set_context("karcytics", {"message": message})


def get_configured_dsn() -> str | None:
    """Return the Sentry DSN, or None if unavailable.

    Returns a non-None value only when running as a frozen production build
    (``sys.frozen`` is True — set by PyInstaller). Source-tree dev runs
    always return None so crash reports are never sent during development,
    regardless of any environment variable.

    The DSN is baked into the frozen binary at build time by
    ``Karcytics.spec`` reading ``KARCYTICS_SENTRY_DSN`` from the CI
    environment via a runtime hook — it is never hardcoded in this source.
    """
    if not getattr(sys, "frozen", False):
        # Never send from development / source-tree runs.
        return None
    return os.environ.get(_DSN_ENV_VAR) or None


def is_consent_given() -> bool | None:
    """Return the user's crash-reporting consent: True, False, or None (never asked)."""
    value = core_preferences.get(CONSENT_PREFERENCE_KEY)
    return value if isinstance(value, bool) else None


def set_consent(enabled: bool) -> None:
    """Persist the user's crash-reporting consent choice."""
    core_preferences.set(CONSENT_PREFERENCE_KEY, enabled)
    if enabled:
        init_crash_reporting()
    else:
        shutdown_crash_reporting()


def is_active() -> bool:
    """Whether Sentry has actually been initialized this session."""
    return _initialized


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        home = str(Path.home())
        if home and home in value:
            value = value.replace(home, "<home>")
        return _PATH_LIKE_RE.sub("<redacted-file>", value)
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    return value


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    return _scrub_value(event)


def init_crash_reporting() -> bool:
    """Initialize Sentry if a DSN is configured and consent has been given.

    Safe to call unconditionally at startup and again whenever consent
    changes — it's a no-op whenever either precondition isn't met, and
    idempotent once active.

    Returns:
        bool: Whether Sentry is active after this call.
    """
    global _initialized

    if _initialized:
        return True

    dsn = get_configured_dsn()
    if not dsn:
        logger.debug("Crash reporting not configured (no DSN for this build/environment).")
        return False

    if is_consent_given() is not True:
        logger.debug("Crash reporting not enabled (consent not given).")
        return False

    import sentry_sdk

    from karcytics.core.config import AppConfig

    # Only frozen builds reach here (get_configured_dsn guards this), so
    # environment is always "production" — captured here explicitly for
    # clarity in the Sentry dashboard.
    environment = "production" if getattr(sys, "frozen", False) else "development"

    sentry_sdk.init(
        dsn=dsn,
        release=f"karcytics@{AppConfig.CORE_VERSION}",
        environment=environment,
        send_default_pii=False,
        include_local_variables=False,
        traces_sample_rate=0.0,
        max_breadcrumbs=50,
        before_send=_before_send,  # type: ignore[arg-type]
    )
    _initialized = True
    logger.info("Crash reporting initialized (environment=%s).", environment)
    return True


def shutdown_crash_reporting() -> None:
    """Stop sending crash reports for the rest of this session."""
    global _initialized
    if not _initialized:
        return

    import sentry_sdk

    sentry_sdk.init(dsn=None)
    _initialized = False


def capture_error(
    message: str,
    exception: BaseException | None,
    plugin_id: str | None,
    traceback_str: str | None,
    level: Literal["fatal", "critical", "error", "warning", "info", "debug"] | None = "error",
) -> None:
    """Report an error to Sentry, if active. A silent no-op otherwise.

    Prefers ``sentry_sdk.capture_exception`` when a live exception object
    is available (the in-process case — gives Sentry a real, parsed
    stacktrace); falls back to ``capture_message`` with the pre-formatted
    traceback attached as extra context for the remote/isolated-plugin case,
    where only strings ever cross the wire.

    Both fatal and non-fatal errors are routed here — ``DiagnosticEngine``
    calls this for every reported error when crash reporting is active and
    consent has been given. All errors are auto-sent; users can see what was
    sent via the ``ErrorReportDialog`` that appears alongside the report.

    Args:
        message: Human-readable error description (file paths will be
            scrubbed by ``_before_send`` before leaving the machine).
        exception: Live exception object, or None for the string-only path.
        plugin_id: Plugin identifier to tag the event with, or None for
            core errors.
        traceback_str: Pre-formatted traceback string for the no-exception
            path; ignored when ``exception`` is provided.
        level: Sentry severity level — ``"fatal"``, ``"error"``,
            ``"warning"``, etc.  Defaults to ``"error"``.
    """
    if not is_active():
        return

    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        _tag_scope(scope, plugin_id, message)

        if exception is not None:
            sentry_sdk.capture_exception(exception)
            return

        if traceback_str:
            scope.set_extra("traceback", traceback_str)
        sentry_sdk.capture_message(message, level=level)


def capture_fatal_error(
    message: str,
    exception: BaseException | None,
    plugin_id: str | None,
    traceback_str: str | None,
) -> None:
    """Report a fatal error to Sentry.

    Thin wrapper around ``capture_error`` kept for backward compatibility
    with existing call sites in ``DiagnosticEngine.report_error``.
    """
    capture_error(
        message=message,
        exception=exception,
        plugin_id=plugin_id,
        traceback_str=traceback_str,
        level="fatal",
    )


def capture_error_data(error_data: dict[str, Any]) -> bool:
    """Send an already-built ``DiagnosticEngine`` ``error_data`` dict to Sentry.

    Used by ``DiagnosticsSettingsDialog``'s test-event action.

    Returns:
        bool: Whether anything was actually sent — False when crash
        reporting isn't active (no DSN configured, or consent not granted).
    """
    if not is_active():
        return False

    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        plugin_id = error_data.get("plugin_id")
        message = error_data.get("message", "")
        _tag_scope(scope, plugin_id, message)

        traceback_str = error_data.get("traceback")
        if traceback_str:
            scope.set_extra("traceback", traceback_str)
        sentry_sdk.capture_message(message, level="error")

    return True
