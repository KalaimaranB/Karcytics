import logging
from pathlib import Path

from karcytics_sdk.plugin.manifest_parser import ManifestParser
from PyQt6.QtCore import QThread, pyqtSignal

from karcytics.core.package_manager import PackageManager

logger = logging.getLogger(__name__)


class PluginDependencyInstallerWorker(QThread):
    """Background thread to download, cache, and link dependencies for a plugin."""

    progress = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, plugin_dir: Path | str, cache_dir: Path | None = None):
        """Initialize the worker for installing dependencies in a plugin directory.

        Parameters:
            plugin_dir (Path | str): Directory containing the plugin.
            cache_dir (Path | None): Optional directory for the package cache.
        """
        super().__init__()
        self.plugin_dir = Path(plugin_dir)
        self.pm = PackageManager(cache_dir=cache_dir)

        logger.info("PluginDependencyInstallerWorker initialized for %s", self.plugin_dir)

    def run(self) -> None:
        """Parse the plugin manifest and install its declared Python dependencies.

        Emits progress updates during installation and signals completion with success
        or failure status. Missing or invalid manifests and installation errors are
        reported through the completion signal.
        """
        try:
            logger.info("PluginDependencyInstallerWorker.run() started for %s", self.plugin_dir)
            manifest_path = self.plugin_dir / "pyproject.toml"
            if not manifest_path.exists():
                self.finished.emit(False, "pyproject.toml missing from plugin directory.")
                return

            try:
                parser = ManifestParser()
                manifest = parser.parse_file(str(manifest_path))
            except Exception as e:
                self.finished.emit(False, f"Failed to parse pyproject.toml: {e}")
                return

            # Use python_dependencies, fallback to core_dependencies for legacy
            dependencies = manifest.get("python_dependencies")
            if dependencies is None:
                deps_list = manifest.get("core_dependencies", [])
                dependencies = dict.fromkeys(deps_list, "")

            if not dependencies:
                self.progress.emit(100)
                self.finished.emit(True, "")
                return

            self.pm.resolve_and_install_all(
                dependencies,
                self.plugin_dir,
                progress_callback=lambda p: self.progress.emit(p),
                log_callback=lambda m: self.log_message.emit(m),
            )
            self.finished.emit(True, "")

        except Exception as e:
            logger.error(f"Plugin dependency installation failed: {e}", exc_info=True)
            self.finished.emit(False, str(e))
