"""Custom-screen tools: a pixel-art sketchpad and a scrolling-text marquee."""

from __future__ import annotations

from typing import Optional

from games.base import GRID_H, GRID_W, Context, PixelGrid, Screen
from games.font import PRINTABLE, text_width

PEN_MODES = ("MOVE", "DRAW", "ERASE")


class PixelArtScreen(Screen):
    """Draw on the LCD grid.

    Keys: arrows / 2468 move the cursor, OK (5) toggles a pixel, 0 cycles
    MOVE -> DRAW -> ERASE, 1 invert, 3 save, 7 load, DEL clear, AC exit.
    The mouse also works: click or drag straight on the LCD.
    """

    tick_ms = 120

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.canvas = PixelGrid()
        self.cx, self.cy = GRID_W // 2, GRID_H // 2
        self.pen = 0
        self._blink = True
        self._toast = ""
        self._toast_ticks = 0
        self._drag_value: Optional[int] = None
        self._load(silent=True)
        self._say("0 PEN 3 SAVE")

    # ---------------------------------------------------------- helpers
    def _say(self, msg: str, ticks: int = 14) -> None:
        self._toast, self._toast_ticks = msg, ticks

    def _store_rows(self):
        return self.ctx.store.get("pixel_art")

    def save(self) -> None:
        self.ctx.store["pixel_art"] = self.canvas.rows()
        self.ctx.save()
        self._say("SAVED")

    def _load(self, silent: bool = False) -> None:
        rows = self._store_rows()
        if rows:
            self.canvas.load_rows(rows)
            if not silent:
                self._say("LOADED")
        elif not silent:
            self._say("NOTHING SAVED")

    def enter(self) -> None:
        self._blink = True

    # ------------------------------------------------------------ input
    def on_key(self, token: str) -> None:
        token = self.norm(token)
        if token in ("back", "menu"):
            self.save()
            self.ctx.pop()
            return
        if token in ("up", "down", "left", "right"):
            dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[token]
            self.cx = (self.cx + dx) % GRID_W
            self.cy = (self.cy + dy) % GRID_H
            if self.pen == 1:
                self.canvas.plot(self.cx, self.cy, 1)
            elif self.pen == 2:
                self.canvas.plot(self.cx, self.cy, 0)
        elif token == "ok":
            self.canvas.toggle(self.cx, self.cy)
        elif token == "char:0":
            self.pen = (self.pen + 1) % len(PEN_MODES)
            self._say("PEN " + PEN_MODES[self.pen])
        elif token == "char:1":
            self.canvas.cells[:] = bytes(1 - v for v in self.canvas.cells)
            self._say("INVERTED")
        elif token == "char:3":
            self.save()
        elif token == "char:7":
            self._load()
        elif token == "del":
            self.canvas.clear()
            self._say("CLEARED")

    def on_mouse(self, x: int, y: int, down: bool, moved: bool) -> None:
        if not down:
            self._drag_value = None
            return
        if not (0 <= x < GRID_W and 0 <= y < GRID_H):
            return
        self.cx, self.cy = x, y
        if self._drag_value is None:  # first touch decides draw vs erase for the drag
            self._drag_value = 0 if self.canvas.get(x, y) else 1
        self.canvas.plot(x, y, self._drag_value)

    # ------------------------------------------------------------- tick
    def tick(self) -> None:
        self._blink = not self._blink
        if self._toast_ticks:
            self._toast_ticks -= 1

    def render(self, g: PixelGrid) -> None:
        g.cells[:] = self.canvas.cells
        if self._blink:
            g.toggle(self.cx, self.cy)
        else:  # a faint crosshair so you can find the cursor on busy art
            g.plot(self.cx, self.cy, self.canvas.get(self.cx, self.cy))
        if self._toast_ticks:
            w = text_width(self._toast)
            g.rect(0, GRID_H - 9, w + 4, 9, 0)
            g.text(2, GRID_H - 8, self._toast)


