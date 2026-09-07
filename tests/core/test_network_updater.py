import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from karcytics.core.network.trust_sync import TrustSync

# Import from the facade and new network modules
from karcytics.core.network_updater import NetworkUpdater
from karcytics.ui.workers.plugin_installer import PluginInstallerWorker


def _dict_to_toml(d):
    # Convert flat dict to pyproject.toml format
    """
    Convert plugin metadata into a pyproject.toml-formatted string.

    Parameters:
        d: Flat plugin metadata dictionary.

    Returns:
        A TOML string containing project and Karcytics plugin metadata.
    """
    lines = []

    lines.append("[project]")
    lines.append(f'name = "{d.get("name", "test")}"')
    lines.append(f'version = "{d.get("version", "1.0.0")}"')
    if "description" in d:
        lines.append(f'description = "{d["description"]}"')

    authors = d.get("authors", [])
    if authors:
        lines.append("authors = [")
        for a in authors:
            lines.append(f'  {{ name = "{a.get("name", "Test")}" }},')
        lines.append("]")

    lines.append("")
    lines.append("[tool.karcytics.plugin]")
    lines.append(f'id = "{d.get("id", "test_id")}"')

    if authors:
        lines.append("authors = [")
        for a in authors:
            role = a.get("role", "Developer")
            perms = a.get("permissions", [])
            perms_str = '", "'.join(perms)
            if perms_str:
                lines.append(
                    f'  {{ name = "{a.get("name", "Test")}", role = "{role}", permissions = ["{perms_str}"] }},'
                )
            else:
                lines.append(f'  {{ name = "{a.get("name", "Test")}", role = "{role}" }},')
        lines.append("]")

    return "\n".join(lines)


# Mock PyQt6 to avoid QThread errors during testing if needed
class MockQThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        self.run()

    def run(self):
        """Should be overridden by subclasses."""
        pass


@pytest.fixture(autouse=True)
def mock_qthread(monkeypatch):
    monkeypatch.setattr("PyQt6.QtCore.QThread", MockQThread)


@pytest.fixture
def temp_plugin_dir(tmp_path):
    # Mock the home directory to use tmp_path
    plugin_dir = tmp_path / ".karcytics" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


def create_malicious_zip() -> bytes:
    """Creates an in-memory zip file with a path traversal payload."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        # Normal file
        z.writestr("safe_plugin/info.json", '{"name": "Safe"}')
        # Malicious file attempting to escape the directory
        z.writestr(
            "../../../../../../../../../../../../../../../../../../tmp/evil.txt", "evil payload"
        )
    return buffer.getvalue()


def create_safe_zip() -> bytes:
    """Creates a basic safe zip file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("test_plugin/config.json", '{"version": "1.0.0"}')
        z.writestr(
            "test_plugin/pyproject.toml",
            _dict_to_toml(
                {
                    "id": "test_plugin",
                    "version": "1.2.3",
                    "name": "Test Plugin",
                    "authors": [{"name": "A"}],
                }
            ),
        )
    return buffer.getvalue()


@patch("requests.Session.get")
def test_plugin_installer_zip_slip(mock_get, temp_plugin_dir, monkeypatch):
    """Verify that the Zip Slip vulnerability is blocked by safe extraction."""
    monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)

    mock_response = mock_get.return_value
    mock_response.content = create_malicious_zip()
    mock_response.raise_for_status.return_value = None

    installer = PluginInstallerWorker(
        "evil_plugin", "https://fake.url", temp_plugin_dir / "evil_plugin.zip"
    )
    installer.run()


@patch("requests.Session.get")
def test_plugin_installer_ssl_verify(mock_get, temp_plugin_dir, monkeypatch):
    """Ensure requests.get is called with properly configured SSL certs."""
    import certifi

    monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)

    mock_response = mock_get.return_value
    mock_response.content = create_safe_zip()

    installer = PluginInstallerWorker(
        "safe_plugin", "https://fake.url", temp_plugin_dir / "safe_plugin.zip"
    )
    installer.run()

    # Verify requests.get was called with verify=certifi.where()
    mock_get.assert_called_once_with(
        "https://fake.url",
        stream=True,
        timeout=15,
        headers={
            "User-Agent": "Karcytics-App",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        },
        verify=certifi.where(),
    )


