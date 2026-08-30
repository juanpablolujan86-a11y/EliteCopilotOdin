# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "assets" / "odin_raven.ico"), "assets"),
        (str(root / "knowledge" / "biology" / "species.json"), "knowledge/biology"),
        (str(root / "knowledge" / "biology" / "prediction_rules.json"), "knowledge/biology"),
        (str(root / "knowledge" / "external" / "explodata" / "LICENSE.txt"), "knowledge/external/explodata"),
        (str(root / "ELEVENLABS_API_KEY.example.txt"), "."),
        (str(root / "EDSM_API_KEY.example.txt"), "."),
        (str(root / "INARA_API_KEY.example.txt"), "."),
        (str(root / "API_KEYS_README.txt"), "."),
        (str(root / "README.md"), "."),
        (str(root / "docs" / "BETA_TESTING.md"), "docs"),
    ],
    hiddenimports=["tkinter", "tkinter.ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "installer" / "runtime_pre_brokk.py")],
    excludes=["PySide6", "watchdog"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ODIN",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(root / "assets" / "odin_raven.ico"),
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ODIN",
)
