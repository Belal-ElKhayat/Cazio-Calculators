"""Snake. 28x16 playfield of 2x2-pixel cells, HUD on the right."""

from __future__ import annotations

import random
from collections import deque
from typing import Deque, Optional, Tuple

from games.base import Context, PixelGrid, Screen

COLS, ROWS, CELL = 28, 16, 2
FIELD_W = COLS * CELL  # 56 px
HUD_X = FIELD_W + 3

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


class SnakeGame(Screen):
    tick_ms = 30
    GAME = "snake"

    def __init__(self, ctx: Context, rng: Optional[random.Random] = None) -> None:
        super().__init__(ctx)
        self.rng = rng or random.Random()
        self.reset()

    # ------------------------------------------------------------- state
    def reset(self) -> None:
        mid = (COLS // 2, ROWS // 2)
        self.body: Deque[Tuple[int, int]] = deque([(mid[0] - i, mid[1]) for i in range(3)])
        self.direction = "right"
        self.queue: list = []
        self.score = 0
        self.state = "ready"  # ready | play | over
        self.new_best = False
        self._acc = 0
        self._blink = 0
        self.food = self._spawn_food()

    @property
    def step_ms(self) -> int:
        return max(60, 150 - self.score * 4)

    def _spawn_food(self) -> Tuple[int, int]:
        free = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in self.body]
        return self.rng.choice(free) if free else (-1, -1)

    # ------------------------------------------------------------- input
    def on_key(self, token: str) -> None:
        token = self.norm(token)
        if token in ("back", "menu"):
            self.ctx.pop()
            return
        if self.state in ("ready", "over"):
            if token == "ok":
                self.reset()
                self.state = "play"
            return
        if token in DIRS:
            last = self.queue[-1] if self.queue else self.direction
            if token != last and token != OPPOSITE[last] and len(self.queue) < 2:
                self.queue.append(token)

    # -------------------------------------------------------------- tick
    def tick(self) -> None:
        self._blink = (self._blink + 1) % 16
        if self.state != "play":
            return
        self._acc += self.tick_ms
        if self._acc >= self.step_ms:
            self._acc = 0
            self.step()

    def step(self) -> None:
        if self.queue:
            self.direction = self.queue.pop(0)
        dx, dy = DIRS[self.direction]
        hx, hy = self.body[0]
        head = (hx + dx, hy + dy)
        eating = head == self.food
        tail = self.body[-1]
        blocked = set(self.body) - ({tail} if not eating else set())
        if not (0 <= head[0] < COLS and 0 <= head[1] < ROWS) or head in blocked:
            self._game_over()
            return
        self.body.appendleft(head)
        if eating:
            self.score += 1
            self.food = self._spawn_food()
            if self.food == (-1, -1):  # board full - you win
                self._game_over()
        else:
            self.body.pop()

    def _game_over(self) -> None:
        self.state = "over"
        self.new_best = self.ctx.scores.submit(self.GAME, self.score)

    # ------------------------------------------------------------ render
    def render(self, g: PixelGrid) -> None:
        for x, y in self.body:
            g.rect(x * CELL, y * CELL, CELL, CELL, 1)
        if self.food != (-1, -1) and (self._blink < 10 or self.state != "play"):
            fx, fy = self.food
            g.plot(fx * CELL, fy * CELL)
            g.plot(fx * CELL + 1, fy * CELL + 1)
        for y in range(0, g.h, 2):  # dotted divider
            g.plot(FIELD_W + 1, y)
        hi = max(self.ctx.scores.get(self.GAME), self.score)
        g.text(HUD_X, 0, "SC")
        g.text(HUD_X, 8, str(self.score))
        g.text(HUD_X, 17, "HI")
        g.text(HUD_X, 25, str(hi))
        if self.state == "ready":
            self._banner(g, "SNAKE", "OK=START", "")
        elif self.state == "over":
            self._banner(g, "GAME OVER", f"SC {self.score}",
                         "NEW BEST!" if self.new_best else "OK=AGAIN")

    @staticmethod
    def _banner(g: PixelGrid, l1: str, l2: str, l3: str) -> None:
        g.rect(0, 3, FIELD_W, 26, 0)
        g.rect(0, 3, FIELD_W, 26, 1, fill=False)
        g.text_center(6, l1, x1=FIELD_W)
        g.text_center(15, l2, x1=FIELD_W)
        if l3:
            g.text_center(22, l3, x1=FIELD_W)
