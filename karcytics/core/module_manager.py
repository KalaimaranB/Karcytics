"""Dynamic Plugin/Module Loader for Karcytics (Facade)."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from karcytics_sdk.host import TrustManager

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

# HACK: Import the base plugins namespace so we can expand it
import karcytics.plugins
from karcytics.core.event_bus import KarcyticsEvent, event_bus
from karcytics.core.plugins.discovery import PluginDiscoveryService
from karcytics.core.plugins.environment import PluginEnvironmentInjector
from karcytics.core.plugins.loader import PluginLoaderFactory
from karcytics.core.resource_manager import resource_path

logger = logging.getLogger(__name__)


class ModuleManager:
    """Discovers, manages, and loads Karcytics analysis modules dynamically."""

    def __init__(self, trust_manager: TrustManager | None = None):
        """Initialize module manager with plugin directories and lifecycle subscriptions.

        Parameters:
            trust_manager (TrustManager | None): Trust manager to use, or None to create a default
            manager.
        """
        # 1. The built-in plugins (baked into the PyInstaller .app)
        self.internal_plugins_dir = resource_path("karcytics/plugins")

        # 2. The dynamic downloaded plugins (safe from macOS code-signing blocks)
        self.user_plugins_dir = Path.home() / ".karcytics" / "plugins"
        self.user_plugins_dir.mkdir(parents=True, exist_ok=True)

        # 3. Bind the user folder to the internal plugin namespace
        if str(self.user_plugins_dir) not in karcytics.plugins.__path__:
            karcytics.plugins.__path__.append(str(self.user_plugins_dir))
            logger.info(f"Appended user directory to plugin namespace: {self.user_plugins_dir}")

        self.modules: dict[str, Any] = {}
        self.trust_manager = trust_manager or TrustManager()
        self._discover_modules()

        # Subscribe to plugin lifecycle events
        event_bus.subscribe(KarcyticsEvent.PLUGIN_INSTALLED, lambda _: self.reload_modules())
        event_bus.subscribe(KarcyticsEvent.PLUGIN_REMOVED, lambda _: self.reload_modules())

    def _discover_modules(self) -> None:
        """Discover available modules from the internal and user plugin directories."""
        discovered = PluginDiscoveryService.discover_modules(
            self.internal_plugins_dir, self.user_plugins_dir
        )
        self.modules.update(discovered)

    def get_available_modules(self) -> list[dict]:
        """Return the manifests for all discovered modules.

        Returns:
                list[dict]: The available module manifests.
        """
        return [m["manifest"] for m in self.modules.values()]

    def _validate_module(self, module_id: str) -> dict[str, Any]:
        """Validate module installation, trust level, and dependencies."""
        if module_id not in self.modules:
            raise ValueError(f"Module {module_id} is not installed.")

        mod_info = self.modules[module_id]

        # Hard check: Prevent execution of untrusted code
        if mod_info["trust_level"] == "untrusted":
            raise PermissionError(
                f"Security Block: Cannot load untrusted module '{module_id}'. Please verify and lock changes first."  # noqa: E501
            )

        if mod_info["trust_level"] == "outdated":
            raise RuntimeError(
                f"OutdatedModuleError: The module '{mod_info['manifest'].get('name', mod_info['package_name'])}' is outdated and must be updated to work with this version of Karcytics."  # noqa: E501
            )

        # Verify Environment Exists
        PluginLoaderFactory.verify_dependencies(Path(mod_info["path"]), mod_info["manifest"])
        return mod_info

    def _verify_and_report_isolation(
        self, module_id: str, purged: list[str], site_packages: Path
    ) -> None:
        """Confirm purged dependencies resolved cleanly and report isolation collisions."""
        still_shadowed = PluginEnvironmentInjector.verify_isolation(purged, site_packages)
        if not still_shadowed:
            return

        logger.error(
            "Plugin '%s' dependencies %s still resolve outside its own "
            "environment after isolation was enforced — likely bundled into the "
            "application itself. Affected features may misbehave.",
            module_id,
            still_shadowed,
        )
        try:
            from karcytics.core.diagnostics import diagnostics

            diagnostics.report_error(
                f"Plugin '{module_id}' could not fully isolate its dependencies "
                f"({', '.join(still_shadowed)}) from the application. Some features "
                f"in this plugin may not work correctly.",
                plugin_id=module_id,
                fatal=True,
            )
        except ImportError as e:
            logger.warning(
                "Failed to report isolation error for plugin '%s': %s",
                module_id,
                e,
            )

    def _load_inprocess_module_ui(
        self, module_id: str, mod_info: dict[str, Any]
    ) -> Callable[[], QWidget] | None:
        """Load UI for an in-process plugin with environment priority and isolation tracking."""
        # Inject path dynamically before loading
        site_packages = PluginEnvironmentInjector.inject_path(
            Path(mod_info["path"]), self.internal_plugins_dir
        )

        # Force any of this plugin's dependencies already shadowed by a stale
        # sys.modules entry (e.g. a partial copy claimed by the frozen core
        # bundle) to re-resolve from the plugin's own environment. This is a
        # fallback net — in the common case `unload_module()` already purged the
        # previous module's dependencies before this load started, so there's
        # nothing left to shadow.
        purged: list[str] = []
        if site_packages is not None:
            purged = PluginEnvironmentInjector.enforce_priority(
                Path(mod_info["path"]), site_packages
            )

        # Snapshot sys.modules so we know exactly what this load introduces —
        # this is what unload_module() will purge later, and (unlike
        # enforce_priority's site-packages heuristic) it also naturally covers the
        # plugin's own injected src/ package tree. Only recorded on a genuine fresh
        # load: PluginLoaderFactory.load_ui() short-circuits and returns the cached
        # panel class when the module is already loaded, so re-diffing here would
        # wipe out the real ownership set with an empty one.
        was_already_loaded = mod_info.get("loaded", False)
        pre_load_modules = set(sys.modules)

        # Load the UI safely
        result = PluginLoaderFactory.load_ui(module_id, mod_info)

        if not was_already_loaded:
            mod_info["_owned_modules"] = set(sys.modules) - pre_load_modules
            mod_info["_owned_paths"] = [p for p in (site_packages,) if p is not None]
            src_dir = Path(mod_info["path"]) / "src"
            if src_dir.exists():
                mod_info["_owned_paths"].append(src_dir)

        # If a collision was found and purged above, confirm the plugin's own import
        # actually landed correctly. If it's still shadowed, purging sys.modules alone
        # couldn't fix it (most likely a frozen sys.meta_path importer reclaiming the
        # name) — that's an environment problem the plugin cannot self-correct, so it
        # must be surfaced loudly rather than left to silently degrade.
        if purged and site_packages is not None:
            self._verify_and_report_isolation(module_id, purged, site_packages)

        return result

    def load_module_ui(self, module_id: str) -> Callable[[], QWidget] | None:
        """Load the user interface class for an installed and trusted module.

        Parameters:
            module_id (str): Identifier of the module to load.

        Returns:
            Callable[[], QWidget] | None: The module's UI class or factory function,
                or `None` when no UI class is available.

        Raises:
            ValueError: If the module is not installed.
            PermissionError: If the module is untrusted.
            RuntimeError: If the module is outdated.
        """
        mod_info = self._validate_module(module_id)

        # Isolated modules run in their own subprocess/interpreter and never
        # touch the Hub's sys.path or sys.modules — none of the path
        # injection, shadow-copy enforcement, or ownership snapshotting below
        # applies, because none of it happens for them.
        if mod_info["manifest"].get("process_model") == "isolated":
            result = PluginLoaderFactory.load_ui(module_id, mod_info)
            mod_info["loaded"] = True
            return result

        return self._load_inprocess_module_ui(module_id, mod_info)

    def unload_module(self, module_id: str) -> None:
        """Release a loaded module's plugin instance, owned modules, and injected paths.

        Must be called only after the module's UI widget has already been fully torn
        down (cleanup() called, C++ object confirmed destroyed) — this purges the
        `sys.modules`/`sys.path` state that widget's live objects may still reference,
        so purging first would risk exactly the shadow-copy/dangling-pointer collision
        this method exists to prevent.

        Parameters:
            module_id (str): Identifier of the module to unload.
        """
        if module_id not in self.modules:
            return

        mod_info = self.modules[module_id]
        if not mod_info.get("loaded"):
            return

        if mod_info["manifest"].get("process_model") == "isolated":
            from karcytics_sdk.plugin.daemon import PluginUIDaemon

            PluginUIDaemon.stop_instance(module_id)
            mod_info["loaded"] = False
            logger.info(f"Unloaded isolated module: {module_id}")
            return

        plugin_ref = mod_info.get("plugin_ref")
        if plugin_ref is not None:
            if hasattr(plugin_ref, "cleanup"):
                plugin_ref.cleanup()
            if hasattr(plugin_ref, "shutdown"):
                plugin_ref.shutdown()

        PluginEnvironmentInjector.purge_owned(mod_info.get("_owned_modules", set()))
        PluginEnvironmentInjector.remove_plugin_paths(mod_info.get("_owned_paths", []))

        mod_info["loaded"] = False
        mod_info["plugin_ref"] = None
        mod_info["_owned_modules"] = set()
        mod_info["_owned_paths"] = []

        logger.info(f"Unloaded module: {module_id}")

    def reload_modules(self) -> None:
        """Refreshes the plugin registry to reflect installed, removed, or updated plugins."""
        for module_id, mod_info in self.modules.items():
            if not mod_info["loaded"]:
                continue

            if mod_info["manifest"].get("process_model") == "isolated":
                # self.modules is discarded and rebuilt from scratch below,
                # but a running isolated plugin's daemon is tracked
                # separately (PluginUIDaemon._instances) — without this it
                # would keep running, orphaned, with no entry in the fresh
                # registry pointing back to it.
                from karcytics_sdk.plugin.daemon import PluginUIDaemon

                PluginUIDaemon.stop_instance(module_id)
                continue

            prefix = f"karcytics.plugins.{mod_info['package_name']}"
            keys_to_remove = [k for k in sys.modules if k == prefix or k.startswith(f"{prefix}.")]
            for k in keys_to_remove:
                del sys.modules[k]

        PluginEnvironmentInjector.cleanup_paths()
        self.modules.clear()
        self._discover_modules()
        logger.info(f"Hot-reloaded plugins. Currently loaded: {list(self.modules.keys())}")

    def trust_module(self, module_id: str) -> bool:
        """Manually trusts the module's current state.

        Parameters:
                module_id (str): Identifier of the module to trust.

        Returns:
                bool: `True` if the module is trusted, `False` if it is unavailable or its state
                cannot be verified.
        """
        if module_id not in self.modules:
            return False

        mod_info = self.modules[module_id]
        hashes = mod_info.get("calculated_hashes")

        if not hashes:
            res = self.trust_manager.verify_plugin(mod_info["path"])
            hashes = res.calculated_hashes

        if hashes:
            self.trust_manager.overrides.trust_current_state(module_id, hashes)
            cache = self.trust_manager._get_cache()
            if cache and module_id in cache.data:
                del cache.data[module_id]
                cache._save()

            logger.info(f"User manually trusted module: {module_id}")
            self.reload_modules()
            return True
        return False
