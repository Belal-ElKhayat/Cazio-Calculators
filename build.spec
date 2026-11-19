# -*- mode: python ; coding: utf-8 -*-
# Build a single-file, windowed Cazio.exe:   pyinstaller build.spec --noconfirm --clean
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "themes"), "themes"),
    ],
    hiddenimports=[
        "src.ui_main", "src.lcd", "src.keypad", "src.settings_dialog", "src.themes",
        "src.calculator_engine", "src.arcade_games", "src.config",
        "games.base", "games.font", "games.menu", "games.snake", "games.invaders",
        "games.flappy", "games.pixel_art",
    ],
    excludes=[
        "tkinter", "unittest", "pytest", "PIL",
        "PyQt6.QtNetwork", "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtWebEngineCore",
        "PyQt6.QtSql", "PyQt6.QtMultimedia", "PyQt6.QtBluetooth", "PyQt6.QtPdf",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Cazio",
    icon=str(ROOT / "assets" / "icon.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
)
