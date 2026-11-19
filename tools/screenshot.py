"""Render a PNG of every model into docs/screenshots/  (needs PyQt6):  python tools/screenshot.py"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    from src.config import Config
    from src.ui_main import MainWindow

    app = QApplication([])
    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    win = MainWindow(cfg)
    win.show()
    for key in ("1", "2", "sin", "3", "0", "rpar", "add", "5", "eq"):
        win.on_key(key)
    for theme in list(win.presets) + ["custom"]:
        win.apply_theme(theme, persist=False)
        app.processEvents()
        win.grab().save(str(out / f"{theme}.png"))
        print("saved", out / f"{theme}.png")
    os._exit(0)


if __name__ == "__main__":
    main()
