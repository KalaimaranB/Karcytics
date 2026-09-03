"""Dynamic plugin instantiation and architecture routing."""

import contextlib
import importlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from karcytics_sdk.plugin import KarcyticsPlugin
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from karcytics_sdk.host.module_status_widget import ModuleStatusWidget
    from karcytics_sdk.plugin.daemon import PluginUIDaemon

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def isolate_frozen_environment() -> Any:
    """Temporarily disables the PyInstaller frozen state while executing a context.

    The original state is restored when the context exits.

    Yields:
        None
    """
    was_frozen = getattr(sys, "frozen", False)
    if was_frozen:
        logger.debug("Temporarily suspending sys.frozen state to load external dependencies.")
        sys.frozen = False  # type: ignore[attr-defined]
    try:
        yield
    finally:
        if was_frozen:
            sys.frozen = True  # type: ignore[attr-defined]


class PluginLoaderFactory:
    """Instantiates plugin UI classes based on their architecture (V2 vs V3)."""

    @staticmethod
    def load_ui(module_id: str, mod_info: dict[str, Any]) -> type[QWidget] | None:
        """Load a plugin and obtain its UI panel class.

        Parameters:
            module_id (str): Identifier used to locate and report the plugin.
            mod_info (dict[str, Any]): Plugin metadata and mutable loading state.

        Returns:
            type[QWidget] | None: The plugin's UI panel class, or `None` when initialization
                fails with an exception that is contained by the loader.

        Raises:
            TypeError: If the plugin does not satisfy the required interface.
            ValueError: If plugin metadata or its entry point is invalid.
            PermissionError: If loading is denied.
        """
        if mod_info.get("manifest", {}).get("process_model") == "isolated":
            display_name = mod_info.get("manifest", {}).get("display_name", module_id)
            return PluginLoaderFactory._load_ui_isolated(module_id, display_name)

        if mod_info["loaded"]:
            return mod_info["plugin_ref"].get_panel_class()

        logger.info(
            "Loading plugin UI: module_id=%s package=%s path=%s trust_level=%s",
            module_id,
            mod_info["package_name"],
            mod_info["path"],
            mod_info["trust_level"],
        )

        try:
            manifest_dict = mod_info.get("manifest", {})

            with isolate_frozen_environment():
                if "entry_point" in manifest_dict:
                    # V3 Architecture with entry point and PluginContext
                    from karcytics_sdk.plugin.context import PluginContext
                    from karcytics_sdk.plugin.manifest import PluginManifest

                    from karcytics.core.task_scheduler import task_scheduler

                    # "event_bus" is deliberately absent, not present-with-None:
                    # there is no real Hub EventManager wired to in-process V3
                    # plugins yet (see docs/internal/25, "Migration status"). A
                    # plugin that never declares `requires = ["event_bus"]`
                    # is unaffected. One that does gets PluginContext.get()'s
                    # loud RuntimeError ("declared but the host environment
                    # did not provide it") the moment it asks for it, instead
                    # of a silent `None` that only fails later, confusingly,
                    # wherever the plugin tries to call a method on it.
                    services = {
                        "task_scheduler": task_scheduler,
                        "logger": logging.getLogger(f"plugin.{module_id}"),
                    }

                    pm = PluginManifest(
                        name=manifest_dict.get("name", module_id),
                        entry_point=manifest_dict["entry_point"],
                        sdk_version=manifest_dict.get("sdk_version", "2.0"),
                        requires=manifest_dict.get("requires", []),
                    )
                    context = PluginContext(services=services, manifest=pm)

                    module_name, func_name = manifest_dict["entry_point"].split(":")
                    plugin_module = importlib.import_module(module_name)
                    init_func = getattr(plugin_module, func_name)
                    plugin_instance = init_func(context)
                    mod_info["plugin_ref"] = plugin_instance
                else:
                    # V2 Legacy Architecture
                    package_name = f"karcytics.plugins.{mod_info['package_name']}"
                    plugin_module = importlib.import_module(package_name)

                    # Perform strict contract validation
                    if not isinstance(plugin_module, KarcyticsPlugin):  # type: ignore
                        msg = f"Module {module_id} failed interface validation. Missing required hooks."  # noqa: E501
                        logger.error(msg)
                        raise TypeError(msg)

                    mod_info["plugin_ref"] = plugin_module

            mod_info["loaded"] = True
            mod_info["status"] = "OK"
            return mod_info["plugin_ref"].get_panel_class()

        except Exception as e:
            logger.error(f"Fatal error loading module {module_id}: {e}", exc_info=True)
            mod_info["loaded"] = False
            mod_info["status"] = "FAILED"
            if isinstance(e, (TypeError, ValueError, PermissionError)):
                raise

            # Exception Containment: Do not crash the application if a plugin fails to initialize
            return None

    @staticmethod
    def _load_ui_isolated(module_id: str, display_name: str) -> type[QWidget]:
        """Return a zero-arg factory for module_id's status widget.

        Deliberately does none of what the in-process path above does:
        no `importlib.import_module` of the plugin's package, no
        `PluginEnvironmentInjector` path injection, no `sys.modules`
        bookkeeping — an isolated module's own code never enters the Hub's
        interpreter at all. `PluginUIDaemon.get_instance(module_id)` is a
        singleton keyed by plugin_id, so calling this repeatedly (e.g. the
        user re-opens an already-running module) reconnects to the same
        daemon rather than spawning a second one.

        Returns a callable rather than a literal `type[QWidget]` — callers
        already invoke this value as `PanelClass()` with no arguments, which
        a zero-arg closure satisfies identically.
        """
        from karcytics_sdk.host.module_status_widget import ModuleStatusWidget
        from karcytics_sdk.plugin.daemon import PluginUIDaemon

        def _factory() -> QWidget:
            daemon = PluginUIDaemon.get_instance(module_id)
            widget = ModuleStatusWidget(daemon, module_name=display_name)
            PluginLoaderFactory._wire_theme_sync(widget)
            PluginLoaderFactory._wire_diagnostics_forwarding(daemon)
            PluginLoaderFactory._wire_state_changed_forwarding(daemon)
            PluginLoaderFactory._wire_academy_handoff_forwarding(daemon)
            return widget

        return _factory  # type: ignore[return-value]

    @staticmethod
    def _wire_diagnostics_forwarding(daemon: "PluginUIDaemon") -> None:
        """Forward an isolated module's `diagnostics_error` events to the Hub's `DiagnosticEngine`.

        A plugin's own `karcytics_sdk.plugin.runtime_services.diagnostics
        .report_error(...)` (the isolated equivalent of an in-process
        plugin's `self.logger.error(..., exc_info=True)` reaching the Hub's
        `AutoReportHandler`) pushes a `"diagnostics_error"` event over this
        same daemon's frame channel — nothing on the Hub side was ever
        subscribed to `event_received` for that topic, so every one of those
        reports vanished silently before this existed. `get_instance()` is a
        singleton keyed by plugin_id (same as `_wire_theme_sync`'s widget),
        so guard against re-wiring a second listener on every reopen of an
        already-running module.
        """
        if getattr(daemon, "_diagnostics_forwarding_wired", False):
            return
        daemon._diagnostics_forwarding_wired = True  # type: ignore[attr-defined]

        def _on_event(topic: str, payload: object) -> None:
            if topic != "diagnostics_error" or not isinstance(payload, dict):
                return

            from karcytics.core.diagnostics import diagnostics

            diagnostics.report_error(
                message=payload.get("message", ""),
                plugin_id=payload.get("plugin_id"),
                fatal=bool(payload.get("fatal", False)),
                exception_repr=payload.get("exception"),
                traceback_str=payload.get("traceback"),
            )

        daemon.event_received.connect(_on_event)

    @staticmethod
    def _wire_state_changed_forwarding(daemon: "PluginUIDaemon") -> None:
        """Finish the `FILE_IMPORTED` wire for isolated modules.

        `ui_daemon.py`'s `_build_panel()` already connects the real panel's
        `state_changed` signal to `send_event("state_changed", {"file_count":
        ...})` over this daemon's frame channel — its own comment says the
        payload shape "must match what `WorkspaceWindow
        ._on_daemon_state_changed()` expects", but that Hub-side method was
        never written, so every one of those frames was silently dropped
        (same class of gap `_wire_diagnostics_forwarding` above closed for
        `diagnostics_error`). `WorkspaceWindow._on_wizard_state_changed()`
        can't fill this role itself — it reads `mw.wizard_panel.state`, and
        for an isolated module `mw.wizard_panel` is the `ModuleStatusWidget`
        this factory builds, not the real panel living in the daemon's own
        process; it has no `.state`.

        Tracks the last seen file_count per daemon (mirroring
        `WorkspaceWindow._last_import_file_count`'s own bookkeeping) so this
        only fires on an actual *increase*, not every state_changed tick.
        """
        if getattr(daemon, "_state_changed_forwarding_wired", False):
            return
        daemon._state_changed_forwarding_wired = True  # type: ignore[attr-defined]
        daemon._last_seen_file_count = 0  # type: ignore[attr-defined]

        def _on_event(topic: str, payload: object) -> None:
            if topic != "state_changed" or not isinstance(payload, dict):
                return
            file_count = payload.get("file_count")
            if not isinstance(file_count, int):
                return
            last_seen = getattr(daemon, "_last_seen_file_count", 0)
            if file_count <= last_seen:
                return
            daemon._last_seen_file_count = file_count  # type: ignore[attr-defined]

            from karcytics.core.event_bus import KarcyticsEvent, event_bus

            event_bus.emit(KarcyticsEvent.FILE_IMPORTED, "")

        daemon.event_received.connect(_on_event)

    @staticmethod
    def _wire_academy_handoff_forwarding(daemon: "PluginUIDaemon") -> None:
        """Resumes the Hub's `core_intro` tour once its handed-off module phase finishes.

        Inside the isolated plugin process, `karcytics_plugins.flow_cytometry.ui_daemon`'s
        `_maybe_start_onboarding_handoff()` sends an
        `"academy_handoff_complete"` frame over this same daemon's channel
        when its local `core_intro_handoff` course completes (see
        `plugin_loader.py::_instantiate_isolated_overlay`, which is what
        told that process to start it in the first place, via
        `daemon.pending_academy_handoff`). Advancing straight to
        `"analysis_saved_confirm_spotlight"` here is what lets the Hub's own
        tour pick back up for the graduation phase, back in the Hub UI.
        """
        if getattr(daemon, "_academy_handoff_forwarding_wired", False):
            return
        daemon._academy_handoff_forwarding_wired = True  # type: ignore[attr-defined]

        def _on_event(topic: str, _payload: object) -> None:
            if topic != "academy_handoff_complete":
                return

            from karcytics.core.tutorial_manager import global_tutorial_manager

            active_course = global_tutorial_manager.active_course
            if active_course and active_course.id == "core_intro_v1":
                global_tutorial_manager.next_step("analysis_saved_confirm_spotlight")

        daemon.event_received.connect(_on_event)

    @staticmethod
    def _wire_theme_sync(widget: "ModuleStatusWidget") -> None:
        """Keep an isolated module's window in sync with the Hub's live colors.

        `ModuleStatusWidget` itself stays Hub-agnostic (it only knows how to
        relay a `dict[str, str]` via `push_theme()`) — reading the Hub's
        actual `Colors` class and deciding *when* to push belongs here, not
        in the SDK. Pushed once immediately when the module's window becomes
        visible (Running), and again on every subsequent Hub theme change —
        `push_theme()` itself no-ops if the module isn't Running yet.
        """
        from karcytics.core.core_services_bootstrap import current_theme_colors
        from karcytics.ui.theme import theme_manager as hub_theme_manager

        def _push_current_theme() -> None:
            widget.push_theme(current_theme_colors())

        def _on_state_changed(state: str) -> None:
            if state == widget.STATE_RUNNING:
                _push_current_theme()

        def _disconnect_on_destroyed() -> None:
            # hub_theme_manager is a long-lived singleton — without this,
            # closing the module would leave it holding a connection to a
            # Python wrapper around a deleted C++ QWidget, which
            # push_theme()'s own sip.isdeleted() guard tolerates but which
            # would otherwise leak. Both exceptions below are the same class
            # of "already gone" race workspace_window.py's own theme_changed
            # disconnect already guards against: TypeError if this
            # connection was somehow already removed, RuntimeError if
            # hub_theme_manager's own C++ object outlived Python's shutdown
            # ordering and is itself gone by the time this fires (observed
            # during interpreter teardown, not during normal operation).
            with contextlib.suppress(TypeError, RuntimeError):
                hub_theme_manager.theme_changed.disconnect(_push_current_theme)

        widget.state_changed.connect(_on_state_changed)
        hub_theme_manager.theme_changed.connect(_push_current_theme)
        widget.destroyed.connect(_disconnect_on_destroyed)

    @staticmethod
    def verify_dependencies(plugin_path: Path, manifest: dict) -> None:
        """Verify that the plugin's isolated Python environment is available.

        Parameters:
            plugin_path (Path): Path to the plugin directory.
            manifest (dict): Plugin manifest used to identify the plugin in error messages.

        Raises:
            RuntimeError: If the plugin's Python environment cannot be found.
        """
        venv = plugin_path / ".venv"
        deps_missing = True
        candidates = []
        if sys.platform == "win32":
            candidates.append(venv / "Scripts" / "python.exe")
        else:
            major, minor = sys.version_info.major, sys.version_info.minor
            candidates.append(venv / "bin" / f"python{major}.{minor}")
            candidates.append(venv / "bin" / "python3")

        for c in candidates:
            if c.exists():
                deps_missing = False
                break

        if deps_missing:
            raise RuntimeError(
                f"DependencyMissingError: The plugin '{manifest.get('name', 'Unknown')}' "
                f"is missing its Python environment. Please reinstall the plugin from the Store to repair it."  # noqa: E501
            )
