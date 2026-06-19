# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path.cwd()
datas = [
    (str(project_root / "templates"), "templates"),
    (str(project_root / "static"), "static"),
]

tesseract_runtime = project_root / "runtime" / "tesseract"
if tesseract_runtime.exists():
    datas.append((str(tesseract_runtime), "runtime/tesseract"))

hiddenimports = collect_submodules("webview")
if sys.platform == "win32":
    hiddenimports += ["tkinter", "tkinter.filedialog"]

a = Analysis(
    ["desktop_app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InvoiceRenamer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="InvoiceRenamer",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="曹姐发票改名器.app",
        icon=None,
        bundle_identifier="com.invoice-renamer.desktop",
        info_plist={
            "CFBundleDisplayName": "曹姐发票改名器",
            "NSHighResolutionCapable": "True",
        },
    )
