"""Karcytics — Bio Analysis Made Simple.

A free, intuitive platform for lab students
and professionals. Automates tedious bio analysis workflows
through a modern desktop interface.

Modules:
    analysis: Headless image processing engine (usable without GUI).
    ui: PyQt6 desktop interface components.
"""


def _get_version():
    """Extract version from pyproject.toml (dev/frozen) or package metadata (installed)."""
    import importlib.metadata
    import sys
    from pathlib import Path

    # 1. Parse pyproject.toml
    # Check both the source directory and the PyInstaller bundle directory
    search_paths = [
        Path(__file__).parent.parent / "pyproject.toml",
    ]

    # If running in a PyInstaller bundle, check the bundle root
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        search_paths.append(Path(sys._MEIPASS) / "pyproject.toml")

    for pyproject_path in search_paths:
        if pyproject_path.exists():
            try:
                import tomllib

                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    version = data.get("project", {}).get("version")
                    if version:
                        return version
            except Exception as e:
                import logging

                logging.getLogger(__name__).debug(
                    f"Failed to read version from {pyproject_path}: {e}"
                )
                # Continue to fallback if one path fails
                continue

    # 2. Fallback: Try standard metadata (for installed packages)
    try:
        return importlib.metadata.version("karcytics")
    except importlib.metadata.PackageNotFoundError:
        pass

    # 3. Final Fallback: Return a placeholder instead of crashing
    return "0.0.0-unknown"


__version__ = _get_version()
__author__ = "Karcytics Contributors"
