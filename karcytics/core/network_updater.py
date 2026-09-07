"""Background network fetcher and plugin installer for Karcytics (Facade)."""

import logging
import os
import tempfile
import webbrowser
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from karcytics.core.config import AppConfig
from karcytics.core.event_bus import KarcyticsEvent, event_bus
from karcytics.core.network.client import NetworkClient
from karcytics.core.network.installer import safe_extract, safe_remove
from karcytics.core.network.registry_sync import RegistrySync
from karcytics.core.network.system_assets import SystemAssetSync
from karcytics.core.network.trust_sync import TrustSync
from karcytics.core.utils import AtomicJsonFile, parse_version

logger = logging.getLogger(__name__)


class NetworkUpdater:
    """Facade for network operations, delegating to specialized network packages."""

    def __init__(self) -> None:
        """Initialize network updater configuration and local plugin storage.

        Creates the plugin directory and initializes the local installed-plugin registry when
        needed.
        """
        self.core_version = AppConfig.CORE_VERSION
        self.registry_url = AppConfig.REGISTRY_URL
        self.core_registry_url = AppConfig.CORE_REGISTRY_URL
        self.authority_url = AppConfig.AUTHORITY_REGISTRY_URL

        self.plugin_dir = Path.home() / ".karcytics" / "plugins"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

        self.local_registry_path = self.plugin_dir / "installed.json"

        if not self.local_registry_path.exists():
            AtomicJsonFile.save(self.local_registry_path, {})

        self.setup_developer_tools()

    def setup_developer_tools(self) -> None:
        """Ensures a copy of the signing utility is available in the plugins folder for developers."""  # noqa: E501
        try:
            signer_source = Path(__file__).parent / "sign_plugin.py"
            signer_dest = self.plugin_dir / "karcytics-sign.py"

            if signer_source.exists() and (
                not signer_dest.exists()
                or os.path.getmtime(signer_source) > os.path.getmtime(signer_dest)
            ):
                import shutil

                shutil.copy(signer_source, signer_dest)
                logger.info(f"Deployed karcytics-sign tool to {signer_dest}")
        except Exception as e:
            logger.warning(f"Could not deploy signing tool: {e}")

    def get_local_state(self) -> dict[str, Any]:
        """Retrieve the locally installed plugin registry state.

        Returns:
            dict: The current local registry data.
        """
        return RegistrySync.get_local_state(self.plugin_dir, self.local_registry_path)

    def fetch_remote_registry(self, registry_url: str) -> dict[str, Any]:
        """Fetches registry data from the specified remote URL.

        Parameters:
            registry_url (str): URL of the remote registry.

        Returns:
            dict: Registry data retrieved from the remote URL.
        """
        return RegistrySync.fetch_remote_registry(registry_url)

    def evaluate_store_state(self, cancel_check: Callable[[], bool] | None = None) -> dict:
        """Evaluate store state and synchronize related trust and system asset data.

        Returns:
                dict: The evaluated store inventory (enriched with per-plugin metadata).
        """
        store_inventory, author_list, remote_data = RegistrySync.evaluate_store_state(
            self.core_version,
            self.registry_url,
            self.plugin_dir,
            self.local_registry_path,
            cancel_check,
        )
        self.sync_trusted_developers(author_list)
        self.fetch_and_sync_authorities()
        SystemAssetSync.sync_assets(remote_data, self.plugin_dir)
        return store_inventory

    def fetch_and_sync_authorities(self) -> None:
        """Fetch and synchronize authority data from the configured authority service."""
        TrustSync.fetch_and_sync_authorities(self.authority_url)

    def sync_trusted_developers(self, trusted_list: list[dict[Any, Any]]) -> None:
        """Synchronize the configured trusted developer records.

        Parameters:
            trusted_list (list): Trusted developer records to synchronize.
        """
        TrustSync.sync_trusted_developers(trusted_list)

    def sync_system_assets(self) -> None:
        """Synchronize system assets using the remote registry data."""
        remote_data = self.fetch_remote_registry(self.registry_url)
        SystemAssetSync.sync_assets(remote_data, self.plugin_dir)

    def invalidate_plugin_registry_cache(self) -> None:
        """Clear the per-plugin pyproject.toml cache so the next store load fetches fresh data.

        Called by the Refresh button in the Marketplace dialog.
        """
        from karcytics.core.network.plugin_registry_fetcher import PluginRegistryFetcher

        PluginRegistryFetcher.invalidate_cache()
        logger.info("Plugin registry cache invalidated — next store open will fetch fresh data.")

    def check_for_core_updates(self) -> tuple[bool, dict[str, Any] | None]:
        """Determine whether a newer core application version is available.

        Fetches Karcytics's own self-published registry.json (a GitHub Release asset on
        the Karcytics repo itself) rather than going through Karcytics-Distribution, since
        the core app always knows exactly where its own releases live.

        Returns:
            tuple: A boolean and core application details when an update is available;
                otherwise, `False` and `None`.
        """
        core_info = self.fetch_remote_registry(self.core_registry_url)
        remote_version = core_info.get("version", "0.0.0")

        if parse_version(self.core_version) < parse_version(remote_version):  # noqa: E501
            return True, core_info
        return False, None

    def launch_core_update_page(self) -> bool:
        """Open the core application's download page when a URL is available.

        Returns:
            bool: `True` if the download page was opened, `False` if no URL is configured.
        """
        core_info = self.fetch_remote_registry(self.core_registry_url)
        download_url = core_info.get("download_url")

        if download_url:
            webbrowser.open_new_tab(download_url)
            return True
        return False

    def install_plugin(self, plugin_id: str, remote_info: dict[str, Any]) -> tuple[bool, str]:
        """Download and install a plugin package, then update the local installation registry.

        Parameters:
            plugin_id: Identifier of the plugin to install.
            remote_info: Plugin metadata containing the download URL, version, and name.

        Returns:
            A tuple containing a success flag and a status message.
        """
        try:
            response = NetworkClient.get(
                remote_info["download_url"],
                timeout=NetworkClient.DEFAULT_TIMEOUT,
                stream=True,
            )
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                max_download_size = 500 * 1024 * 1024  # 500 MB limit
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > max_download_size:
                        raise RuntimeError("Download exceeded maximum size limit.")
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                plugin_folder = self.plugin_dir / plugin_id
                safe_remove(self.plugin_dir, plugin_folder)

                with zipfile.ZipFile(tmp_path) as z:
                    plugin_folder.mkdir(parents=True, exist_ok=True)
                    safe_extract(z, plugin_folder)

                # Flatten single root directory (e.g., GitHub release artifacts)
                items = [item for item in plugin_folder.iterdir() if item.name != "__MACOSX"]
                if len(items) == 1 and items[0].is_dir():
                    nested_dir = items[0]
                    for item in nested_dir.iterdir():
                        import shutil

                        shutil.move(str(item), str(plugin_folder / item.name))
                    nested_dir.rmdir()
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            local_data = self.get_local_state()
            local_data[plugin_id] = {"version": remote_info["version"], "name": remote_info["name"]}

            AtomicJsonFile.save(self.local_registry_path, local_data)

            # Broadcast the installation success
            event_bus.emit(KarcyticsEvent.PLUGIN_INSTALLED, plugin_id)

            return True, "Installation successful."
        except Exception as e:
            logger.error(f"Failed to install {plugin_id}: {e}")
            return False, f"Failed to install: {e}"

    def remove_plugin(self, plugin_id: str) -> tuple[bool, str]:
        """Remove an installed plugin and update the local registry.

        Parameters:
            plugin_id: Identifier of the plugin to remove.

        Returns:
            A tuple containing a success flag and a status message.
        """
        try:
            plugin_folder = self.plugin_dir / plugin_id
            safe_remove(self.plugin_dir, plugin_folder)

            local_data = self.get_local_state()
            if plugin_id in local_data:
                del local_data[plugin_id]

            AtomicJsonFile.save(self.local_registry_path, local_data)

            # Broadcast the removal
            event_bus.emit(KarcyticsEvent.PLUGIN_REMOVED, plugin_id)

            return True, "Plugin removed successfully."
        except Exception as e:
            return False, f"Failed to remove: {e}"
