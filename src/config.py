"""Persistent user settings (``config.json``) and resource lookup helpers."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "Cazio"
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULTS: Dict[str, Any] = {
    "version": 1,
    "theme": "slate",
    "custom": {"body": "#2f3b52", "buttons": "#5c6b85", "lcd": "#b9d3a2"},
    "angle": "deg",
    "always_on_top": False,
    "window": None,
    "arcade": {
        "highscores": {},
        "pixel_art": [],
        "marquee": "HELLO CAZIO",
        "marquee_speed": 3,
    },
}


def project_root() -> Path:
    """Repository root when running from source."""
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Path to a bundled resource (works from source and from a PyInstaller exe)."""
    base = Path(getattr(sys, "_MEIPASS", project_root()))
    return base.joinpath(*parts)


def app_dir() -> Path:
    """Folder that holds the executable (frozen) or the repo root (source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def user_config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME


def _is_writable(directory: Path) -> bool:
    try:
        with tempfile.TemporaryFile(dir=directory):
            return True
    except OSError:
        return False


def default_config_path() -> Path:
    """``config.json`` next to the app when possible, else in the user profile."""
    override = os.environ.get("CAZIO_CONFIG")
    if override:
        return Path(override)
    local = app_dir()
    if _is_writable(local):
        return local / "config.json"
    return user_config_dir() / "config.json"


class Config:
    """Tiny JSON-backed settings store. Never raises on I/O problems."""

    def __init__(self, path: Optional[os.PathLike] = None) -> None:
        self.path = Path(path) if path else default_config_path()
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ------------------------------------------------------------------ io
    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self._quarantine()
            return
        if isinstance(raw, dict):
            self._merge(self.data, raw)
        self._sanitize()

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def _quarantine(self) -> None:
        """Keep a corrupted file around as ``config.json.bak`` instead of losing it."""
        try:
            os.replace(self.path, self.path.with_suffix(".json.bak"))
        except OSError:
            pass

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> None:
        for key, value in incoming.items():
            if key not in base:
                continue
            if isinstance(base[key], dict) and base[key] and isinstance(value, dict):
                Config._merge(base[key], value)
            else:
                base[key] = value

    def _sanitize(self) -> None:
        d = self.data
        custom = d.get("custom")
        defaults = DEFAULTS["custom"]
        if not isinstance(custom, dict):
            custom = {}
        d["custom"] = {
            k: (custom.get(k) if is_hex(custom.get(k)) else defaults[k]) for k in defaults
        }
        if d.get("angle") not in ("deg", "rad", "gra"):
            d["angle"] = "deg"
        if not isinstance(d.get("theme"), str):
            d["theme"] = "slate"
        arcade = d.get("arcade")
        if not isinstance(arcade, dict):
            arcade = copy.deepcopy(DEFAULTS["arcade"])
        arcade.setdefault("highscores", {})
        arcade.setdefault("pixel_art", [])
        arcade.setdefault("marquee", "HELLO CAZIO")
        arcade.setdefault("marquee_speed", 3)
        if not isinstance(arcade["highscores"], dict):
            arcade["highscores"] = {}
        d["arcade"] = arcade

    # --------------------------------------------------------- convenience
    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def set_custom(self, body: str, buttons: str, lcd: str) -> None:
        self.data["custom"] = {"body": body, "buttons": buttons, "lcd": lcd}


def is_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


def normalize_hex(value: str) -> Optional[str]:
    """Accept ``#abc``, ``abc``, ``#aabbcc`` and return ``#aabbcc`` (or None)."""
    v = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", v):
        v = "".join(c * 2 for c in v)
    if re.fullmatch(r"[0-9a-fA-F]{6}", v):
        return "#" + v.lower()
    return None
