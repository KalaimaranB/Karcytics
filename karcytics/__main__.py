import logging  # noqa: D100
import sys
from pathlib import Path
from typing import Any, Final


# --- STABILIZATION: Bootstrap Logging ---
# This MUST happen before any wasm/karcytics imports
def setup_logging() -> Path:
    """Configure application logging and create the Karcytics log files.

    Splits logging into ``~/.karcytics/logs/core.log``,
    ``logs/ipc.log`` (core<->plugin transport traffic), and
    ``logs/plugins/<plugin_id>.log`` — see `karcytics.core.logging_setup`.

    Returns:
        Path: The path to the core log file.
    """
    from pathlib import Path

    from karcytics.core.logging_setup import configure_logging

    return configure_logging(Path.home() / ".karcytics")


def install_exception_hook():
    """Catch unhandled exceptions and route them through the diagnostic engine."""
    import sys

    from karcytics.core.diagnostics import diagnostics

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Log it officially through our diagnostics engine
        diagnostics.report_error(
            message=f"Unhandled Exception: {exc_value}", exception=exc_value, fatal=True
        )

    sys.excepthook = handle_exception


class KarcyticsApp:
    """Main application class for Karcytics."""

    def __init__(self, module_manager, updater, core_services_server=None):
        """Initialize the Qt application and store dependencies.

        Parameters:
            module_manager: Manager used to load and reload application modules.
            updater: Service used to retrieve and update plugins.
            core_services_server: The Hub's already-started `CoreServicesServer`
                (see `core_services_bootstrap.start_core_services`), stopped on
                quit. `None` is accepted so tests/tools that build a
                `KarcyticsApp` without a full boot sequence don't need one.
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        # CRITICAL: WebEngine initialization must happen BEFORE QApplication is created.
        with contextlib.suppress(ImportError):
            import PyQt6.QtWebEngineWidgets  # noqa: F401

        print("1. Initializing QApplication...")
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        self.app = QApplication(sys.argv)

        # CRITICAL: Theme is loaded from preferences BEFORE QApplication exists.
        # Now that QApplication exists, we must compile and apply the global stylesheet.
        from karcytics.ui.theme import theme_manager

        theme_manager._apply_global_stylesheet()

        # --- BRANDING: Set Global Application Icon ---
        from PyQt6.QtGui import QIcon

        from karcytics.core.resource_manager import resource_path

        # On macOS, the Dock icon is natively and perfectly managed by the .app bundle's Info.plist.
        # Setting a window icon with .icns can overwrite and reset the native round icon to a generic square if Qt's icns plugin is not loaded.  # noqa: E501
        if sys.platform != "darwin":
            icon_path = resource_path("icon.icns")
            if icon_path.exists():
                self.app.setWindowIcon(QIcon(str(icon_path)))

        self.module_manager = module_manager
        self.updater = updater
        self.core_services_server = core_services_server

        # Apply SDK global styles (Fusion style engine, QPalette, QToolTip CSS).
        # This MUST be called after QApplication is created — the module-level call
        # in components.py fires too early (before QApplication exists) and is a no-op.
        try:
            from karcytics_sdk.plugin.components import apply_global_sdk_styles

            apply_global_sdk_styles()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to apply SDK styles: {e}")

    def run(self) -> None:
        """Display the project hub and start the PyQt event loop."""
        print("4. Showing Hub Window...")
        self.show_hub()

        print("5. Starting PyQt Event Loop...")
        from karcytics.core.task_scheduler import task_scheduler

        self.app.aboutToQuit.connect(task_scheduler.shutdown)
        if self.core_services_server is not None:
            self.app.aboutToQuit.connect(self.core_services_server.stop)

        sys.exit(self.app.exec())

    def show_hub(self) -> None:
        """Display the project launcher window."""
        from karcytics.ui.windows.project_launcher import ProjectLauncherWindow

        self.hub = ProjectLauncherWindow(
            self.module_manager, self.updater, self.open_store, self.show_hub
        )
        self.hub.show()

    def open_store(self, parent_window) -> None:
        """Open the plugin store dialog and refresh the parent window after it closes.

        Parameters:
            parent_window: The window that owns the dialog and may be refreshed afterward.
        """
        from karcytics.ui.dialogs.plugin_store import PluginStoreDialog

        dialog = PluginStoreDialog(self.module_manager, self.updater, parent=parent_window)
        dialog.exec()

        # Explicitly cleanup the tutorial overlay and delete the C++ dialog object
        # to guarantee we don't leak memory or dangling event bus subscriptions.
        dialog.tutorial_overlay._cleanup()
        dialog.deleteLater()

        self.module_manager.reload_modules()
        if hasattr(parent_window, "refresh_ui"):
            parent_window.refresh_ui()


def bootstrap_sdk():
    """Dynamic Bootstrapper for Karcytics SDK.

    Checks ~/.karcytics/sdk/ for a hot-patched/updated SDK.
    If it exists and is cryptographically verified against the Root Key,
    we prepend it to sys.path so the application runs the updated version.
    Otherwise, we fall back to the built-in system karcytics-sdk.
    """
    # Temporarily disabled due to security concerns
    return False

    import sys
    from pathlib import Path

    sdk_dir = Path.home() / ".karcytics" / "sdk"
    if sdk_dir.exists():
        try:
            from karcytics_sdk.host import TrustManager

            trust_mgr = TrustManager()
            result = trust_mgr.verify_plugin(sdk_dir)
            if result.success:
                sys.path.insert(0, str(sdk_dir / "src"))
                import logging

                logging.info(
                    f"🚀 [HOT PATCH] Successfully loaded cryptographically verified SDK from {sdk_dir}"  # noqa: E501
                )
                return True
            import logging

            logging.warning(
                f"⚠️ [HOT PATCH] SDK verification failed at {sdk_dir}: {result.error_message}. Falling back to default SDK."  # noqa: E501
            )
        except Exception as e:
            import logging

            logging.error(
                f"❌ [HOT PATCH] Failed to bootstrap dynamic SDK: {e}. Falling back to default SDK."
            )
    return False


# Smoke test timeout configuration
SMOKE_TEST_TIMEOUT_MS = 15000  # Maximum time to wait for async data loading
SMOKE_TEST_TICK_MS = 1000  # Delay before quitting when no async data expected
SMOKE_TEST_ISOLATED_SPAWN_TIMEOUT_S = 45.0  # Daemon spawn + ready handshake budget

_BIEXPONENTIAL_PROBE_VALUES: Final[tuple[float, ...]] = (1.0, 100.0, 10_000.0, 200_000.0)


def _install_plugin_for_smoke_test(module_manager, plugin_id: str, logger: logging.Logger) -> None:
    """Force-download and install `plugin_id` from the remote registry.

    Re-scans `module_manager` so its manifest (in particular `process_model`)
    is available to the caller. Shared by both the in-process and isolated
    smoke-test paths — which plugin architecture is in play is decided
    *after* this runs, from the freshly-discovered manifest, not before.
    """
    from karcytics.core.network.plugin_registry_fetcher import PluginRegistryFetcher
    from karcytics.core.network_updater import NetworkUpdater

    updater = NetworkUpdater()
    logger.info(f"Attempting to download and install {plugin_id}...")
    registry = updater.fetch_remote_registry(updater.registry_url)
    plugin_info = registry.get("plugins", {}).get(plugin_id)

    if not plugin_info:
        raise RuntimeError(f"Plugin {plugin_id} not found in remote registry.")

    # The Distribution index only carries `repo_url` — mirror what the real Store
    # flow does in PluginRegistryFetcher.fetch_all: enrich name/version from the
    # plugin's own pyproject.toml, then resolve an actual install URL from its
    # newest GitHub Release, before handing off to install_plugin.
    repo_url = plugin_info.get("repo_url")
    if not repo_url:
        raise RuntimeError(f"Plugin {plugin_id} has no repo_url in remote registry.")

    manifest = PluginRegistryFetcher.fetch(plugin_id, repo_url)
    if not manifest:
        raise RuntimeError(f"Could not fetch pyproject.toml manifest for plugin {plugin_id}.")
    PluginRegistryFetcher.enrich_entry(plugin_info, manifest)

    download_url = PluginRegistryFetcher.resolve_download_url(plugin_id, repo_url)
    if not download_url:
        raise RuntimeError(f"Could not resolve a download URL for plugin {plugin_id}.")
    plugin_info["download_url"] = download_url

    success, msg = updater.install_plugin(plugin_id, plugin_info)
    if not success:
        raise RuntimeError(f"Failed to install plugin: {msg}")

    # Install Python dependencies for the newly downloaded plugin
    from karcytics_sdk.plugin.manifest_parser import ManifestParser

    from karcytics.core.package_manager import PackageManager

    pm = PackageManager()
    plugin_dir = updater.plugin_dir / plugin_id
    manifest_path = plugin_dir / "pyproject.toml"
    if manifest_path.exists():
        manifest = ManifestParser().parse_file(str(manifest_path))
        deps = manifest.get("python_dependencies")
        if deps is None:
            deps_list = manifest.get("core_dependencies", [])
            deps = dict.fromkeys(deps_list, "")

        if deps:
            logger.info(
                f"Installing {len(deps)} dependencies for {plugin_id} into isolated venv..."
            )
            pm.resolve_and_install_all(deps, plugin_dir)

    # Re-scan installed modules so module_manager.modules[plugin_id]["manifest"]
    # reflects what was just installed, including process_model.
    module_manager.reload_modules()


def _run_smoke_test_in_process(module_manager, plugin_id: str, data_file: str | None) -> int:  # noqa: C901, PLR0915
    """Drive an in-process (V2/V3) plugin's real panel directly.

    Exactly as `PluginLoaderManager` would in the live Hub — `PanelClass()`
    returns the plugin's actual widget, in this same interpreter, so its
    `load_workflow`/`panel_ready`/`data_ready`/`begin_async_init` are the
    plugin's own.

    This is the pre-isolation smoke test's logic, unchanged: it only ever
    applied to plugins whose code genuinely runs in the Hub's process, and
    it still does for those. See `_run_smoke_test_isolated` for the
    `process_model = "isolated"` case, where none of these attributes exist
    on what `PanelClass()` returns.
    """
    from typing import NoReturn

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox

    logger = logging.getLogger("Karcytics.SmokeTest")
    app = QApplication.instance() or QApplication(sys.argv)

    data_ready_emitted = False
    panel_ready_emitted = False
    load_workflow_failed = False

    logger.info(
        "Loading plugin UI class to trigger all heavy imports (Numba, Matplotlib, C-Extensions)..."
    )

    # Prevent modal dialogs from hanging the headless runner
    def _mock_msgbox(*_args: object, **_kwargs: object) -> None:
        return None

    def _mock_question(*_args: object, **_kwargs: object) -> QMessageBox.StandardButton:
        return QMessageBox.StandardButton.Yes

    QMessageBox.information = _mock_msgbox  # type: ignore[assignment]
    QMessageBox.warning = _mock_msgbox  # type: ignore[assignment]
    QMessageBox.critical = _mock_msgbox  # type: ignore[assignment]
    QMessageBox.question = _mock_question  # type: ignore[assignment]

    PanelClass = module_manager.load_module_ui(plugin_id)  # noqa: N806
    if PanelClass is None:
        raise RuntimeError(f"Plugin {plugin_id} exposes no UI class.")
    panel = PanelClass()

    if data_file and hasattr(panel, "load_workflow"):
        logger.info(f"Injecting test data file: {data_file}")

        try:
            # Monkeypatch fcs_io to explicitly fail if flowkit (daemon) is NOT used.
            # Only meaningful in-process — an isolated plugin's own analysis code
            # never enters this interpreter at all, see _run_smoke_test_isolated.
            import karcytics_plugins.flow_cytometry.analysis.fcs_io as fcs_io  # type: ignore[import-untyped, import-not-found]

            def _crash_fcsparser(*_args: object, **_kwargs: object) -> NoReturn:  # noqa: ARG001
                raise RuntimeError(
                    "Smoke test explicitly failed: flowkit was not used! "
                    "Daemon virtual environment may be broken."
                )

            fcs_io._load_with_fcsparser = _crash_fcsparser
            logger.info("Monkeypatched fcs_io to strictly enforce flowkit usage via daemon.")
        except ImportError:
            if plugin_id == "flow_cytometry":
                raise

        # If the plugin signals when async data is ready, wait for it
        if hasattr(panel, "data_ready"):
            logger.info("Hooking into plugin data_ready signal for delayed exit.")

            def _on_data_ready() -> None:
                nonlocal data_ready_emitted
                data_ready_emitted = True
                logger.info("Smoke test: data_ready signal received. Exiting cleanly.")
                app.quit()

            panel.data_ready.connect(_on_data_ready)

            def _on_timeout() -> None:
                if not data_ready_emitted:
                    logger.error("Smoke test: timeout reached without data_ready emission.")
                app.quit()

            QTimer.singleShot(SMOKE_TEST_TIMEOUT_MS, _on_timeout)

        # Connect panel_ready BEFORE calling begin_async_init to avoid race condition
        if hasattr(panel, "panel_ready"):

            def _on_panel_ready() -> None:
                nonlocal panel_ready_emitted, load_workflow_failed
                if panel_ready_emitted:
                    logger.warning(
                        "Smoke test: panel_ready emitted multiple times, "
                        "ignoring subsequent emissions."
                    )
                    return
                panel_ready_emitted = True
                try:
                    panel.load_workflow(None, filename=data_file)
                except Exception as e:
                    load_workflow_failed = True
                    logger.exception("Smoke test: load_workflow raised exception: %s", e)
                    app.quit()
                    return
                if not hasattr(panel, "data_ready"):
                    logger.info(
                        "Smoke test: load_workflow invoked via panel_ready. "
                        "No data_ready signal, exiting cleanly."
                    )
                    app.quit()

            panel.panel_ready.connect(_on_panel_ready)

            def _on_panel_ready_timeout() -> None:
                if not panel_ready_emitted:
                    logger.error("Smoke test: timeout reached without panel_ready emission.")
                    app.quit()

            if not hasattr(panel, "data_ready"):
                QTimer.singleShot(SMOKE_TEST_TIMEOUT_MS, _on_panel_ready_timeout)
        else:
            panel.load_workflow(None, filename=data_file)

    if hasattr(panel, "begin_async_init"):
        panel.begin_async_init()

    if not (data_file and hasattr(panel, "data_ready")) and not (
        data_file and hasattr(panel, "panel_ready")
    ):
        QTimer.singleShot(SMOKE_TEST_TICK_MS, app.quit)
    app.exec()

    if data_file and hasattr(panel, "panel_ready") and load_workflow_failed:
        logger.error("SMOKE TEST FAILED: load_workflow raised an exception.")
        return 1

    if data_file and hasattr(panel, "data_ready") and not data_ready_emitted:
        logger.error("SMOKE TEST FAILED: data_ready signal was never emitted.")
        return 1

    # Exercise the biexponential (Logicle) transform directly. This is the exact
    # code path that broke on Windows when bokeh (a transitive flowkit dependency)
    # failed to resolve its own template environment inside the frozen app — it
    # only ever triggers the first time a user renders a biexponential/log axis
    # (e.g. a fluorescence channel), which the default linear scatter view this
    # smoke test otherwise loads never does. Only valid in-process, same reason
    # as the fcs_io monkeypatch above — flow_cytometry is isolated today, so
    # this branch is currently unreachable in practice, kept for a future
    # in-process plugin with the same regression shape.
    if plugin_id == "flow_cytometry" and data_ready_emitted:
        try:
            import numpy as np
            from karcytics_plugins.flow_cytometry.analysis.transforms import (  # type: ignore[import-untyped, import-not-found]
                biexponential_transform,
            )

            biexponential_transform(np.array(_BIEXPONENTIAL_PROBE_VALUES))
            logger.info("Smoke test: biexponential_transform executed successfully.")
        except Exception as e:
            logger.error(f"SMOKE TEST FAILED: biexponential_transform raised: {e}")
            return 1

    logger.info("Smoke test passed all critical execution paths. Exiting cleanly.")
    return 0


def _confirm_isolated_daemon_boots(daemon, logger: logging.Logger) -> int:
    """No data file: confirm the isolated daemon boots and reaches ready, nothing more."""
    logger.info("No data file provided — confirming the isolated daemon boots and reaches ready.")
    try:
        daemon.ensure_started(timeout=SMOKE_TEST_ISOLATED_SPAWN_TIMEOUT_S)
    except Exception as e:
        logger.error(f"SMOKE TEST FAILED: isolated daemon failed to start: {e}")
        return 1
    logger.info(
        "Smoke test passed all critical execution paths (isolated plugin, no data). Exiting."
    )
    return 0


def _inject_and_await_isolated_workflow(
    daemon,
    data_file: str,
    events: list[tuple[str, object]],
    crashed: dict[str, bool],
    logger: logging.Logger,
) -> int:
    """Inject `data_file` via the real `inject_workflow` RPC.

    Then poll for the worker's async `panel_data_ready`/`workflow_injection_failed`
    response event.
    """
    import time

    from PyQt6.QtWidgets import QApplication

    logger.info(f"Injecting test data file via inject_workflow RPC: {data_file}")
    try:
        # payload must be a dict, not None: the worker only treats a
        # workflow as "pending" (panel_loader.py's `_phase2_finalize`,
        # mirrored here) when `_deferred_workflow_payload is not None`.
        # {} is not None and is otherwise unused by the CI direct-FCS
        # injection branch this filename triggers inside load_workflow().
        result = daemon.call(
            "inject_workflow",
            {"payload": {}, "filename": data_file},
            timeout=SMOKE_TEST_ISOLATED_SPAWN_TIMEOUT_S,
        )
    except Exception as e:
        logger.error(f"SMOKE TEST FAILED: isolated daemon failed to start or respond: {e}")
        return 1

    if result.get("status") != "ok":
        logger.error(f"SMOKE TEST FAILED: inject_workflow request was rejected: {result}")
        return 1

    deadline = time.monotonic() + (SMOKE_TEST_TIMEOUT_MS / 1000)
    topics: dict[str, object] = {}
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if crashed["flag"]:
            break
        topics = dict(events)
        if "panel_data_ready" in topics or "workflow_injection_failed" in topics:
            break
        time.sleep(0.02)

    if crashed["flag"]:
        logger.error("SMOKE TEST FAILED: isolated worker process exited unexpectedly.")
        return 1

    if "workflow_injection_failed" in topics:
        error = topics["workflow_injection_failed"]
        logger.error(f"SMOKE TEST FAILED: workflow injection failed: {error}")
        return 1

    if "panel_data_ready" not in topics:
        logger.error("SMOKE TEST FAILED: timeout reached without panel_data_ready.")
        return 1

    logger.info("Smoke test: panel_data_ready received. Isolated plugin loaded data successfully.")
    logger.info(
        "Smoke test passed all critical execution paths (isolated plugin). Exiting cleanly."
    )
    return 0


def _run_smoke_test_isolated(module_manager, plugin_id: str, data_file: str | None) -> int:
    """Drive an isolated plugin through the real `PluginUIDaemon` protocol.

    Unlike an in-process panel, `module_manager.load_module_ui()` returns a
    `ModuleStatusWidget` factory for one of these (see
    `PluginLoaderFactory._load_ui_isolated`), which deliberately has no
    `load_workflow` at all.

    Requires the caller to have already started `CoreServicesServer`
    (`_run_smoke_test` does this before dispatching here) — without it, the
    worker's own startup theme gate (`_confirm_hub_theme_or_exit`) refuses to
    build any window and exits immediately; see docs/internal/26.
    """
    from karcytics_sdk.plugin.daemon import PluginUIDaemon
    from PyQt6.QtWidgets import QApplication

    logger = logging.getLogger("Karcytics.SmokeTest")
    # Must keep this reference alive: with no Python-side owner, PyQt/SIP
    # destroys the underlying QApplication as soon as this statement
    # completes (refcount hits zero), so the very next QWidget construction
    # below aborts with "Must construct a QApplication before a QWidget."
    # `app` itself is never called directly — it only needs to stay alive so
    # `daemon.event_received` has *some* QApplication to pump processEvents()
    # against (see the polling loop below).
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

    logger.info(
        "Loading isolated plugin UI via the real Hub routing path "
        "(ModuleManager -> PluginLoaderFactory)..."
    )
    PanelClass = module_manager.load_module_ui(plugin_id)  # noqa: N806
    if PanelClass is None:
        logger.error(f"SMOKE TEST FAILED: isolated plugin '{plugin_id}' produced no panel factory.")
        return 1

    daemon = PluginUIDaemon.get_instance(plugin_id)
    # A raw FCS file is the *first* thing this panel ever loads, same as the
    # in-process path's `panel.load_workflow(None, filename=data_file)` — so
    # this must go through the same "reopen with a workflow already queued"
    # mechanism a real project reopen uses (see
    # karcytics/ui/windows/workspace/plugin_loader.py's
    # `_instantiate_isolated_overlay`), not the "module already running"
    # dynamic-inject path. Without pending_workflow, the panel's own
    # one-shot `data_ready` fires once for its empty startup state before
    # our injected file ever loads, and never fires again for the real load.
    daemon.pending_workflow = bool(data_file)

    events: list[tuple[str, object]] = []
    daemon.event_received.connect(lambda topic, payload: events.append((topic, payload)))
    crashed = {"flag": False}
    daemon.process_exited.connect(lambda: crashed.__setitem__("flag", True))

    # Exercises the real Hub-side widget construction path too — proves
    # ModuleManager/PluginLoaderFactory routing to an isolated plugin
    # produces a working ModuleStatusWidget, not just that the daemon
    # singleton (driven directly below) can be started.
    PanelClass()

    try:
        if not data_file:
            return _confirm_isolated_daemon_boots(daemon, logger)
        return _inject_and_await_isolated_workflow(daemon, data_file, events, crashed, logger)
    finally:
        PluginUIDaemon.stop_instance(plugin_id)


def _run_smoke_test(argv: list[str]) -> int:
    """Run a smoke test for a specified plugin in a headless PyInstaller environment.

    Dispatches to `_run_smoke_test_in_process` or `_run_smoke_test_isolated`
    based on the plugin's own `process_model` — the two architectures share
    almost nothing at this level (an isolated `PanelClass()` is a
    `ModuleStatusWidget`, not the plugin's real panel; see
    docs/internal/24_Plugin_Communication_Protocol.md), so forcing one code
    path to cover both silently skipped every isolated-plugin check this
    used to run, which is exactly the regression this split fixes.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", dest="plugin_id")
    parser.add_argument("data_file", nargs="?", default=None)
    args, _ = parser.parse_known_args(argv[1:])

    logger = logging.getLogger("Karcytics.SmokeTest")
    logger.info(f"--- SMOKE TEST SEQUENCE STARTED FOR {args.plugin_id} ---")

    from karcytics.core.module_manager import ModuleManager

    module_manager = ModuleManager()

    if not args.plugin_id:
        # Bare boot check: no plugin requested, just prove the app starts.
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(argv)
        QTimer.singleShot(SMOKE_TEST_TICK_MS, app.quit)
        app.exec()
        logger.info("Smoke test passed all critical execution paths. Exiting cleanly.")
        return 0

    _install_plugin_for_smoke_test(module_manager, args.plugin_id, logger)

    if args.plugin_id not in module_manager.modules:
        raise RuntimeError(
            f"Plugin '{args.plugin_id}' was installed but is not discoverable by ModuleManager."
        )
    is_isolated = (
        module_manager.modules[args.plugin_id]["manifest"].get("process_model") == "isolated"
    )

    # An isolated plugin's worker calls back into CoreServicesServer for its
    # startup theme confirmation before it will build any window at all (see
    # docs/internal/26_Server_Client_Lifecycle.md) — without this, every
    # isolated smoke test would hang or fail the ready handshake before ever
    # reaching the plugin's own code. Harmless, and arguably more faithful to
    # a real boot, for the in-process path too: real `_start_application`
    # always starts this before loading any plugin.
    from karcytics.core.core_services_bootstrap import start_core_services

    core_services_server = start_core_services()
    try:
        if is_isolated:
            return _run_smoke_test_isolated(module_manager, args.plugin_id, args.data_file)
        return _run_smoke_test_in_process(module_manager, args.plugin_id, args.data_file)
    finally:
        core_services_server.stop()


