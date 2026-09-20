"""Tests for karcytics.core.resource_manager.default_app_icon_path — the
Hub's own icon file, shared by KarcyticsApp's dev-mode window/menu-bar icon
(karcytics.__main__) and the fallback every isolated plugin's window uses
when it doesn't ship its own (core_services_bootstrap
._register_default_icon_path).

Regression coverage: this used to be hardcoded as resource_path("icon.icns")
in __main__.py, a file that has never existed in this repo (dev tree or
PyInstaller bundle) — Karcytics.spec bundles logo.icns/logo.ico unrenamed —
so the lookup silently always missed, on every platform.
"""

import sys

from karcytics.core.resource_manager import default_app_icon_path


def test_default_app_icon_path_resolves_to_an_existing_file():
    icon_path = default_app_icon_path()

    assert icon_path.exists()


def test_default_app_icon_path_picks_the_right_extension_per_platform():
    icon_path = default_app_icon_path()

    expected_suffix = ".icns" if sys.platform == "darwin" else ".ico"
    assert icon_path.suffix == expected_suffix
