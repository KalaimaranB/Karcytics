"""Tests for karcytics.core.plugins.environment cross-platform plugin venv resolution."""

import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from karcytics.core.plugins.environment import PluginEnvironmentInjector


def _dict_to_toml(d):
    # Convert flat dict to pyproject.toml format
    """
    Convert a flat dictionary into a minimal pyproject.toml configuration string.

    Parameters:
        d (dict): Configuration values for the project and Karcytics plugin.

    Returns:
        str: TOML-formatted project and plugin configuration.
    """
    lines = []
    lines.append("[project]")
    lines.append(f'name = "{d.get("name", "test")}"')
    lines.append(f'version = "{d.get("version", "1.0.0")}"')
    if "description" in d:
        lines.append(f'description = "{d["description"]}"')

    lines.append("")
    lines.append("[tool.karcytics.plugin]")
    lines.append(f'id = "{d.get("id", "test_id")}"')
    return "\n".join(lines)


def _expected_venv_python(venv_dir: Path) -> Path:
    """
    Determine the expected Python interpreter path within a virtual environment.

    Parameters:
        venv_dir (Path): Root directory of the virtual environment.

    Returns:
        Path: Platform-specific path to the virtual environment's Python interpreter.
    """
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / f"python{sys.version_info.major}.{sys.version_info.minor}"


def _expected_site_packages(venv_dir: Path) -> Path:
    """Return the site-packages path for the current OS."""
    if sys.platform == "win32":
        return venv_dir / "Lib" / "site-packages"
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return venv_dir / "lib" / py_ver / "site-packages"


def _uv_available() -> bool:
    """Determine whether the `uv` executable is available on the system PATH.

    Returns:
        bool: `True` if `uv` is available, `False` otherwise.
    """
    return shutil.which("uv") is not None


def _create_plugin_venv_with_package(uv_path: str, venv_dir: Path, package: str) -> Path:
    """Create a virtual environment and install a package into it.

    Parameters:
        uv_path (str): Path to the uv executable.
        venv_dir (Path): Directory where the virtual environment should be created.
        package (str): Package name to install.

    Returns:
        Path: The site-packages directory of the created virtual environment.
    """
    import subprocess as sp

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    sp.run(
        [uv_path, "venv", str(venv_dir), "--python", python_version],
        capture_output=True,
        check=True,
    )
    sp.run(
        [
            uv_path,
            "pip",
            "install",
            "--python",
            str(_expected_venv_python(venv_dir)),
            package,
        ],
        capture_output=True,
        check=True,
    )
    return _expected_site_packages(venv_dir)


