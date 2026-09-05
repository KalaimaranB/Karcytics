from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from karcytics.core.package_manager import PackageManager
from karcytics.ui.workers.plugin_dependency_installer import PluginDependencyInstallerWorker


def test_package_manager_default_init(monkeypatch, tmp_path):
    """Verify default cache directory initialization."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    pm = PackageManager()
    assert ".karcytics" in str(pm.cache_dir)
    assert pm.cache_dir.exists()


@patch("karcytics.core.package_manager.PackageManager.resolve_and_install_all")
def test_plugin_installer_worker(mock_resolve, tmp_path: Path):
    """Verify that PluginDependencyInstallerWorker successfully runs in background and processes manifest dependencies."""
    cache_dir = tmp_path / "cache"
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    with open(plugin_dir / "pyproject.toml", "w", encoding="utf-8") as f:
        f.write(
            '[project]\nname = "my_plugin"\nversion = "1.0.0"\ndescription = "desc"\nauthors = [{name = "author"}]\n'
            '[tool.karcytics.plugin]\nid = "my_plugin"\nauthors = [{name = "author", role = "Developer"}]\n'
            '[tool.karcytics.plugin.python_dependencies]\nscipy = "1.11.3"\n'
        )

    worker = PluginDependencyInstallerWorker(plugin_dir, cache_dir=cache_dir)
    # Run execution directly (synchronous for test)
    worker.run()

    mock_resolve.assert_called_once()


def test_worker_manifest_missing(tmp_path):
    """Verify worker handles missing manifest.json."""
    with patch.object(PluginDependencyInstallerWorker, "finished") as mock_finished:
        worker = PluginDependencyInstallerWorker(tmp_path)
        worker.run()
        mock_finished.emit.assert_called_with(
            False, "pyproject.toml missing from plugin directory."
        )


def test_worker_no_deps(tmp_path):
    """Verify worker handles plugins with no dependencies."""
    plugin_dir = tmp_path / "plugin_no_deps"
    plugin_dir.mkdir()
    (plugin_dir / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "1.0.0"\ndescription = "desc"\nauthors = [{name = "author"}]\n'
        '[tool.karcytics.plugin]\nid = "test"\nauthors = [{name = "author", role = "Developer"}]\n'
    )
    with patch.object(PluginDependencyInstallerWorker, "finished") as mock_finished:
        worker = PluginDependencyInstallerWorker(plugin_dir)
        worker.run()
        mock_finished.emit.assert_called_with(True, "")


def test_worker_exception(tmp_path):
    """Verify worker handles unexpected exceptions during installation."""
    plugin_dir = tmp_path / "plugin_crash"
    plugin_dir.mkdir()
    (plugin_dir / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "1.0.0"\ndescription = "desc"\nauthors = [{name = "author"}]\n'
        '[tool.karcytics.plugin]\nid = "test"\nauthors = [{name = "author", role = "Developer"}]\n'
        '[tool.karcytics.plugin.python_dependencies]\na = "1"\n'
    )
    with patch.object(PluginDependencyInstallerWorker, "finished") as mock_finished:
        worker = PluginDependencyInstallerWorker(plugin_dir)
        with patch.object(worker.pm, "resolve_and_install_all", side_effect=Exception("Crash")):
            worker.run()
            mock_finished.emit.assert_called_with(False, "Crash")


def test_resolve_bundled_uv_windows(monkeypatch, tmp_path):
    """Verify that on Windows, uv.exe is resolved."""
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")

    pm = PackageManager()

    # Create fake uv.exe
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv.exe").touch()

    # Create dummy plugin and fake python
    plugin_dir = tmp_path / "test_win_uv"
    plugin_dir.mkdir()
    venv_python = plugin_dir / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    worker_script = plugin_dir / "analysis" / "fcs_worker.py"
    worker_script.parent.mkdir(parents=True)
    worker_script.touch()

    with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
        mock_run.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        mock_popen.return_value.returncode = 0
        pm.resolve_and_install_all({"dummy": "1.0"}, plugin_dir, lambda x: None)

        # Verify uv.exe was used
        args = mock_run.call_args_list[0][0][0]
        assert args[0] == str(bin_dir / "uv.exe")
        args_popen = mock_popen.call_args_list[0][0][0]
        assert args_popen[0] == str(bin_dir / "uv.exe")


def test_resolve_bundled_uv_unix(monkeypatch, tmp_path):
    """Verify that on Unix, uv is resolved."""
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")

    pm = PackageManager()

    # Create fake uv
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").touch()

    # Create dummy plugin and fake python
    plugin_dir = tmp_path / "test_unix_uv"
    plugin_dir.mkdir()
    venv_python = plugin_dir / ".venv" / "bin" / "python3.12"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    worker_script = plugin_dir / "analysis" / "fcs_worker.py"
    worker_script.parent.mkdir(parents=True)
    worker_script.touch()

    with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
        mock_run.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        mock_popen.return_value.returncode = 0
        pm.resolve_and_install_all({"dummy": "1.0"}, plugin_dir, lambda x: None)

        # Verify uv was used
        args = mock_run.call_args_list[0][0][0]
        assert args[0] == str(bin_dir / "uv")
        args_popen = mock_popen.call_args_list[0][0][0]
        assert args_popen[0] == str(bin_dir / "uv")


class _FakeDaemon:
    """Stands in for `karcytics_sdk.plugin.daemon.PluginDaemon` — `_run_selftest`
    only needs `ensure_started`/`call`/`shutdown`, so these tests exercise
    `PackageManager`'s own control flow (skip when no daemon script is present,
    wrap a bad ping response or a failed handshake into a RuntimeError, always
    shut the daemon down) without spawning a real subprocess.
    """

    instances: list["_FakeDaemon"] = []

    def __init__(self, plugin_id: str, daemon_script_path: Path | None = None) -> None:
        self.plugin_id = plugin_id
        self.daemon_script_path = daemon_script_path
        self.ensure_started_error: Exception | None = None
        self.call_result: dict[str, Any] = {"status": "pong"}
        self.call_error: Exception | None = None
        self.shutdown_called = False
        _FakeDaemon.instances.append(self)

    def ensure_started(self, timeout: float = 30.0) -> None:  # noqa: ARG002
        if self.ensure_started_error is not None:
            raise self.ensure_started_error

    def call(self, method: str, kwargs: dict, timeout: float = 120.0) -> dict:  # noqa: ARG002
        if self.call_error is not None:
            raise self.call_error
        return self.call_result

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture(autouse=True)
def _reset_fake_daemon_instances():
    _FakeDaemon.instances = []
    yield
    _FakeDaemon.instances = []


def _make_isolated_plugin_dir(tmp_path: Path, plugin_id: str) -> Path:
    plugin_dir = tmp_path / plugin_id
    daemon_worker = (
        plugin_dir / "src" / "karcytics_plugins" / plugin_id / "analysis" / "daemon_worker.py"
    )
    daemon_worker.parent.mkdir(parents=True)
    daemon_worker.touch()
    return plugin_dir


def test_run_selftest_skips_when_no_daemon_script_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginDaemon", _FakeDaemon)

    plugin_dir = tmp_path / "no_daemon_plugin"
    plugin_dir.mkdir()

    PackageManager._run_selftest(plugin_dir)

    assert _FakeDaemon.instances == []


def test_run_selftest_passes_on_pong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginDaemon", _FakeDaemon)

    plugin_dir = _make_isolated_plugin_dir(tmp_path, "flow_cytometry")

    PackageManager._run_selftest(plugin_dir)

    assert len(_FakeDaemon.instances) == 1
    daemon = _FakeDaemon.instances[0]
    assert daemon.plugin_id == "flow_cytometry"
    assert daemon.shutdown_called is True


def test_run_selftest_raises_on_unexpected_ping_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginDaemon", _FakeDaemon)

    plugin_dir = _make_isolated_plugin_dir(tmp_path, "flow_cytometry")

    def _install_bad_response(
        plugin_id: str, daemon_script_path: Path | None = None
    ) -> _FakeDaemon:
        daemon = _FakeDaemon(plugin_id, daemon_script_path)
        daemon.call_result = {"status": "unexpected"}
        return daemon

    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginDaemon", _install_bad_response)

    with pytest.raises(RuntimeError, match="self-test failed"):
        PackageManager._run_selftest(plugin_dir)


def test_run_selftest_raises_and_still_shuts_down_when_handshake_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_dir = _make_isolated_plugin_dir(tmp_path, "flow_cytometry")

    created: list[_FakeDaemon] = []

    def _install_failing_handshake(
        plugin_id: str, daemon_script_path: Path | None = None
    ) -> _FakeDaemon:
        daemon = _FakeDaemon(plugin_id, daemon_script_path)
        daemon.ensure_started_error = RuntimeError("failed ready handshake")
        created.append(daemon)
        return daemon

    monkeypatch.setattr("karcytics_sdk.plugin.daemon.PluginDaemon", _install_failing_handshake)

    with pytest.raises(RuntimeError, match="self-test failed"):
        PackageManager._run_selftest(plugin_dir)

    assert created[0].shutdown_called is True
