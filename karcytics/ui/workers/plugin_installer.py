"""Worker thread for downloading and installing plugins in the UI."""

import logging
import zipfile
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from karcytics.core.network.client import NetworkClient
from karcytics.core.network.installer import safe_extract

logger = logging.getLogger(__name__)


class PluginInstallerWorker(QThread):
    """Downloads, extracts, and installs a plugin into the user directory."""

    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, plugin_id: str, download_url: str, plugins_dir: Path) -> None:
        """Initialize a plugin installation worker using the per-user plugin directory.

        Parameters:
            plugin_id (str): Identifier of the plugin to install.
            download_url (str): URL of the plugin archive.
            plugins_dir (Path): The directory to install plugins to.
        """
        super().__init__()
        self.plugin_id = plugin_id
        self.download_url = download_url
        self.plugins_dir = plugins_dir

    def run(self) -> None:
        """Install the plugin and report progress and completion status.

        Download failures, invalid archives, and unexpected errors are reported through
        the completion signal with an appropriate failure message.
        """
        try:
            # 1. Ensure the user plugin directory exists
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

            # 2. Download the Zip File
            self.progress.emit(10, f"Downloading {self.plugin_id}...")
            response = NetworkClient.get(self.download_url, stream=True)
            response.raise_for_status()

            # 3. Stream the file to disk to bound memory usage
            # Fixes CodeRabbit comment about response.content loading entire file into memory
            zip_path = self.plugins_dir / f"{self.plugin_id}.zip"
            max_download_size = 500 * 1024 * 1024  # 500 MB limit
            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > max_download_size:
                        raise RuntimeError("Download exceeded maximum size limit.")
                    f.write(chunk)

            # 4. Extract the Zip (Safely!)
            self.progress.emit(60, "Extracting plugin files...")
            with zipfile.ZipFile(zip_path) as z:
                safe_extract(z, self.plugins_dir)

            # Cleanup the temporary zip
            zip_path.unlink()

            self.progress.emit(100, "Installation complete!")
            self.finished.emit(True, f"Successfully installed {self.plugin_id}")

        except requests.RequestException as e:
            msg = f"Network error downloading plugin: {e}"
            logger.error(msg, exc_info=True)
            self.finished.emit(False, "Download failed: Check your internet connection.")
        except zipfile.BadZipFile:
            msg = "Downloaded file is not a valid zip archive."
            logger.error(msg, exc_info=True)
            self.finished.emit(False, "Installation failed: Corrupted zip file.")
        except Exception as e:
            msg = f"Unexpected error installing plugin {self.plugin_id}"
            logger.exception(msg)
            self.finished.emit(False, f"Installation error: {str(e)}")