class TestVenvPathResolution:
    """Verify interpreter + site-packages paths are OS-correct without running uv."""

    def test_interpreter_path_is_platform_correct(self, tmp_path):
        venv_dir = tmp_path / ".venv"
        expected = _expected_venv_python(venv_dir)

        if sys.platform == "win32":
            assert "Scripts" in str(expected)
            assert expected.name == "python.exe"
        else:
            assert "bin" in str(expected)
            assert expected.name.startswith("python")

    def test_site_packages_path_is_platform_correct(self, tmp_path):
        venv_dir = tmp_path / ".venv"
        sp = _expected_site_packages(venv_dir)

        if sys.platform == "win32":
            assert "Lib" in sp.parts
            assert "site-packages" in sp.parts
            py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
            assert py_ver not in sp.parts
        else:
            py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
            assert py_ver in sp.parts

    def test_inject_plugin_path_finds_windows_layout(self, tmp_path):
        plugin_dir = tmp_path / "cytometrics"
        plugin_dir.mkdir()
        internal_dir = tmp_path / "karcytics" / "plugins"

        # Simulate Windows venv layout
        win_sp = plugin_dir / ".venv" / "Lib" / "site-packages"
        win_sp.mkdir(parents=True)

        PluginEnvironmentInjector.inject_path(plugin_dir, internal_dir)

        assert str(win_sp) in sys.path
        sys.path.remove(str(win_sp))

    def test_inject_plugin_path_finds_unix_layout(self, tmp_path):
        plugin_dir = tmp_path / "cytometrics"
        plugin_dir.mkdir()
        internal_dir = tmp_path / "karcytics" / "plugins"

        # Simulate Unix venv layout
        py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        unix_sp = plugin_dir / ".venv" / "lib" / py_ver / "site-packages"
        unix_sp.mkdir(parents=True)

        PluginEnvironmentInjector.inject_path(plugin_dir, internal_dir)

        assert str(unix_sp) in sys.path
        sys.path.remove(str(unix_sp))

    def _write_fake_dist_info(self, site_packages: Path, name: str, version: str = "1.0.0") -> Path:
        dist_info = site_packages / f"{name}-{version}.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
        )
        return dist_info

    def test_installed_names_excludes_pinned_singleton_packages(self, tmp_path: Path) -> None:
        """Regression test for a real production incident: PySide6 is a transitive
        dependency of karcytics_sdk, so it's installed in every plugin's own
        site-packages too. `_installed_names()` must never surface it as a purge
        candidate — the running process must keep exactly one Qt binding, ever.
        Purging and reloading PySide6 mid-session produced a QFont type mismatch
        (`setFont(): argument 1 has unexpected type 'QFont'`) that then triggered
        an infinite reporting loop (see test_diagnostics.py).
        """
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        self._write_fake_dist_info(site_packages, "PySide6", "6.11.0")
        self._write_fake_dist_info(site_packages, "requests", "2.32.0")

        names = PluginEnvironmentInjector._installed_names(site_packages)

        assert "PySide6" not in names
        assert "requests" in names

    def test_enforce_priority_never_purges_pyqt6(self, tmp_path: Path) -> None:
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        self._write_fake_dist_info(site_packages, "PySide6", "6.11.0")

        # PySide6 is genuinely already loaded in this test process (pytest-qt),
        # and its real location is certainly not our fake tmp_path — exactly the
        # "shadowed" condition enforce_priority looks for.
        assert "PySide6" in sys.modules
        live_module = sys.modules["PySide6"]

        purged = PluginEnvironmentInjector.enforce_priority(tmp_path, site_packages)

        assert "PySide6" not in purged
        assert sys.modules["PySide6"] is live_module


class TestPurgeOwnedAndRemovePluginPaths:
    """Tests for the unload-time primitives used by ModuleManager.unload_module():
    purge_owned() (explicit-name-set purge) and remove_plugin_paths() (scoped
    sys.path cleanup), as opposed to enforce_priority()/cleanup_paths() which
    operate reactively/globally during load.
    """

    def test_purge_owned_excludes_pinned_singletons(self) -> None:
        sys.modules.setdefault("_fake_owned_dep", ModuleType("_fake_owned_dep"))
        try:
            purged = PluginEnvironmentInjector.purge_owned({"PySide6", "_fake_owned_dep"})
            assert "PySide6" not in purged
            assert "_fake_owned_dep" in purged
            assert "PySide6" in sys.modules
            assert "_fake_owned_dep" not in sys.modules
        finally:
            sys.modules.pop("_fake_owned_dep", None)

    def test_purge_owned_removes_submodules(self) -> None:
        sys.modules["_fake_owned_pkg"] = ModuleType("_fake_owned_pkg")
        sys.modules["_fake_owned_pkg.sub"] = ModuleType("_fake_owned_pkg.sub")
        try:
            purged = PluginEnvironmentInjector.purge_owned({"_fake_owned_pkg"})
            assert purged == ["_fake_owned_pkg"]
            assert "_fake_owned_pkg" not in sys.modules
            assert "_fake_owned_pkg.sub" not in sys.modules
        finally:
            sys.modules.pop("_fake_owned_pkg", None)
            sys.modules.pop("_fake_owned_pkg.sub", None)

    def test_purge_owned_ignores_names_not_in_sys_modules(self) -> None:
        purged = PluginEnvironmentInjector.purge_owned({"_nonexistent_module_xyz"})
        assert purged == []

    def test_remove_plugin_paths_is_scoped(self, tmp_path: Path) -> None:
        site_packages_a = tmp_path / "plugin_a" / "site-packages"
        site_packages_b = tmp_path / "plugin_b" / "site-packages"
        site_packages_a.mkdir(parents=True)
        site_packages_b.mkdir(parents=True)

        sys.path.insert(0, str(site_packages_a))
        sys.path.insert(0, str(site_packages_b))
        try:
            PluginEnvironmentInjector.remove_plugin_paths([site_packages_a])

            assert str(site_packages_a) not in sys.path
            assert str(site_packages_b) in sys.path
        finally:
            for p in (str(site_packages_a), str(site_packages_b)):
                if p in sys.path:
                    sys.path.remove(p)


