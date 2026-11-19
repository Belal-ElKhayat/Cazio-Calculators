"""Generic list menu and a static text page, drawn in the dot-matrix font."""

from __future__ import annotations

from typing import Callable, List, Sequence, Tuple, Union

from games.base import GRID_W, Context, PixelGrid, Screen
from games.font import ADVANCE

Label = Union[str, Callable[[], str]]
Item = Tuple[Label, Callable[[], None]]

VISIBLE = 3  # rows under the title bar


def _label(item: Item) -> str:
    lab = item[0]
    return lab() if callable(lab) else lab


class MenuScreen(Screen):
    tick_ms = 140

    def __init__(self, ctx: Context, title: str, items: Sequence[Item]) -> None:
        super().__init__(ctx)
        self.title = title
        self.items: List[Item] = list(items)
        self.sel = 0
        self.top = 0
        self._blink = True

    def tick(self) -> None:
        self._blink = not self._blink

    def on_key(self, token: str) -> None:
        token = self.norm(token)
        if token == "up":
            self.sel = (self.sel - 1) % len(self.items)
        elif token == "down":
            self.sel = (self.sel + 1) % len(self.items)
        elif token == "ok":
            self.items[self.sel][1]()
            return
        elif token in ("back", "menu"):
            self.ctx.pop()
            return
        self._scroll()

    def _scroll(self) -> None:
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + VISIBLE:
            self.top = self.sel - VISIBLE + 1

    def render(self, g: PixelGrid) -> None:
        g.rect(0, 0, GRID_W, 7, 1)
        g.text_center(0, self.title, mode="invert")
        if self.top > 0:
            g.text(GRID_W - 6, 0, "▲", mode="invert")
        if self.top + VISIBLE < len(self.items):
            g.text(GRID_W - 6, 0, "▼", mode="invert")
        for row in range(VISIBLE):
            idx = self.top + row
            if idx >= len(self.items):
                break
            y = 9 + row * 8
            if idx == self.sel and self._blink:
                g.text(0, y, "►")
            elif idx == self.sel:
                g.text(1, y, "►")
            g.text(ADVANCE + 2, y, _label(self.items[idx])[:12])


class TextScreen(Screen):
    """Up to four lines of centred text. Any key goes back."""

    tick_ms = 500

    def __init__(self, ctx: Context, lines: Sequence[Label]) -> None:
        super().__init__(ctx)
        self.lines = list(lines)

    def on_key(self, token: str) -> None:
        if self.norm(token) in ("ok", "back", "menu", "del"):
            self.ctx.pop()

    def render(self, g: PixelGrid) -> None:
        for i, line in enumerate(self.lines[:4]):
            text = line() if callable(line) else line
            g.text_center(i * 8, text[:13])
