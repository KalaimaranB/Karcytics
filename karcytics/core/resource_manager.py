"""Centralized Resource Path Handling for PyInstaller and Development."""

import sys
from pathlib import Path


def resource_path(relative_path: str | Path) -> Path:
    """Get the absolute path to a resource, works for dev and for PyInstaller.

    PyInstaller creates a temporary folder and stores the path in `sys._MEIPASS`.
    In development, it uses the local relative path from the project root.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        # Path(__file__) is karcytics/core/resource_manager.py
        # We want the root of the project
        base_path = Path(__file__).parent.parent.parent

    # Special handling for paths that are nested differently in the bundle
    # If the relative path starts with 'karcytics/', and we are in dev, it's fine.
    # But in the bundle, we might have mapped 'karcytics/themes' to 'themes'.
    # We should handle both cases or ensure the .spec file matches.

    full_path = base_path / relative_path

    # If the relative path wasn't found at the root, check inside karcytics/
    if not full_path.exists() and not str(relative_path).startswith("karcytics/"):
        alt_path = base_path / "karcytics" / relative_path
        if alt_path.exists():
            return alt_path

    return full_path


def default_app_icon_path() -> Path:
    """Resolve the Hub's own icon file.

    It resolves to `logo.icns` on macOS and `logo.ico` elsewhere — the same file
    `Karcytics.spec` bundles as `icon_file` and copies to the frozen app's root
    unrenamed, so this matches both a dev checkout (where only `logo.icns`/`logo.ico`
    exist at the repo root, not `icon.icns`) and a PyInstaller build.

    Shared by `karcytics.__main__` (the Hub's own window/Dock icon in dev —
    see `KarcyticsApp.__init__`) and `core_services_bootstrap` (the fallback
    every isolated plugin's window uses when it doesn't ship its own).
    """
    icon_file = "logo.icns" if sys.platform == "darwin" else "logo.ico"
    return resource_path(icon_file)
