"""Calculator models ("skins"): colour data, JSON preset loading and the QSS builder.

Presets live in ``themes/*.json`` - drop in a new file and it shows up in the
theme menu on next launch. The *Custom* model is derived at runtime from three
user-picked colours (body, buttons, LCD backlight).

This module is Qt-free so it can be unit tested anywhere.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.config import is_hex, resource_path

CUSTOM_KEY = "custom"

# --------------------------------------------------------------------------
# Colour helpers (hex strings in, hex strings out)
# --------------------------------------------------------------------------


def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    c = lambda v: max(0, min(255, int(round(v))))  # noqa: E731
    return f"#{c(r):02x}{c(g):02x}{c(b):02x}"


def mix(a: str, b: str, t: float) -> str:
    """Linear blend: t=0 -> a, t=1 -> b."""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(*(x + (y - x) * t for x, y in zip(ra, rb)))


def shade(h: str, factor: float) -> str:
    """factor < 1 darkens towards black, factor > 1 lightens towards white."""
    if factor <= 1:
        return mix("#000000", h, max(0.0, factor))
    return mix(h, "#ffffff", min(1.0, factor - 1))


def luminance(h: str) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_dark(h: str) -> bool:
    return luminance(h) < 0.28


def contrast(bg: str, dark: str = "#10141a", light: str = "#ffffff") -> str:
    """Pick whichever of two text colours reads better on ``bg``."""
    return light if is_dark(bg) else dark


def css_color(h: str, alpha: int = 255) -> str:
    if alpha >= 255:
        return h
    r, g, b = hex_to_rgb(h)
    return f"rgba({r}, {g}, {b}, {alpha})"


# --------------------------------------------------------------------------
# Theme model
# --------------------------------------------------------------------------


@dataclass
class Theme:
    """Defaults are the *Classic Slate* palette, so partial JSON files still work."""

    key: str = "slate"
    name: str = "Classic Slate"
    description: str = ""
    short: str = "SLATE"  # <= 11 chars, shown in the LCD theme menu
    order: int = 100
    translucent: bool = False
    glow: bool = False
    glow_color: str = "#00f0ff"

    body_top: str = "#3d4658"
    body_bottom: str = "#252b38"
    body_edge: str = "#141821"
    bezel: str = "#12161d"

    lcd_bg: str = "#b7c9a4"
    lcd_ink: str = "#1c261a"
    lcd_glow: bool = False

    key_num: str = "#6e7480"
    key_num_text: str = "#ffffff"
    key_func: str = "#2b3039"
    key_func_text: str = "#f2f2f2"
    key_op: str = "#4b515d"
    key_op_text: str = "#ffffff"
    key_ctrl: str = "#343a46"
    key_ctrl_text: str = "#e6e6e6"
    key_del: str = "#b8d43c"
    key_del_text: str = "#1e2606"
    key_ac: str = "#5fa83a"
    key_ac_text: str = "#0c1a05"
    key_eq: str = "#262b34"
    key_eq_text: str = "#ffffff"

    label_shift: str = "#e5b42b"
    label_alpha: str = "#e0584c"
    label_text: str = "#d7dbe3"
    brand: str = "#e9edf5"

    # ------------------------------------------------------------------ io
    @classmethod
    def from_dict(cls, data: dict, key: Optional[str] = None) -> "Theme":
        known = {f.name: f for f in fields(cls)}
        clean: dict = {}
        for k, v in data.items():
            f = known.get(k)
            if f is None:
                continue
            if f.type in ("str", str):
                if isinstance(v, str) and (
                        k in ("key", "name", "description", "short") or is_hex(v)):
                    clean[k] = v
            elif f.type in ("bool", bool):
                clean[k] = bool(v)
            elif f.type in ("int", int):
                if isinstance(v, int):
                    clean[k] = v
        if key:
            clean["key"] = key
        return cls(**clean)

    def to_dict(self) -> dict:
        return asdict(self)

    # ------------------------------------------------------------- colours
    def kind_colors(self, kind: str) -> Tuple[str, str]:
        """(background, text) for a key kind."""
        return {
            "num": (self.key_num, self.key_num_text),
            "func": (self.key_func, self.key_func_text),
            "op": (self.key_op, self.key_op_text),
            "ctrl": (self.key_ctrl, self.key_ctrl_text),
            "del": (self.key_del, self.key_del_text),
            "ac": (self.key_ac, self.key_ac_text),
            "eq": (self.key_eq, self.key_eq_text),
            "shift": (self.key_ctrl, self.label_shift),
            "alpha": (self.key_ctrl, self.label_alpha),
        }[kind]

    def swatches(self) -> Tuple[str, str, str]:
        """Body / key / LCD colours for small previews."""
        return self.body_top, self.key_num, self.lcd_bg


KEY_KINDS = ("num", "func", "op", "ctrl", "del", "ac", "eq", "shift", "alpha")


# --------------------------------------------------------------------------
# Loading & the derived custom model
# --------------------------------------------------------------------------


def load_presets(directory: Optional[Path] = None) -> Dict[str, Theme]:
    """Read every ``*.json`` theme. Always returns at least the built-in slate."""
    directory = directory or resource_path("themes")
    presets: Dict[str, Theme] = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                presets[path.stem] = Theme.from_dict(data, key=path.stem)
    if not presets:
        presets["slate"] = Theme()
    return dict(sorted(presets.items(), key=lambda kv: (kv[1].order, kv[1].name)))


def build_custom_theme(body: str, buttons: str, lcd: str) -> Theme:
    """Derive a complete, readable theme from three colours."""
    dark_body = is_dark(body)
    return Theme(
        key=CUSTOM_KEY,
        name="Custom",
        short="CUSTOM",
        description="Your own colours",
        order=900,
        body_top=shade(body, 1.14),
        body_bottom=shade(body, 0.78),
        body_edge=shade(body, 0.45),
        bezel=shade(body, 0.4),
        lcd_bg=lcd,
        lcd_ink=contrast(lcd, dark=shade(lcd, 0.16), light=shade(lcd, 1.88)),
        lcd_glow=is_dark(lcd),
        key_num=buttons,
        key_num_text=contrast(buttons),
        key_func=shade(buttons, 0.7),
        key_func_text=contrast(shade(buttons, 0.7)),
        key_op=mix(buttons, body, 0.4),
        key_op_text=contrast(mix(buttons, body, 0.4)),
        key_ctrl=shade(buttons, 0.58),
        key_ctrl_text=contrast(shade(buttons, 0.58)),
        key_eq=shade(buttons, 0.5),
        key_eq_text=contrast(shade(buttons, 0.5)),
        label_shift="#e8b422" if dark_body else "#8a5d00",
        label_alpha="#ee5b4f" if dark_body else "#b02a20",
        label_text=contrast(body, dark="#2b3038", light="#dfe4ec"),
        brand=contrast(body, dark="#1a1f27", light="#f2f5fa"),
    )


# --------------------------------------------------------------------------
# QSS
# --------------------------------------------------------------------------

_FONT = "'Segoe UI', 'Inter', 'Helvetica Neue', 'DejaVu Sans', sans-serif"
_KEY_FONT_PX = {
    "num": 17, "func": 12, "op": 19, "ctrl": 10, "del": 13, "ac": 13,
    "eq": 19, "shift": 10, "alpha": 10,
}


def _gradient(top: str, mid: str, bottom: str) -> str:
    return (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {top}, stop:0.45 {mid}, stop:1 {bottom})"
    )


def build_qss(t: Theme) -> str:
    """Tactile key styling: gradient face, thick bottom 'lip', pressed-in state."""
    alpha = 214 if t.translucent else 255
    out = []
    for kind in KEY_KINDS:
        bg, fg = t.kind_colors(kind)
        edge = css_color(fg if t.glow else shade(bg, 0.45), alpha)
        lip = css_color(shade(fg, 0.6) if t.glow else shade(bg, 0.5), alpha)
        face = _gradient(
            css_color(shade(bg, 1.22), alpha),
            css_color(bg, alpha),
            css_color(shade(bg, 0.84), alpha),
        )
        hover = _gradient(
            css_color(shade(bg, 1.34), alpha),
            css_color(shade(bg, 1.12), alpha),
            css_color(shade(bg, 0.92), alpha),
        )
        down = _gradient(
            css_color(shade(bg, 0.78), alpha),
            css_color(shade(bg, 0.88), alpha),
            css_color(shade(bg, 0.98), alpha),
        )
        px = _KEY_FONT_PX[kind]
        sel = f'QPushButton[kind="{kind}"]'
        out.append(
            f"""
{sel} {{
    color: {fg};
    background: {face};
    border: 1px solid {edge};
    border-bottom: 3px solid {lip};
    border-radius: 7px;
    font-family: {_FONT};
    font-size: {px}px;
    font-weight: 700;
    padding: 0px;
}}
{sel}:hover {{ background: {hover}; }}
{sel}:pressed {{
    background: {down};
    border-bottom: 1px solid {lip};
    padding-top: 2px;
}}"""
        )
    # SHIFT / ALPHA light up while armed
    out.append(
        f"""
QPushButton[kind="shift"][active="true"] {{
    background: {t.label_shift}; color: #1a1400; border-color: {shade(t.label_shift, 0.6)};
}}
QPushButton[kind="alpha"][active="true"] {{
    background: {t.label_alpha}; color: #200503; border-color: {shade(t.label_alpha, 0.6)};
}}
QLabel#shiftLabel {{ color: {t.label_shift}; font: 700 9px {_FONT}; }}
QLabel#alphaLabel {{ color: {t.label_alpha}; font: 700 9px {_FONT}; }}
QLabel#plainLabel {{ color: {t.label_text}; font: 700 9px {_FONT}; }}
QToolButton#chrome {{
    background: transparent; color: {t.label_text}; border: none;
    border-radius: 9px; font: 700 12px {_FONT}; padding: 0px;
}}
QToolButton#chrome:hover {{ background: rgba(255, 255, 255, 46); }}
QToolButton#chrome:pressed {{ background: rgba(0, 0, 0, 60); }}
QToolTip {{
    background: {t.bezel}; color: {t.label_text}; border: 1px solid {t.body_edge};
    padding: 3px 6px;
}}"""
    )
    return "\n".join(out)