def main():
    """Start the Karcytics application or dispatch supported command-line modes.

    Handles SDK and AI server commands, optional plugin smoke tests, normal
    application initialization, and fatal startup errors.
    """
    log_file = setup_logging()

    from karcytics.core.config import migrate_legacy_app_data

    migrate_legacy_app_data()

    bootstrap_sdk()

    # Handle SDK CLI commands if detected
    if len(sys.argv) > 1 and sys.argv[1] == "sdk":
        try:
            from karcytics_sdk.sdk_cli import main as sdk_main

            sdk_main()
            return
        except Exception as e:
            logging.error(f"SDK Error: {e}")
            sys.exit(1)

    # Handle AI Server launch (used by the internal AI manager)
    if len(sys.argv) > 1 and sys.argv[1] == "ai-server":
        try:
            import llama_cpp.server.__main__ as ai_server

            # Remove 'ai-server' from args so llama_cpp.server sees its own flags
            sys.argv.pop(1)
            ai_server.main()
            return
        except Exception as e:
            logging.error(f"AI Server Startup Error: {e}")
            sys.exit(1)

    # Handle Smoke Test for PyInstaller validation (E2E CI/CD)
    if len(sys.argv) > 1 and sys.argv[1].startswith("--smoke-test"):
        try:
            sys.exit(_run_smoke_test(sys.argv))
        except Exception:
            import traceback

            logging.critical(f"SMOKE TEST FATAL CRASH:\n{traceback.format_exc()}")
            sys.exit(1)

    _start_application(log_file)


