"""Shared plumbing for LCD screens: pixel grid, Screen base class, navigation stack."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from games.font import ADVANCE, GLYPH_H, GLYPH_W, glyph, text_width

GRID_W = 80
GRID_H = 32

# Keypad digits double as a D-pad (numpad style): 8 up, 2 down, 4 left, 6 right, 5 = OK.
DIGIT_DIRECTIONS: Dict[str, str] = {
    "char:8": "up", "char:2": "down", "char:4": "left", "char:6": "right", "char:5": "ok",
}


class PixelGrid:
    """A monochrome frame buffer. 0 = off, 1 = on."""

    def __init__(self, w: int = GRID_W, h: int = GRID_H) -> None:
        self.w, self.h = w, h
        self.cells = bytearray(w * h)

    # -- basics
    def clear(self, value: int = 0) -> None:
        self.cells[:] = bytes([value]) * (self.w * self.h)

    def plot(self, x: int, y: int, value: int = 1) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.cells[y * self.w + x] = value

    def get(self, x: int, y: int) -> int:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[y * self.w + x]
        return 0

    def toggle(self, x: int, y: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.cells[y * self.w + x] ^= 1

    def rect(self, x: int, y: int, w: int, h: int, value: int = 1, fill: bool = True) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if fill or yy in (y, y + h - 1) or xx in (x, x + w - 1):
                    self.plot(xx, yy, value)

    def sprite(self, x: int, y: int, rows: Sequence[str], on: str = "#") -> None:
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == on:
                    self.plot(x + dx, y + dy, 1)

    def on_pixels(self):
        """Yield (x, y) of every lit pixel."""
        w = self.w
        for i, v in enumerate(self.cells):
            if v:
                yield i % w, i // w

    # -- text (5x7 dot-matrix font)
    def text(self, x: int, y: int, s: str, mode: str = "on", scale: int = 1) -> int:
        """Draw ``s``. mode: 'on' (set pixels), 'knock' (clear a box first),
        'invert' (lit box with the glyph knocked out). Returns the pixel width."""
        for i, ch in enumerate(s):
            gx = x + i * ADVANCE * scale
            if mode in ("knock", "invert"):
                self.rect(gx, y, ADVANCE * scale, (GLYPH_H + 0) * scale,
                          1 if mode == "invert" else 0)
            rows = glyph(ch)
            for ry, bits in enumerate(rows):
                for cx in range(GLYPH_W):
                    lit = (bits >> (GLYPH_W - 1 - cx)) & 1
                    if mode == "invert":
                        lit ^= 1
                    if lit:
                        self.rect(gx + cx * scale, y + ry * scale, scale, scale, 1)
        return text_width(s, scale)

    def text_center(self, y: int, s: str, mode: str = "on", scale: int = 1,
                    x0: int = 0, x1: Optional[int] = None) -> None:
        x1 = self.w if x1 is None else x1
        self.text(x0 + (x1 - x0 - text_width(s, scale)) // 2, y, s, mode, scale)

    def rows(self) -> List[str]:
        """Serialise as '#'/'.' strings (used to persist pixel art)."""
        return ["".join("#" if self.cells[y * self.w + x] else "." for x in range(self.w))
                for y in range(self.h)]

    def load_rows(self, rows: Sequence[str]) -> None:
        self.clear()
        for y, row in enumerate(rows[: self.h]):
            for x, ch in enumerate(row[: self.w]):
                if ch == "#":
                    self.cells[y * self.w + x] = 1


class Screen:
    """Something the LCD can show. Subclass and override what you need."""

    tick_ms = 50
    digit_dirs = True  # map keypad 8/2/4/6/5 to up/down/left/right/ok
    text_input = False  # True -> physical letter keys arrive as 'char:X' tokens

    def __init__(self, ctx: "Context") -> None:
        self.ctx = ctx

    def enter(self) -> None:
        """Called whenever this screen becomes the visible one."""

    def on_key(self, token: str) -> None:
        """Tokens: up/down/left/right/ok/back/del/menu or ``char:<c>``."""

    def tick(self) -> None:
        """Called every ``tick_ms`` milliseconds."""

    def render(self, grid: PixelGrid) -> None:
        """Draw the current frame into ``grid`` (already cleared)."""

    def on_mouse(self, x: int, y: int, down: bool, moved: bool) -> None:
        """Mouse on the LCD, in grid coordinates."""

    def norm(self, token: str) -> str:
        return DIGIT_DIRECTIONS.get(token, token) if self.digit_dirs else token


class HighScores:
    def __init__(self, store: dict, save: Callable[[], object]) -> None:
        self._table: dict = store.setdefault("highscores", {})
        self._save = save

    def get(self, game: str) -> int:
        try:
            return int(self._table.get(game, 0))
        except (TypeError, ValueError):
            return 0

    def submit(self, game: str, score: int) -> bool:
        """Record ``score``; True if it is a new personal best."""
        if score > self.get(game):
            self._table[game] = int(score)
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._table.clear()
        self._save()

    def all(self) -> Dict[str, int]:
        return {k: self.get(k) for k in self._table}


class Context:
    """Screen stack + persistence shared by every LCD screen.

    An empty stack means "show the calculator". ``on_change`` is called whenever the
    visible screen changes so the Qt widget can re-time and repaint itself.
    """

    def __init__(self, store: Optional[dict] = None,
                 save: Optional[Callable[[], object]] = None,
                 hooks: Optional[Dict[str, Callable]] = None) -> None:
        self.store: dict = store if store is not None else {}
        self.save: Callable[[], object] = save or (lambda: None)
        self.hooks: Dict[str, Callable] = hooks or {}
        self.scores = HighScores(self.store, self.save)
        self.stack: List[Screen] = []
        self.on_change: Callable[[], None] = lambda: None

    @property
    def current(self) -> Optional[Screen]:
        return self.stack[-1] if self.stack else None

    def push(self, screen: Screen) -> None:
        self.stack.append(screen)
        screen.enter()
        self.on_change()

    def pop(self) -> None:
        if self.stack:
            self.stack.pop()
        if self.stack:
            self.stack[-1].enter()
        self.on_change()

    def replace(self, screen: Screen) -> None:
        if self.stack:
            self.stack.pop()
        self.push(screen)

    def exit(self) -> None:
        """Back to the calculator."""
        self.stack.clear()
        self.on_change()

    def hook(self, name: str, *args):
        fn = self.hooks.get(name)
        return fn(*args) if fn else None