@pytest.mark.skipif(
    not _uv_available(), reason="uv not on PATH — skipped in environments without uv"
)
class TestRealVenvInstallation:
    LIGHTWEIGHT_PACKAGE = "charset-normalizer"

    def _require_uv(self) -> str:
        import shutil

        uv = shutil.which("uv")
        if uv is None:
            pytest.skip("uv not on PATH")
        assert uv is not None
        return uv

    def test_venv_created_with_correct_interpreter(self, tmp_path):
        import subprocess as sp

        uv = self._require_uv()
        venv_dir = tmp_path / ".venv"
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        result = sp.run(
            [uv, "venv", str(venv_dir), "--python", python_version],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        expected_python = _expected_venv_python(venv_dir)
        assert expected_python.exists()

    def test_package_installs_and_is_importable(self, tmp_path):
        import subprocess as sp

        uv = self._require_uv()
        plugin_dir = tmp_path / "cytometrics_integration"
        plugin_dir.mkdir()
        venv_dir = plugin_dir / ".venv"
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        sp.run(
            [uv, "venv", str(venv_dir), "--python", python_version], capture_output=True, text=True
        )
        expected_python = _expected_venv_python(venv_dir)

        sp.run(
            [uv, "pip", "install", "--python", str(expected_python), self.LIGHTWEIGHT_PACKAGE],
            capture_output=True,
            text=True,
        )

        site_packages = _expected_site_packages(venv_dir)
        assert site_packages.exists()

        installed_names = [p.name.lower() for p in site_packages.iterdir()]
        assert any(
            self.LIGHTWEIGHT_PACKAGE.replace("-", "_") in name or self.LIGHTWEIGHT_PACKAGE in name
            for name in installed_names
        )

    def test_inject_and_import_from_real_venv(self, tmp_path):
        """Verifies that a package installed in a plugin's virtual environment can be imported after its site-packages directory is injected.

        Parameters:
            tmp_path: Temporary directory used to create the plugin and virtual environment.
        """
        import subprocess as sp

        uv = self._require_uv()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        plugin_dir = tmp_path / "cytometrics"
        plugin_dir.mkdir()
        internal_dir = tmp_path / "karcytics" / "plugins"
        venv_dir = plugin_dir / ".venv"

        sp.run(
            [uv, "venv", str(venv_dir), "--python", python_version], capture_output=True, check=True
        )
        expected_python = _expected_venv_python(venv_dir)
        sp.run(
            [uv, "pip", "install", "--python", str(expected_python), self.LIGHTWEIGHT_PACKAGE],
            capture_output=True,
            check=True,
        )

        site_packages = _expected_site_packages(venv_dir)
        original_path = sys.path.copy()

        try:
            PluginEnvironmentInjector.inject_path(plugin_dir, internal_dir)
            assert str(site_packages) in sys.path

            pkg_name = self.LIGHTWEIGHT_PACKAGE.replace("-", "_")
            if pkg_name in sys.modules:
                del sys.modules[pkg_name]

            mod = importlib.import_module(pkg_name)
            assert mod is not None
        finally:
            sys.path[:] = original_path

    def test_enforce_priority_overrides_shadow_copy(self, tmp_path: Path) -> None:
        """Reproduces the bokeh/flowkit bug: a dependency already resolved from a
        non-plugin location (simulating a frozen core bundle's copy) must be forced
        to re-resolve from the plugin's own site-packages once `enforce_priority`
        runs, and `inject_path`'s `sys.path` reordering alone must NOT be sufficient
        (this is what let the real bug through undetected).
        """
        uv = shutil.which("uv")
        if not uv:
            pytest.skip("uv not available")
        assert uv is not None

        pkg_name = self.LIGHTWEIGHT_PACKAGE.replace("-", "_")

        # A decoy copy elsewhere on sys.path, imported first — simulates a name
        # already claimed in sys.modules (e.g. by a frozen bundle's importer).
        fake_core_venv = tmp_path / "fake_core" / ".venv"
        fake_core_sp = _create_plugin_venv_with_package(
            uv, fake_core_venv, self.LIGHTWEIGHT_PACKAGE
        )

        # The plugin's own copy.
        plugin_dir = tmp_path / "cytometrics_isolation"
        plugin_dir.mkdir()
        internal_dir = tmp_path / "karcytics" / "plugins"
        venv_dir = plugin_dir / ".venv"
        site_packages = _create_plugin_venv_with_package(uv, venv_dir, self.LIGHTWEIGHT_PACKAGE)

        original_path = sys.path.copy()
        sys.modules.pop(pkg_name, None)
        # Snapshot all submodules for cleanup
        original_submodules = {
            k: v for k, v in sys.modules.items() if k == pkg_name or k.startswith(f"{pkg_name}.")
        }

        try:
            sys.path.insert(0, str(fake_core_sp))
            decoy = importlib.import_module(pkg_name)
            assert str(fake_core_sp) in str(decoy.__file__)

            PluginEnvironmentInjector.inject_path(plugin_dir, internal_dir)
            purged = PluginEnvironmentInjector.enforce_priority(plugin_dir, site_packages)
            assert pkg_name in purged

            resolved = importlib.import_module(pkg_name)
            assert str(site_packages) in str(resolved.__file__)

            still_shadowed = PluginEnvironmentInjector.verify_isolation(purged, site_packages)
            assert still_shadowed == []
        finally:
            sys.path[:] = original_path
            # Remove all modules and submodules from the namespace
            keys_to_remove = [
                k for k in sys.modules if k == pkg_name or k.startswith(f"{pkg_name}.")
            ]
            for k in keys_to_remove:
                del sys.modules[k]
            # Restore original modules
            sys.modules.update(original_submodules)


def test_installed_names_derives_from_dist_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _installed_names correctly derives top-level import names from dist.files.

    Verifies the Pillow→PIL, scikit-learn→sklearn, and beautifulsoup4→bs4 mappings
    when distributions lack top_level.txt metadata.
    """
    from unittest.mock import MagicMock

    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    # Mock distributions for Pillow, scikit-learn, and beautifulsoup4
    mock_distributions = []

    # Pillow → PIL mapping
    pillow_dist = MagicMock()
    pillow_dist.name = "Pillow"
    pillow_dist.metadata.get.return_value = "Pillow"
    pillow_dist.read_text.side_effect = Exception("No top_level.txt")
    pillow_dist.files = [
        Path("PIL/__init__.py"),
        Path("PIL/Image.py"),
        Path("PIL/ImageFilter.py"),
        Path("Pillow-10.0.0.dist-info/METADATA"),
    ]
    mock_distributions.append(pillow_dist)

    # scikit-learn → sklearn mapping
    sklearn_dist = MagicMock()
    sklearn_dist.name = "scikit-learn"
    sklearn_dist.metadata.get.return_value = "scikit-learn"
    sklearn_dist.read_text.side_effect = Exception("No top_level.txt")
    sklearn_dist.files = [
        Path("sklearn/__init__.py"),
        Path("sklearn/ensemble.py"),
        Path("sklearn/tree.py"),
        Path("scikit_learn-1.3.0.dist-info/METADATA"),
    ]
    mock_distributions.append(sklearn_dist)

    # beautifulsoup4 → bs4 mapping
    bs4_dist = MagicMock()
    bs4_dist.name = "beautifulsoup4"
    bs4_dist.metadata.get.return_value = "beautifulsoup4"
    bs4_dist.read_text.side_effect = Exception("No top_level.txt")
    bs4_dist.files = [
        Path("bs4/__init__.py"),
        Path("bs4/element.py"),
        Path("bs4/builder.py"),
        Path("beautifulsoup4-4.12.0.dist-info/METADATA"),
    ]
    mock_distributions.append(bs4_dist)

    # Mock importlib.metadata.distributions to return our mock distributions
    def mock_distributions_func(path: Any = None) -> list[Any]:
        return mock_distributions

    monkeypatch.setattr("importlib.metadata.distributions", mock_distributions_func)

    # Call _installed_names
    result = PluginEnvironmentInjector._installed_names(site_packages)

    # Assert the correct import names are derived from dist.files
    assert "PIL" in result, "Pillow should map to PIL"
    assert "sklearn" in result, "scikit-learn should map to sklearn"
    assert "bs4" in result, "beautifulsoup4 should map to bs4"

    # Ensure we don't get the distribution names themselves
    assert "Pillow" not in result
    assert "scikit-learn" not in result
    assert "scikit_learn" not in result
    assert "beautifulsoup4" not in result