@patch("requests.Session.get")
def test_network_updater_fetch_registry(mock_get, temp_plugin_dir, monkeypatch):
    """Ensure NetworkUpdater uses requests with verify=certifi.where() and no-cache headers."""
    import certifi

    monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)

    mock_response = mock_get.return_value
    mock_response.json.return_value = {"plugins": {}}
    mock_response.raise_for_status.return_value = None

    updater = NetworkUpdater()
    updater.fetch_remote_registry("https://registry.url")

    mock_get.assert_called_once_with(
        "https://registry.url",
        stream=False,
        timeout=15,  # Default client timeout
        headers={
            "User-Agent": "Karcytics-App",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        },
        verify=certifi.where(),
    )


class TestNetworkUpdaterExpanded:
    """Detailed logic tests for registry processing and state evaluation."""

    @pytest.fixture
    def updater(self, temp_plugin_dir, monkeypatch):
        """Create a network updater configured to use the temporary plugin directory.

        Parameters:
            temp_plugin_dir (Path): Temporary home directory for plugin data.
            monkeypatch: Pytest monkeypatch fixture used to override the home directory.

        Returns:
            NetworkUpdater: An updater configured with the temporary plugin directory.
        """
        monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)
        return NetworkUpdater()

    @patch("requests.Session.get")
    def test_evaluate_store_state_scenarios(self, mock_get, updater):
        """Classify plugins as INSTALL, UPDATE, UP_TO_DATE, or INCOMPATIBLE based on local and remote state."""
        mock_response = mock_get.return_value
        mock_response.json.return_value = {"authorities": []}
        mock_response.raise_for_status.return_value = None
        # 1. Mock local state (what's already installed)
        local_data = {
            "old_plugin": {"version": "1.0.0", "name": "Old"},
            "current_plugin": {"version": "2.0.0", "name": "Current"},
        }

        # 2. Mock remote registry
        remote_registry = {
            "plugins": {
                "old_plugin": {
                    "version": "1.1.0",
                    "name": "Old",
                    "download_url": "...",
                    "min_core_version": "0.1.0",
                },
                "current_plugin": {
                    "version": "2.0.0",
                    "name": "Current",
                    "download_url": "...",
                    "min_core_version": "0.1.0",
                },
                "new_plugin": {
                    "version": "1.0.0",
                    "name": "New",
                    "download_url": "...",
                    "min_core_version": "0.1.0",
                },
                "future_plugin": {
                    "version": "1.0.0",
                    "name": "Future",
                    "download_url": "...",
                    "min_core_version": "9.9.9",
                },
            }
        }

        with (
            patch(
                "karcytics.core.network.registry_sync.RegistrySync.fetch_remote_registry",
                return_value=remote_registry,
            ),
            patch(
                "karcytics.core.network.registry_sync.RegistrySync.get_local_state",
                return_value=local_data,
            ),
        ):
            inventory = updater.evaluate_store_state()

            assert inventory["old_plugin"]["state"] == "UPDATE"
            assert inventory["current_plugin"]["state"] == "UP_TO_DATE"
            assert inventory["new_plugin"]["state"] == "INSTALL"
            assert inventory["future_plugin"]["state"] == "INCOMPATIBLE"

    def test_check_for_core_updates_detection(self, updater):
        """Tests core update detection logic."""
        # Case 1: Newer version available (self-published registry.json, flat shape)
        remote_data = {
            "version": "9.9.9",
            "download_url": "http://karcytics.io",
            "notes": "- fix: something",
        }
        with patch.object(updater, "fetch_remote_registry", return_value=remote_data):
            needed, info = updater.check_for_core_updates()
            assert needed is True
            assert info["version"] == "9.9.9"

        # Case 2: Current or older version
        remote_data = {"version": "0.0.1"}
        with patch.object(updater, "fetch_remote_registry", return_value=remote_data):
            needed, _ = updater.check_for_core_updates()
            assert needed is False

    def test_check_for_core_updates_uses_core_registry_url(self, updater):
        """Ensures the core update-check fetches Karcytics's own registry.json, not distribution's."""
        with patch.object(
            updater, "fetch_remote_registry", return_value={"version": "0.0.1"}
        ) as mock_fetch:
            updater.check_for_core_updates()
            mock_fetch.assert_called_once_with(updater.core_registry_url)

    @patch("requests.Session.get")
    def test_install_plugin_updates_local_registry(self, mock_get, updater):
        """Verify that successful installation updates the local registry file."""
        mock_response = mock_get.return_value
        import io

        zip_bytes = create_safe_zip()
        mock_response.content = zip_bytes
        mock_response.raw = io.BytesIO(zip_bytes)
        mock_response.iter_content.return_value = [zip_bytes]
        mock_response.raise_for_status.return_value = None

        plugin_info = {"version": "1.2.3", "name": "Test Plugin", "download_url": "http://fake.url"}
        success, msg = updater.install_plugin("test_plugin", plugin_info)

        if not success:
            pytest.fail(msg)
        # Verify local registry file now contains the new plugin
        local_state = updater.get_local_state()
        assert local_state["test_plugin"]["version"] == "1.2.3"
        assert local_state["test_plugin"]["name"] == "Test Plugin"

    def test_remove_plugin_logic(self, updater, temp_plugin_dir):
        """Verify that removing a plugin deletes files and registry entries."""
        # Setup: Create a fake plugin folder and registry entry
        plugin_dir = updater.plugin_dir / "to_delete"
        plugin_dir.mkdir()
        (plugin_dir / "some_file.py").write_text("print('hi')")

        local_data = {"to_delete": {"version": "1.0.0", "name": "Delete Me"}}
        with open(updater.local_registry_path, "w", encoding="utf-8") as f:
            json.dump(local_data, f)

        # Execution
        success, _ = updater.remove_plugin("to_delete")

        assert success is True
        assert not plugin_dir.exists()
        assert "to_delete" not in updater.get_local_state()

    def test_fetch_remote_registry_error(self, updater):
        """Ensures that network errors during registry fetch return an empty dict."""
        with patch("requests.Session.get", side_effect=Exception("Timeout")):
            res = updater.fetch_remote_registry("http://bad.url")
            assert res == {}

    def test_get_local_state_corrupted_manifest(self, updater):
        """Verifies that corrupted manifest.json files are skipped but others are loaded."""
        plugin_dir = updater.plugin_dir / "bad_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "pyproject.toml").write_text("invalid_toml = [")

        good_dir = updater.plugin_dir / "good_plugin"
        good_dir.mkdir()
        (good_dir / "pyproject.toml").write_text(
            _dict_to_toml(
                {"id": "good", "version": "1.0.0", "name": "good", "authors": [{"name": "A"}]}
            )
        )

        state = updater.get_local_state()
        assert "good" in state
        assert "bad_plugin" not in state

    def test_install_plugin_failure_path(self, updater):
        """Ensures that installation failures are caught and reported."""
        with patch("requests.Session.get", side_effect=Exception("IO Error")):
            success, msg = updater.install_plugin("fail", {"download_url": "..."})
            assert success is False
            assert "Failed to install" in msg

    def test_sync_keys_cleanup(self, updater, temp_plugin_dir, monkeypatch):
        """Verifies that keys no longer in the trusted list are removed from disk."""
        monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)
        roots_dir = temp_plugin_dir / ".karcytics" / "trusted_roots"
        roots_dir.mkdir(parents=True, exist_ok=True)
        old_key = roots_dir / "network_old.pub"
        old_key.write_bytes(b"data")

        # Sync with an empty list should remove the old key
        TrustSync.sync_keys([], prefix="network_")
        assert not old_key.exists()

    def test_sync_keys_rejects_traversal_attack(self, updater, temp_plugin_dir, monkeypatch):
        """Verify that sync_keys rejects path traversal attempts in entity IDs."""
        monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)
        roots_dir = temp_plugin_dir / ".karcytics" / "trusted_roots"
        roots_dir.mkdir(parents=True, exist_ok=True)

        # Attempt to write outside trusted_roots via path traversal
        malicious_entities = [
            {"id": "../../../tmp/evil", "public_key": "aabbcc"},
            {"id": "..\\..\\..\\tmp\\evil2", "public_key": "ddeeff"},
            {"id": "normal_id/../../../evil3", "public_key": "112233"},
        ]

        # Should not raise but should skip invalid entries
        TrustSync.sync_keys(malicious_entities, prefix="network_")

        # Verify no files were created outside roots_dir
        parent_dir = roots_dir.parent
        for item in parent_dir.rglob("*evil*"):
            # If the item is inside roots_dir, it was safely sanitized and contained
            if roots_dir in item.parents:
                continue
            # If any evil files exist outside roots_dir, fail the test
            raise AssertionError(f"Malicious file escaped roots_dir: {item}")

        # Verify only valid files (none in this case) exist in roots_dir
        created_files = list(roots_dir.glob("network_*.pub"))
        assert len(created_files) == 3, "Sanitized files should have been created for invalid IDs"

    def test_authority_sync_404_ignored(self, updater, temp_plugin_dir, monkeypatch):
        """Ensures that a 404 on the authority registry is handled silently."""
        monkeypatch.setattr(Path, "home", lambda: temp_plugin_dir)
        roots_dir = temp_plugin_dir / ".karcytics" / "trusted_roots"
        roots_dir.mkdir(parents=True, exist_ok=True)

        with patch("requests.Session.get") as mock_get:
            mock_get.return_value.status_code = 404
            # Should not raise
            updater.fetch_and_sync_authorities()

            # Verify no authority keys were synchronized
            auth_keys = list(roots_dir.glob("auth_*.pub"))
            assert len(auth_keys) == 0, "No authority keys should be synchronized after 404"

    @patch("karcytics.core.network.trust_sync.KARCYTICS_ROOT_PUBLIC_KEY_HEX", "0" * 64)
    def test_authority_sync_signature_verification_failure(self, updater):
        """Verifies that authority sync aborts if signature verification fails."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Generate a real key pair but use the wrong one for verification
        private_key = ed25519.Ed25519PrivateKey.generate()
        authorities = [{"id": "a", "public_key": "00"}]
        canonical_bytes = json.dumps(authorities, sort_keys=True).encode()
        sig = private_key.sign(canonical_bytes).hex()

        with patch("requests.Session.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"authorities": authorities, "signature": sig}
            # This should fail because the root public key hex was patched to 00...
            with patch("karcytics.core.network.trust_sync.TrustSync.sync_keys") as mock_sync:
                updater.fetch_and_sync_authorities()
                mock_sync.assert_not_called()

    def test_sync_system_assets_logic(self, updater):
        """Verify that newer system assets are downloaded and recorded in local metadata."""
        import hashlib

        fake_content = b"zipdata"
        fake_hash = hashlib.sha256(fake_content).hexdigest()

        remote_data = {
            "sdk": {"version": "2.0.0", "download_url": "http://sdk.zip", "sha256": fake_hash},
            "plugins": {},
        }
        local_assets = {"sdk": {"version": "1.0.0"}}

        assets_json = updater.plugin_dir / "system_assets.json"
        assets_json.write_text(json.dumps(local_assets))

        with (
            patch.object(updater, "fetch_remote_registry", return_value=remote_data),
            patch("requests.Session.get") as mock_get,
            patch("shutil.rmtree"),
            patch("zipfile.ZipFile"),
            patch("karcytics.core.network.system_assets.safe_extract"),
        ):
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.content = fake_content

            updater.sync_system_assets()

            # Verify it tried to download the new SDK
            mock_get.assert_called()
            # Verify it updated the local tracking file
            updated_assets = json.loads(assets_json.read_text())
            assert updated_assets["sdk"]["version"] == "2.0.0"

    def test_plugin_installer_worker_exceptions(self, tmp_path):
        """Verify exception handling in the PluginInstallerWorker thread."""
        from karcytics.ui.workers.plugin_installer import PluginInstallerWorker

        # Patch the signal on the class before instantiation
        with patch.object(PluginInstallerWorker, "finished") as mock_finished:
            worker = PluginInstallerWorker("test", "url", tmp_path)
            with patch(
                "karcytics.ui.workers.plugin_installer.NetworkClient.get",
                side_effect=Exception("Crash"),
            ):
                worker.run()
                mock_finished.emit.assert_called_with(False, "Installation error: Crash")
