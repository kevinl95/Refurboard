# PyInstaller spec for Refurboard
from __future__ import annotations

from pathlib import Path
import platform
import inspect

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

block_cipher = None

spec_path = Path(inspect.stack()[0].filename).resolve()
root = spec_path.parent
assets_dir = root / "assets"

# Bundle logo assets if present
_datas = []
for fname in ("logo.png", "logo.ico", "logo.icns"):
    fp = assets_dir / fname
    if fp.exists():
        _datas.append((str(fp), "assets"))

# OpenCV shared libraries
_binaries = collect_dynamic_libs("cv2")

_hidden = []
# Ensure pyobjc modules are discovered on macOS (Quartz for cursor, AppKit for Dock hiding)
if platform.system() == "Darwin":
    _hidden += collect_submodules("Quartz")
    _hidden += collect_submodules("AppKit")
    _hidden += collect_submodules("pyobjc")

# Carry package metadata for license/readme propagation
_datas += copy_metadata("refurboard")

# Choose icon based on platform
if platform.system() == "Darwin":
    _icon = assets_dir / "logo.icns"
else:
    _icon = assets_dir / "logo.ico"
_icon = str(_icon) if _icon.exists() else None

a = Analysis(
    ['src/refurboard_py/__main__.py'],
    pathex=[str(root)],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Suppress console window on Windows and macOS (keep for Linux for debugging)
_console = platform.system() == "Linux"

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='refurboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=_console,
    icon=_icon,
)

# Create macOS app bundle for proper GUI integration
if platform.system() == "Darwin":
    app = BUNDLE(
        exe,
        name='Refurboard.app',
        icon=_icon,
        bundle_identifier='com.refurboard.app',
        info_plist={
            'CFBundleName': 'Refurboard',
            'CFBundleDisplayName': 'Refurboard',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSCameraUsageDescription': 'Refurboard needs camera access to track the IR pen.',
            'NSAccessibilityUsageDescription': 'Refurboard needs accessibility access to control the cursor.',
            'LSMinimumSystemVersion': '10.13.0',
            'LSEnvironment': {
                'OBJC_DISABLE_INITIALIZE_FORK_SAFETY': 'YES',
            },
        },
    )
