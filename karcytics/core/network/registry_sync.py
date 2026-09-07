"""Local and remote registry state management."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from karcytics.core.network.client import NetworkClient
from karcytics.core.network.plugin_registry_fetcher import PluginRegistryFetcher
from karcytics.core.utils import AtomicJsonFile, parse_version, sanitize_identifier

logger = logging.getLogger(__name__)


class RegistrySync:
    """Handles fetching remote registries and managing the local installed.json state."""

    @staticmethod
    def get_local_state(plugin_dir: Path, local_registry_path: Path) -> Any:
        """Build the installed plugin state from manifests in a plugin directory.

        Parameters:
            plugin_dir (Path): Directory containing installed plugin directories.
            local_registry_path (Path): Path where the generated local registry state is saved.

        Returns:
            dict: Mapping of plugin identifiers to their names and versions.
        """
        local_state: dict = {}

        if not plugin_dir.exists():
            return local_state

        try:
            from karcytics_sdk.plugin.manifest_parser import ManifestParser

            parser = ManifestParser()
        except ImportError:
            parser = None
            # When parser is unavailable, return existing local registry state
            return AtomicJsonFile.load(local_registry_path, default={})

        for item in plugin_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "pyproject.toml"
                if manifest_path.exists() and parser:
                    try:
                        manifest = parser.parse_file(str(manifest_path))
                        plugin_id = manifest.get("id") or item.name
                        local_state[plugin_id] = {
                            "version": manifest.get("version", "0.0.0"),
                            "name": manifest.get("name", item.name),
                        }
                    except Exception as e:
                        logger.warning(f"Could not read pyproject.toml for {item.name}: {e}")

        if not AtomicJsonFile.save(local_registry_path, local_state):
            logger.error("Failed to sync local registry")

        return local_state

    @staticmethod
    def fetch_remote_registry(registry_url: str) -> dict:
        """Fetch the remote plugin registry data.

        Parameters:
            registry_url (str): URL of the remote registry.

        Returns:
            dict: Parsed registry data, or an empty dictionary if fetching fails.
        """
        try:
            response = NetworkClient.get(registry_url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            msg = f"Network error fetching registry: {e}"
            logger.error(msg, exc_info=True)
            return {}

    @staticmethod
    def evaluate_store_state(
        core_version: str,
        registry_url: str,
        plugin_dir: Path,
        local_registry_path: Path,
        cancel_check: Callable[[], bool] | None = None,
    ):  # noqa: E501
        """Compare installed plugins with the remote registry and classify their availability.

        Eagerly enriches each entry from the plugin's own ``pyproject.toml``
        (fetched via ``PluginRegistryFetcher``).

        Parameters:
            core_version (str): Current application core version.
            registry_url (str): URL of the remote plugin registry.
            plugin_dir (Path): Directory containing installed plugins.
            local_registry_path (Path): Path used to store the local registry state.

        Returns:
            tuple: Store inventory, trusted developer information, and the remote registry data.
        """
        remote_data = RegistrySync.fetch_remote_registry(registry_url)
        local_data = RegistrySync.get_local_state(plugin_dir, local_registry_path)
        store_inventory = {}
        plugins_data = remote_data.get("plugins", {})

        app_v = parse_version(core_version)

        logger.info(f"Checking Store State. App Version: {core_version} (Parsed: {app_v})")

        for plugin_id, remote_info in plugins_data.items():
            state = "INSTALL"
            min_core_str = remote_info.get("min_core_version", "0.0.0")
            min_core_v = parse_version(min_core_str)

            logger.info(
                f"Plugin {plugin_id}: MinCoreReq={min_core_str} ({min_core_v}), AppVersion={core_version} ({app_v})"  # noqa: E501
            )

            if app_v < min_core_v:
                state = "INCOMPATIBLE"
                logger.warning(f"MARKING {plugin_id} AS INCOMPATIBLE: {app_v} < {min_core_v}")
            elif plugin_id in local_data:
                local_v = parse_version(local_data[plugin_id].get("version", "0.0.0"))
                remote_v = parse_version(remote_info.get("version", "0.0.0"))
                state = "UPDATE" if local_v < remote_v else "UP_TO_DATE"

            store_inventory[plugin_id] = {
                "info": remote_info,
                "state": state,
                "local_version": local_data.get(plugin_id, {}).get("version", None),
                "is_verified": False,  # Resolved after enrichment below
            }

        # Eagerly enrich every entry from each plugin's own pyproject.toml
        store_inventory = PluginRegistryFetcher.fetch_all(store_inventory, cancel_check)

        # Resolve verified status now that author keys are populated from pyproject.toml
        roots_dir = Path.home() / ".karcytics" / "trusted_roots"
        for entry in store_inventory.values():
            authors = entry["info"].get("authors", [])
            is_verified = False
            for author in authors if isinstance(authors, list) else []:
                author_id = author.get("github") or author.get("name", "")
                sanitized = sanitize_identifier(author_id)
                if sanitized and (roots_dir / f"network_{sanitized}.pub").exists():
                    is_verified = True
                    break
            entry["is_verified"] = is_verified

        # Collect all authors across enriched entries as the trusted developer list
        trusted_devs = RegistrySync._extract_authors_from_inventory(store_inventory)

        return store_inventory, trusted_devs, remote_data

    @staticmethod
    def _extract_authors_from_inventory(store_inventory: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect the union of ``authors`` lists from all enriched store entries.

        Parameters:
            store_inventory (dict): Enriched store inventory.

        Returns:
            list: Deduplicated author records for ``TrustSync.sync_trusted_developers``.
        """
        seen: set[str] = set()
        authors: list[dict[str, Any]] = []
        for entry in store_inventory.values():
            for author in entry.get("info", {}).get("authors", []):
                key = author.get("github") or author.get("name", "")
                if key and key not in seen:
                    seen.add(key)
                    normalized = dict(author)
                    normalized.setdefault("developer_id", key)
                    authors.append(normalized)
        return authors
