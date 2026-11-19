"""Flappy Pixel. Any key (OK / up recommended) flaps."""

from __future__ import annotations

import random
from typing import List, Optional

from games.base import GRID_H, GRID_W, Context, PixelGrid, Screen

BIRD_X = 16
BIRD = ("#.#", "###", ".#.")
BIRD_SIZE = 3
PIPE_W = 5
GAP = 11
SPACING = 30
GRAVITY = 0.30
FLAP_V = -2.1
MAX_FALL = 3.2


class FlappyGame(Screen):
    tick_ms = 40
    GAME = "flappy"

    def __init__(self, ctx: Context, rng: Optional[random.Random] = None) -> None:
        super().__init__(ctx)
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.y = 14.0
        self.vy = 0.0
        self.score = 0
        self.state = "ready"  # ready | play | over
        self.new_best = False
        self.pipes: List[List[float]] = []  # [x, gap_top, passed]
        self._t = 0
        self._since_pipe = SPACING  # spawn the first pipe quickly

    # ------------------------------------------------------------- input
    def on_key(self, token: str) -> None:
        token = self.norm(token)
        if token in ("back", "menu"):
            self.ctx.pop()
            return
        if self.state == "ready":
            if token in ("ok", "up"):
                self.reset()
                self.state = "play"
                self.vy = FLAP_V
            return
        if self.state == "over":
            if token == "ok":
                self.reset()
            return
        if token in ("ok", "up", "left", "right"):
            self.vy = FLAP_V

    # -------------------------------------------------------------- tick
    def tick(self) -> None:
        self._t += 1
        if self.state == "ready":
            self.y = 14 + (1 if (self._t // 6) % 2 else 0)
            return
        if self.state != "play":
            return
        self.vy = min(MAX_FALL, self.vy + GRAVITY)
        self.y += self.vy
        for p in self.pipes:
            p[0] -= 1
        self.pipes = [p for p in self.pipes if p[0] + PIPE_W > 0]
        self._since_pipe += 1
        if self._since_pipe >= SPACING:
            self._since_pipe = 0
            self.pipes.append([GRID_W, float(self.rng.randint(3, GRID_H - GAP - 3)), 0])
        for p in self.pipes:
            if not p[2] and p[0] + PIPE_W < BIRD_X:
                p[2] = 1
                self.score += 1
        if self._collides():
            self.state = "over"
            self.new_best = self.ctx.scores.submit(self.GAME, self.score)

    def _collides(self) -> bool:
        top = int(round(self.y))
        if top < 0 or top + BIRD_SIZE > GRID_H:
            return True
        for x, gap_top, _ in self.pipes:
            if x < BIRD_X + BIRD_SIZE and x + PIPE_W > BIRD_X:
                if top < gap_top or top + BIRD_SIZE > gap_top + GAP:
                    return True
        return False

    # ------------------------------------------------------------ render
    def render(self, g: PixelGrid) -> None:
        for x, gap_top, _ in self.pipes:
            px, gt = int(x), int(gap_top)
            g.rect(px, 0, PIPE_W, gt, 1)
            g.rect(px - 1, gt - 2, PIPE_W + 2, 2, 1)  # cap
            g.rect(px, gt + GAP, PIPE_W, GRID_H - gt - GAP, 1)
            g.rect(px - 1, gt + GAP, PIPE_W + 2, 2, 1)
            g.rect(px + 1, 0, 1, max(0, gt - 2), 0)  # highlight stripe
            g.rect(px + 1, gt + GAP + 2, 1, max(0, GRID_H - gt - GAP - 2), 0)
        g.sprite(BIRD_X, int(round(self.y)), BIRD)
        if self.state == "play":
            g.text(GRID_W // 2 - 6, 0, str(self.score), mode="knock")
        elif self.state == "ready":
            g.rect(14, 3, 52, 9, 0)
            g.text_center(4, "FLAPPY")
            g.rect(18, 23, 44, 8, 0)
            g.text_center(24, "OK=FLAP")
        else:
            g.rect(12, 6, 56, 21, 0)
            g.rect(12, 6, 56, 21, 1, fill=False)
            g.text_center(9, "GAME OVER")
            g.text_center(18, "NEW BEST!" if self.new_best else f"SC {self.score}")