class MarqueeScreen(Screen):
    """Edit a message, then watch it scroll across the LCD in big letters."""

    text_input = True
    digit_dirs = False
    MAX_LEN = 60
    SPEEDS_MS = (110, 80, 55, 38, 25)

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.text = str(ctx.store.get("marquee", "HELLO CAZIO"))[: self.MAX_LEN] or "HELLO"
        self.speed = min(4, max(0, int(ctx.store.get("marquee_speed", 3)) - 1))
        self.mode = "edit"
        self.cur = len(self.text)
        self.offset = GRID_W
        self.paused = False
        self.scale = 3
        self._blink = True
        self._toast = ""
        self._toast_ticks = 0
        self._acc = 0
        self._t = 0
        self.tick_ms = 40

    # ------------------------------------------------------------ input
    def on_key(self, token: str) -> None:
        if self.mode == "edit":
            self._edit_key(token)
        else:
            self._run_key(token)

    def _edit_key(self, token: str) -> None:
        if token in ("back", "menu"):
            self._persist()
            self.ctx.pop()
        elif token == "ok":
            self._persist()
            self.mode = "run"
            self.offset = GRID_W
            self.paused = False
        elif token == "left":
            self.cur = max(0, self.cur - 1)
        elif token == "right":
            self.cur = min(len(self.text), self.cur + 1)
        elif token in ("up", "down"):
            if self.cur >= len(self.text):
                self.text += "A"
            ch = self.text[self.cur]
            idx = PRINTABLE.find(ch.upper())
            idx = (idx + (1 if token == "up" else -1)) % len(PRINTABLE)
            self.text = self.text[: self.cur] + PRINTABLE[idx] + self.text[self.cur + 1:]
        elif token == "del":
            if self.cur > 0:
                self.text = self.text[: self.cur - 1] + self.text[self.cur:]
                self.cur -= 1
        elif token.startswith("char:") and len(token) == 6:
            ch = token[5].upper()
            if ch in PRINTABLE and len(self.text) < self.MAX_LEN:
                self.text = self.text[: self.cur] + ch + self.text[self.cur:]
                self.cur += 1

    def _run_key(self, token: str) -> None:
        if token in ("back", "menu"):
            self.mode = "edit"
        elif token == "ok":
            self.paused = not self.paused
        elif token == "up":
            self.speed = min(len(self.SPEEDS_MS) - 1, self.speed + 1)
            self._say(f"SPEED {self.speed + 1}")
        elif token == "down":
            self.speed = max(0, self.speed - 1)
            self._say(f"SPEED {self.speed + 1}")
        elif token in ("left", "right"):
            self.scale = 2 if self.scale == 3 else 3
            self._say(f"SIZE {self.scale}")

    def _persist(self) -> None:
        self.ctx.store["marquee"] = self.text
        self.ctx.store["marquee_speed"] = self.speed + 1
        self.ctx.save()

    def _say(self, msg: str) -> None:
        self._toast, self._toast_ticks = msg, 20

    # ------------------------------------------------------------- tick
    def tick(self) -> None:
        self._t += 1
        if self._t % 8 == 0:
            self._blink = not self._blink
        if self._toast_ticks:
            self._toast_ticks -= 1
        if self.mode != "run" or self.paused:
            return
        self._acc += self.tick_ms
        if self._acc >= self.SPEEDS_MS[self.speed]:
            self._acc = 0
            self.offset -= 1
            if self.offset < -text_width(self.text, self.scale):
                self.offset = GRID_W

    # ----------------------------------------------------------- render
    def render(self, g: PixelGrid) -> None:
        if self.mode == "run":
            y = (GRID_H - 7 * self.scale) // 2
            g.text(self.offset, y, self.text, scale=self.scale)
            if self._toast_ticks:
                g.rect(0, 0, text_width(self._toast) + 3, 8, 0)
                g.text(1, 0, self._toast)
            return
        g.text(0, 0, "MARQUEE TEXT", mode="invert")
        width = GRID_W // 6  # characters visible
        start = max(0, min(self.cur - width + 2, len(self.text) - width + 1))
        window = self.text[start: start + width]
        g.text(0, 12, window)
        caret_x = (self.cur - start) * 6
        if self._blink:
            g.rect(caret_x, 20, 5, 1, 1)
        g.text(0, 24, "OK=GO", mode="on")
        g.text(GRID_W - 6 * 8, 24, "AC=BACK")
