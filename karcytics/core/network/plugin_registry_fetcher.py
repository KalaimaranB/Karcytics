"""Decentralized plugin registry fetcher.

Fetches each plugin's own ``pyproject.toml`` from its GitHub repository,
reads the ``[tool.karcytics.plugin]`` section for store-display metadata
(icon, tags, homepage, rich author info), caches the result locally, and
enriches the store inventory built from the slim Distribution index.

The Distribution index only carries a ``repo_url`` per plugin — it has no
install artifact of its own — so this module also resolves the actual
downloadable zip via each plugin's own GitHub Releases (published by the
plugin's own ``release.yml``, one asset per release).
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from karcytics.core.config import AppConfig
from karcytics.core.network.client import NetworkClient

logger = logging.getLogger(__name__)

# Raw-content URL template: github.com → raw.githubusercontent.com/<branch>/pyproject.toml
_RAW_TEMPLATE = "https://raw.githubusercontent.com/{owner}/{repo}/main/pyproject.toml"

# GitHub REST API template for a repo's newest published release.
_RELEASES_LATEST_TEMPLATE = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


class PluginRegistryFetcher:
    """Fetches, caches, and enriches plugin metadata from each plugin's own pyproject.toml."""

    # ── URL derivation ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_owner_repo(repo_url: str) -> tuple[str, str] | None:
        """Split a GitHub repository URL into ``(owner, repo)``, or ``None`` if unparseable."""
        try:
            parsed = urlparse(repo_url.rstrip("/"))
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 2:
                return None
            return parts[0], parts[1]
        except Exception:
            return None

    @staticmethod
    def derive_manifest_url(repo_url: str) -> str | None:
        """Derive the raw ``pyproject.toml`` URL from a GitHub repository URL.

        Parameters:
            repo_url (str): GitHub repository URL, e.g.
                ``https://github.com/KalaimaranB/Karcytics-flow-cytometry``.

        Returns:
            str | None: The raw-content URL, or ``None`` if the URL cannot be parsed.
        """
        owner_repo = PluginRegistryFetcher._parse_owner_repo(repo_url)
        if not owner_repo:
            logger.warning("Cannot derive manifest URL — repo_url has no owner/repo: %s", repo_url)
            return None
        owner, repo = owner_repo
        return _RAW_TEMPLATE.format(owner=owner, repo=repo)

    # ── Cache helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _cache_path(plugin_id: str, ext: str = "toml") -> Path:
        return AppConfig.PLUGIN_REGISTRY_CACHE_DIR / f"{plugin_id}.{ext}"

    @staticmethod
    def _timestamp_path(plugin_id: str, ext: str = "toml") -> Path:
        return AppConfig.PLUGIN_REGISTRY_CACHE_DIR / f"{plugin_id}.{ext}.timestamp"

    @classmethod
    def is_cache_valid(cls, plugin_id: str, ext: str = "toml") -> bool:
        """Return ``True`` when a fresh cache entry exists for *plugin_id* under *ext*."""
        ts_file = cls._timestamp_path(plugin_id, ext)
        if not ts_file.exists():
            return False
        try:
            ts = float(ts_file.read_text().strip())
            return (time.time() - ts) < AppConfig.PLUGIN_REGISTRY_CACHE_TTL_SECONDS
        except Exception:
            return False

    @classmethod
    def _write_cache(cls, plugin_id: str, raw_toml: str) -> None:
        AppConfig.PLUGIN_REGISTRY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls._cache_path(plugin_id).write_text(raw_toml, encoding="utf-8")
        cls._timestamp_path(plugin_id).write_text(str(time.time()), encoding="utf-8")

    @classmethod
    def _read_cache(cls, plugin_id: str) -> dict[str, Any] | None:
        try:
            import tomllib

            raw = cls._cache_path(plugin_id).read_bytes()
            return tomllib.loads(raw.decode("utf-8"))
        except Exception:
            return None

    @classmethod
    def _write_download_url_cache(cls, plugin_id: str, download_url: str) -> None:
        AppConfig.PLUGIN_REGISTRY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls._cache_path(plugin_id, "download_url").write_text(download_url, encoding="utf-8")
        cls._timestamp_path(plugin_id, "download_url").write_text(
            str(time.time()), encoding="utf-8"
        )

    @classmethod
    def _read_download_url_cache(cls, plugin_id: str) -> str | None:
        try:
            return cls._cache_path(plugin_id, "download_url").read_text(encoding="utf-8").strip()
        except Exception:
            return None

    @classmethod
    def invalidate_cache(cls) -> None:
        """Delete all cached plugin manifests and download URLs (manual Refresh button)."""
        cache_dir = AppConfig.PLUGIN_REGISTRY_CACHE_DIR
        if not cache_dir.exists():
            return
        for f in cache_dir.iterdir():
            if f.suffix in {".toml", ".timestamp"} or f.name.endswith(
                (".download_url", ".download_url.timestamp")
            ):
                with contextlib.suppress(Exception):
                    f.unlink()
        logger.info("Plugin registry cache cleared.")

    # ── Fetch ───────────────────────────────────────────────────────────────

    @classmethod
    def fetch(cls, plugin_id: str, repo_url: str) -> dict[str, Any] | None:
        """Fetch the full ``pyproject.toml`` manifest from a plugin's repository.

        Uses the local disk cache when it is still within the TTL, otherwise
        performs a live HTTP GET and refreshes the cache.

        Parameters:
            plugin_id (str): Plugin identifier used as the cache key.
            repo_url (str): GitHub repository URL to derive the manifest URL from.

        Returns:
            dict | None: The parsed TOML dict, or ``None`` on failure.
        """
        if cls.is_cache_valid(plugin_id):
            cached = cls._read_cache(plugin_id)
            if cached is not None:
                logger.debug("Plugin registry cache hit for '%s'.", plugin_id)
                return cached

        manifest_url = cls.derive_manifest_url(repo_url)
        if not manifest_url:
            return None

        try:
            response = NetworkClient.get(manifest_url, timeout=10)
            if response.status_code == 404:
                logger.debug(
                    "No pyproject.toml found at %s (404) — skipping enrichment.",
                    manifest_url,
                )
                return None
            response.raise_for_status()

            raw_toml = response.text
            cls._write_cache(plugin_id, raw_toml)

            import tomllib

            return tomllib.loads(raw_toml)
        except Exception:
            logger.warning(
                "Failed to fetch plugin manifest for '%s' from %s "
                "— using cached data if available.",
                plugin_id,
                manifest_url,
                exc_info=True,
            )
            # Attempt stale cache as graceful fallback
            return cls._read_cache(plugin_id)

    @classmethod
    def resolve_download_url(cls, plugin_id: str, repo_url: str) -> str | None:
        """Resolve the installable zip URL for a plugin's newest published GitHub Release.

        Each plugin repository publishes its own release (see its ``release.yml``)
        with exactly one zip asset per tag. The Distribution index only carries
        ``repo_url``, so this is the piece that turns that into something
        ``NetworkUpdater.install_plugin`` can actually download.

        Parameters:
            plugin_id (str): Plugin identifier used as the cache key.
            repo_url (str): GitHub repository URL to resolve the latest release from.

        Returns:
            str | None: The release asset's direct download URL, or ``None`` on failure.
        """
        if cls.is_cache_valid(plugin_id, "download_url"):
            cached = cls._read_download_url_cache(plugin_id)
            if cached:
                logger.debug("Download URL cache hit for '%s'.", plugin_id)
                return cached

        owner_repo = cls._parse_owner_repo(repo_url)
        if not owner_repo:
            logger.warning("Cannot resolve download URL — repo_url has no owner/repo: %s", repo_url)
            return None
        owner, repo = owner_repo
        releases_url = _RELEASES_LATEST_TEMPLATE.format(owner=owner, repo=repo)

        try:
            response = NetworkClient.get(releases_url, timeout=10)
            response.raise_for_status()
            release = response.json()

            assets = release.get("assets", [])
            if not assets:
                logger.warning(
                    "Latest release of '%s' (%s) has no assets to install.",
                    plugin_id,
                    releases_url,
                )
                return None

            download_url = assets[0].get("browser_download_url")
            if not download_url:
                return None

            cls._write_download_url_cache(plugin_id, download_url)
            return download_url
        except Exception:
            logger.warning(
                "Failed to resolve download URL for '%s' from %s — using cached data if available.",
                plugin_id,
                releases_url,
                exc_info=True,
            )
            # Attempt stale cache as graceful fallback
            return cls._read_download_url_cache(plugin_id)

    # ── Enrichment ──────────────────────────────────────────────────────────

    @staticmethod
    def enrich_entry(  # noqa: E501
        store_entry: dict[str, Any], plugin_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge ``[tool.karcytics.plugin]`` fields into a store inventory entry.

        Parameters:
            store_entry (dict): An entry from the store inventory (the ``info`` sub-dict).
            plugin_manifest (dict): The full parsed ``pyproject.toml`` table.

        Returns:
            dict: The enriched ``store_entry["info"]`` dict (mutated in place and returned).
        """
        info = store_entry.get("info", store_entry)

        plugin_table = plugin_manifest.get("tool", {}).get("karcytics", {}).get("plugin", {})
        project_table = plugin_manifest.get("project", {})

        # 1. Use display_name for the name in store
        display_name = plugin_table.get("display_name")
        if display_name:
            info["name"] = display_name
        elif "name" in project_table:
            info["name"] = project_table["name"]

        # 4. Parse version and min_core_version parameters correctly
        if "version" in project_table:
            info["version"] = project_table["version"]

        if "min_core_version" in plugin_table:
            info["min_core_version"] = plugin_table["min_core_version"]

        # Standard metadata mapping
        for field in ("description", "icon", "tags", "homepage", "is_beta", "beta"):
            value = plugin_table.get(field)
            if value is not None:
                info[field] = value

        # Map authors and contributors
        authors = plugin_table.get("authors")
        if authors and isinstance(authors, list):
            info["authors"] = authors

        # 5. Extract contributors as well
        contributors = plugin_table.get("contributors")
        if contributors and isinstance(contributors, list):
            info["contributors"] = contributors

        return info

    # ── Batch fetch ─────────────────────────────────────────────────────────

    @classmethod
    def _apply_fetch_result(
        cls,
        store_inventory: dict[str, Any],
        result: tuple[str, dict[str, Any] | None, str | None],
    ) -> bool:
        """Merge one plugin's fetched manifest/download URL into its store entry.

        Returns:
            bool: ``True`` if the entry now has both a manifest and a download URL
                (i.e. is actually installable), ``False`` otherwise.
        """
        plugin_id, manifest, download_url = result
        if not manifest:
            return False
        if not download_url:
            logger.warning(
                "Skipping '%s' — manifest fetched but no install release found.", plugin_id
            )
            return False

        info = cls.enrich_entry(store_inventory[plugin_id], manifest)
        info["download_url"] = download_url
        logger.debug("Enriched store entry for '%s' from plugin manifest.", plugin_id)
        return True

    @classmethod
    def fetch_all(  # noqa: C901
        cls, store_inventory: dict[str, Any], cancel_check: Callable[[], bool] | None = None
    ) -> dict[str, Any]:  # noqa: C901
        """Eagerly fetch, enrich, and resolve an install URL for all plugins in parallel.

        For each entry that contains a ``repo_url``, derives the ``pyproject.toml``
        URL, fetches it (with cache), and merges the metadata into the entry — and
        separately resolves ``download_url`` from that same repo's newest GitHub
        Release. Plugins without a ``repo_url``, that fail manifest parsing, or that
        have no resolvable release asset are removed from the store inventory, since
        none of those cases can actually be installed.

        Parameters:
            store_inventory (dict): Mapping of plugin_id → store entry dict.

        Returns:
            dict: The same *store_inventory* dict, enriched in place (invalid plugins removed).
        """
        to_fetch: list[tuple[str, str]] = []
        for plugin_id, entry in store_inventory.items():
            repo_url = entry.get("info", {}).get("repo_url")
            if repo_url:
                to_fetch.append((plugin_id, repo_url))

        if not to_fetch:
            return store_inventory

        successful_plugins = set()

        def _fetch_one(args: tuple[str, str]) -> tuple[str, dict[str, Any] | None, str | None]:
            pid, url = args
            return pid, cls.fetch(pid, url), cls.resolve_download_url(pid, url)

        with ThreadPoolExecutor(max_workers=min(8, len(to_fetch))) as executor:
            futures = {executor.submit(_fetch_one, args): args[0] for args in to_fetch}
            for future in as_completed(futures):
                if cancel_check and cancel_check():
                    for f in futures:
                        f.cancel()
                    return {}
                plugin_id = futures[future]
                try:
                    if cls._apply_fetch_result(store_inventory, future.result()):
                        successful_plugins.add(plugin_id)
                except Exception:
                    logger.warning(
                        "Failed to enrich store entry for '%s'.",
                        plugin_id,
                        exc_info=True,
                    )

        # 3. If a module's toml or install release can not be resolved, it should not be rendered.
        fetch_pids = [p[0] for p in to_fetch]
        for pid in list(store_inventory.keys()):
            if pid in fetch_pids and pid not in successful_plugins:
                del store_inventory[pid]

        return store_inventory