def _on_error_event(error_data: Any) -> None:
    # CRITICAL: We cannot show a QDialog if QApplication hasn't been created.
    # If it's a fatal error, we'll let the global exception handler in main() catch it
    # and show a native message box there.
    from PyQt6.QtWidgets import QApplication

    if not QApplication.instance():
        return

    if isinstance(error_data, dict) and "title" in error_data and "message" in error_data:
        from karcytics.core.event_bus import ErrorEventPayload
        from karcytics.shared.ui.alerts import show_error

        # Narrow the type for strict Mypy compatibility
        typed_error: ErrorEventPayload = error_data  # type: ignore[assignment]
        show_error(
            QApplication.activeWindow(),
            typed_error["title"],
            typed_error["message"],
        )
        return

    from karcytics.ui.dialogs.error_report import ErrorReportDialog

    dialog = ErrorReportDialog(error_data)
    dialog.exec()


def _start_application(log_file: Path) -> None:

    try:
        logger = logging.getLogger("Karcytics")
        logger.info("--- APP BOOT SEQUENCE STARTED ---")

        # Import core modules only after logging is setup
        from karcytics.core.module_manager import ModuleManager
        from karcytics.core.network_updater import NetworkUpdater

        module_manager = ModuleManager()
        updater = NetworkUpdater()

        # Reachable by any isolated module's process, regardless of how it
        # was spawned — see core_services_bootstrap for what's exposed and
        # why task scheduling deliberately isn't.
        from karcytics.core.core_services_bootstrap import start_core_services

        core_services_server = start_core_services()

        # Initialize diagnostics and connect UI listener
        from karcytics.core.event_bus import KarcyticsEvent, event_bus

        # Restore Global Preferences (e.g. Theme)
        from karcytics.core.preferences import core_preferences

        # Initialize global ToastManager for warnings
        from karcytics.ui.theme import theme_manager

        saved_theme = core_preferences.get("theme")
        if saved_theme:
            theme_path = Path(saved_theme)
            if theme_path.exists():
                theme_manager.load_theme(theme_path)

        # No-ops unless both a DSN is configured and the user has opted in —
        # see crash_reporting.py. Developer-mode Sentry testing is available
        # via Help → Diagnostics & Privacy → Developer Tools (dev builds only).
        from karcytics.core import crash_reporting
        from karcytics.core.crash_reporting import init_crash_reporting, set_module_manager

        set_module_manager(module_manager)
        init_crash_reporting()

        # Show the first-run consent dialog once if the user hasn't made a
        # choice yet and this is a production build with a DSN configured.
        # The 800 ms delay lets the main window appear first so the dialog
        # doesn't flash before the UI is ready.
        from PyQt6.QtCore import QTimer

        if crash_reporting.get_configured_dsn() and crash_reporting.is_consent_given() is None:

            def _show_consent_dialog() -> None:
                from karcytics.ui.dialogs.crash_reporting_consent_dialog import (
                    CrashReportingConsentDialog,
                )

                CrashReportingConsentDialog().exec()

            QTimer.singleShot(800, _show_consent_dialog)

        event_bus.subscribe(KarcyticsEvent.ERROR_OCCURRED, _on_error_event)
        install_exception_hook()

        app = KarcyticsApp(module_manager, updater, core_services_server=core_services_server)
        app.run()
    except Exception as e:
        import traceback

        error_msg = f"FATAL BOOT ERROR:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        logging.critical(error_msg)

        from PyQt6.QtWidgets import QApplication, QMessageBox

        # Ensure we have a QApplication instance to show the message box
        _app = QApplication.instance()
        if not _app:
            # Create a dummy app just for the dialog
            _app = QApplication(sys.argv)

        QMessageBox.critical(
            None,
            "Karcytics Crash",
            f"Karcytics failed to start.\n\nError: {str(e)}\n\n"
            f"Check the log for details:\n{log_file}",
        )

        sys.exit(1)


if __name__ == "__main__":
    import contextlib
    import multiprocessing

    multiprocessing.freeze_support()
    with contextlib.suppress(RuntimeError):
        multiprocessing.set_start_method("spawn", force=True)

    main()
