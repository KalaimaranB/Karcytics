# -*- mode: python ; coding: utf-8 -*-
import sys
import shutil
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Prevent PyInstaller from crashing when tracing PyTorch's massive dependency tree
sys.setrecursionlimit(5000)

icon_file = 'logo.icns' if sys.platform == 'darwin' else 'logo.ico'

# 1. Force-collect heavy core libraries
pil_bins, pil_datas, pil_hidden = collect_all('PIL')
cert_bins, cert_datas, cert_hidden = collect_all('certifi')
sdk_bins, sdk_datas, sdk_hidden = collect_all('karcytics_sdk')

# --- THE OPTIMIZATION ENGINE ---
# Strip out hundreds of MBs of useless testing/mock data from the final build
def filter_bloat(item_list):
    clean_list = []
    for item in item_list:
        dest = item[1].lower() if len(item) > 1 else item[0].lower()
        if any(bad in dest for bad in ['/test/', '/tests/', '/testing/', 'test_', '__pycache__']):
            continue
        clean_list.append(item)
    return clean_list

all_bins = sorted(filter_bloat(pil_bins + cert_bins + sdk_bins))
all_datas = sorted(filter_bloat(pil_datas + cert_datas + sdk_datas))
all_hidden = sorted(list(set(pil_hidden + cert_hidden + sdk_hidden)))

# --- BUNDLE UV SIDECAR ---
# We package the uv binary into sys._MEIPASS/bin/uv so the PackageManager
# can use it to install dependencies in the frozen environment.
uv_path = shutil.which('uv')
if uv_path:
    all_bins.append((uv_path, 'bin'))

# 2. Aggressive Excludes (Modules Karcytics does not need to run)
# Explicitly exclude test modules and development dependencies
bloat_modules = [
    'tests',
    'pytest',
    'pytest_qt',
    'mock',
    'coverage',
    # Plugin-only analysis libraries: NOT core dependencies (see
    # pyproject.toml). Plugins bring their own complete copies in their
    # isolated .venv. If one of these ends up installed in the build
    # environment, PyInstaller's static analysis can sweep it into the
    # frozen bundle incompletely (e.g. missing bokeh's jinja templates) —
    # and because sys.modules/sys.meta_path resolution happens before
    # sys.path, a plugin's own copy can never override a core-bundled one.
    # Excluding them here guarantees the frozen core never claims the name.
    'bokeh',
    'flowkit',
    'flowutils',
    'flowio',
    'fcsparser',
]

import tomllib
with open("pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)
    
deps = pyproject.get("project", {}).get("dependencies", [])
dynamic_deps = [dep.split("=")[0].split(">")[0].split("<")[0].strip() for dep in deps]

# 3. Hidden Imports (Ensuring dynamic libraries are packed)
hidden_imports = [
    'karcytics_sdk',
    'karcytics_sdk.plugin',
    'karcytics_sdk.host',
    'karcytics.plugins',
    'matplotlib.backends.backend_qtagg',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    # --- Standard Library Guarantees for Dynamic Plugins ---
    'fileinput',
    'multiprocessing',
    'concurrent.futures',
    'ctypes',
    'ctypes.util',
    'sqlite3',
    'urllib',
    'urllib.request',
    'bz2',
    'lzma',
    'gzip',
    'zipfile',
    'tarfile',
    'xml.etree.ElementTree',
    'csv',
    'json',
    'logging.config',
] + dynamic_deps + collect_submodules('karcytics')

a = Analysis(
    ['karcytics/__main__.py'],
    pathex=[],
    binaries=all_bins,
    datas=[
        ('karcytics/themes', 'themes'),
        ('karcytics/resources/fonts', 'resources/fonts'),
        ('karcytics/ui/styles', 'karcytics/ui/styles'),
        ('karcytics/shared', 'karcytics/shared'),
        ('karcytics/plugins', 'karcytics/plugins'),
        ('karcytics/tutorials/assets', 'karcytics/tutorials/assets'),
        ('docs', 'docs'),
        (icon_file, '.'),
        ('pyproject.toml', '.')
    ] + all_datas,
    hiddenimports=hidden_imports + all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=bloat_modules,
    noarchive=False,
    optimize=1, # Strips assert statements and docstrings to save space
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Karcytics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False, # Reverted for stability; use karcytics.log for troubleshooting
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Karcytics',
)

# Protects Windows/Linux servers from trying to build Apple bundles
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Karcytics.app',
        icon=icon_file,
        bundle_identifier='com.karcytics.analysis',
    )
