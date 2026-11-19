"""Cazio entry point:  python src/main.py  [--theme KEY] [--config PATH]"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:  # allow `python src/main.py` as well as `python -m src.main`
    sys.path.insert(0, ROOT)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cazio", description="Cazio scientific calculator")
    parser.add_argument("--theme", help="start with this model (slate, atomic_purple, cyberpunk, custom)")
    parser.add_argument("--config", help="path to a config.json to use")
    args = parser.parse_args(argv)

    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from src.config import Config, resource_path
    from src.ui_main import MainWindow

    if sys.platform == "win32":  # own taskbar identity instead of python.exe's
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cazio.Calculator")
        except Exception:  # pragma: no cover
            pass

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Cazio")
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    cfg = Config(args.config)
    if args.theme:
        cfg["theme"] = args.theme
    win = MainWindow(cfg)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
