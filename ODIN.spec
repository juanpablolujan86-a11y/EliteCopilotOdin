# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "knowledge" / "biology" / "species.json"), "knowledge/biology"),
        (str(root / "knowledge" / "biology" / "prediction_rules.json"), "knowledge/biology"),
        (str(root / "knowledge" / "external" / "explodata" / "LICENSE.txt"), "knowledge/external/explodata"),
        (str(root / "ELEVENLABS_API_KEY.example.txt"), "."),
    ],
    hiddenimports=["tkinter", "tkinter.ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
