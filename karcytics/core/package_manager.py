"""Core module."""

import logging
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from karcytics.core.config import AppConfig

logger = logging.getLogger(__name__)

# Some plugins' daemon workers import Numba-backed packages (e.g. umap-learn,
# hdbscan for flow_cytometry) at module load. Numba's first-ever JIT compile
# on a brand-new venv — before anything is cached to disk — routinely takes
# well over 30s on a modest machine, even though the daemon isn't actually
# broken. This self-test only runs once at install time, so a generous
# timeout here costs nothing on every subsequent (fast, cached) daemon start.
_SELFTEST_DAEMON_READY_TIMEOUT = 120.0


class PackageManager:
    """Manages the global pre-compiled package cache and user-space symlinking."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize the package manager with the specified or default cache directory.

        Parameters:
            cache_dir (Path | None): Directory used to cache packages. Defaults to the application
            package cache directory.
        """
        if cache_dir is None:
            self.cache_dir = AppConfig.APP_DATA_DIR / "cache" / "packages"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _build_requirements(dependencies: dict[str, str]) -> list[str]:
        """Build the requirements list from dependency dictionary.

        Parameters:
            dependencies (dict[str, str]): Dependency names mapped to versions or constraints.

        Returns:
            list[str]: List of requirement specifiers.
        """
        reqs = []
        for name, ver in dependencies.items():
            if ver and not ver.startswith(("=", ">", "<")):
                reqs.append(f"{name}=={ver}")
            else:
                reqs.append(f"{name}{ver}")

        # Ensure setuptools is always available
        if not any(r.startswith("setuptools") for r in reqs):
            reqs.append("setuptools<71.0.0")

        return reqs

    @staticmethod
    def _resolve_uv_path() -> str:
        """Resolve the path to the uv executable.

        Returns:
            str: Path to the uv executable.

        Raises:
            RuntimeError: If uv is not found.
        """
        uv_path = None
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            uv_name = "uv.exe" if sys.platform == "win32" else "uv"
            bundled_uv = Path(sys._MEIPASS) / "bin" / uv_name
            if bundled_uv.exists():
                uv_path = str(bundled_uv)
        if not uv_path:
            uv_path = shutil.which("uv")

        if not uv_path:
            raise RuntimeError(
                "uv is required to install plugin dependencies but was not found "
                "(bundled uv missing and not on PATH)."
            )

        return uv_path

    @staticmethod
    def _create_venv(uv_path: str, venv_dir: Path, sp_kwargs: dict[str, Any]) -> Path:
        """Create a virtual environment for the plugin.

        Parameters:
            uv_path (str): Path to the uv executable.
            venv_dir (Path): Directory for the virtual environment.
            sp_kwargs (dict[str, Any]): Subprocess keyword arguments.

        Returns:
            Path: Path to the Python interpreter in the venv.

        Raises:
            RuntimeError: If venv creation fails or interpreter is not found.
        """
        venv_cmd = [uv_path, "venv", str(venv_dir), "--python", "3.12", "--seed"]
        logger.info("Creating plugin venv: %s", " ".join(venv_cmd))
        result = subprocess.run(venv_cmd, capture_output=True, text=True, **sp_kwargs)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create plugin venv: {result.stderr}\nCommand: {' '.join(venv_cmd)}"
            )

        # Resolve the interpreter path cross-platform
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
        else:
            venv_python = venv_dir / "bin" / "python3.12"

        if not venv_python.exists():
            raise RuntimeError(f"uv venv did not produce expected interpreter at {venv_python}")

        return venv_python

    @staticmethod
    def _run_selftest(plugin_dir: Path) -> None:
        """Run the plugin's self-test if available.

        Parameters:
            plugin_dir (Path): Directory containing the plugin.

        Raises:
            RuntimeError: If the self-test fails.
        """
        plugin_id = plugin_dir.name
        daemon_script = (
            plugin_dir / "src" / "karcytics_plugins" / plugin_id / "analysis" / "daemon_worker.py"
        )
        if daemon_script.exists():
            PackageManager._run_isolated_daemon_selftest(plugin_id, daemon_script)
        else:
            logger.info(f"No self-test script found at {daemon_script}, skipping self-test.")

    @staticmethod
    def _run_isolated_daemon_selftest(plugin_id: str, daemon_script: Path) -> None:
        """Self-test an isolated plugin's venv via a real ping over its worker protocol.

        Uses the same msgpack/stdio protocol `PluginDaemon` uses at runtime, so a
        broken interpreter or missing heavy dependency fails the daemon's own
        startup ready handshake before ping is even reachable.

        Parameters:
            plugin_id (str): The plugin's id, used for daemon logging.
            daemon_script (Path): Path to the plugin's daemon_worker.py.

        Raises:
            RuntimeError: If the daemon fails to start or does not answer ping.
        """
        from karcytics_sdk.plugin.daemon import PluginDaemon

        daemon = PluginDaemon(plugin_id, daemon_script_path=daemon_script)
        try:
            daemon.ensure_started(timeout=_SELFTEST_DAEMON_READY_TIMEOUT)
            result = daemon.call("ping", {}, timeout=10.0)
            if result.get("status") != "pong":
                raise RuntimeError(f"daemon responded unexpectedly to ping: {result}")
        except Exception as exc:
            raise RuntimeError(
                f"Plugin venv self-test failed — interpreter, packages, or worker protocol "
                f"are broken: {exc}"
            ) from exc
        finally:
            daemon.shutdown()

        logger.info("Plugin venv self-test passed (isolated daemon ping/pong).")

    def resolve_and_install_all(  # noqa: C901
        self,
        dependencies: dict[str, str],
        plugin_dir: Path,
        progress_callback: Callable[[int], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ):
        """Install the plugin's dependencies into its standalone virtual environment.

        Parameters:
            dependencies (dict[str, str]): Dependency names mapped to versions or version
                constraints.
            plugin_dir (Path): Directory containing the plugin.
            progress_callback (Callable[[int], None] | None): Callback receiving installation
                progress percentages.
            log_callback (Callable[[str], None] | None): Callback receiving log messages.

        Raises:
            RuntimeError: If `uv` is unavailable or environment creation, dependency
                installation, interpreter discovery, or the plugin self-test fails.
        """
        if not dependencies:
            if progress_callback:
                progress_callback(100)
            if log_callback:
                log_callback("No python dependencies to install.")
            return

        venv_dir = plugin_dir / ".venv"

        reqs = self._build_requirements(dependencies)
        uv_path = self._resolve_uv_path()

        logger.info(
            "Preparing plugin dependency install: venv=%s uv_path=%s req_count=%d",
            venv_dir,
            uv_path,
            len(reqs),
        )
        logger.debug("Plugin dependency requirement list: %s", reqs)

        if log_callback:
            log_callback(f"Bootstrapping isolated environment in {venv_dir}...")

        if progress_callback:
            progress_callback(5)

        # Hide subprocess window on Windows
        sp_kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            # subprocess.CREATE_NO_WINDOW = 0x08000000
            sp_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        venv_python = self._create_venv(uv_path, venv_dir, sp_kwargs)

        if progress_callback:
            progress_callback(15)

        # Install packages into the interpreter
        install_cmd = [uv_path, "pip", "install", "--python", str(venv_python)] + reqs
        logger.info("Installing plugin dependencies: %s", " ".join(install_cmd))

        if log_callback:
            log_callback("\nResolving and installing dependencies...")

        process = subprocess.Popen(
            install_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **sp_kwargs
        )

        if process.stdout:
            for line in process.stdout:
                line = line.strip()
                if line and log_callback:
                    log_callback(line)

        process.wait()
        if process.returncode != 0:
            cmd_str = " ".join(install_cmd)
            raise RuntimeError(
                f"Failed to install dependencies (code {process.returncode})\nCommand: {cmd_str}"
            )

        if log_callback:
            log_callback(
                "\nRunning plugin self-test... "
                "(this may take a minute on first install due to JIT compilation)"
            )

        self._run_selftest(plugin_dir)

        if log_callback:
            log_callback("Self-test passed! Installation complete.")

        if progress_callback:
            progress_callback(100)
