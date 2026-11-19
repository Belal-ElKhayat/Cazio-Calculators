"""Space Invaders for an 80x32 LCD.

Controls: left/right (4/6) move, OK (5) or up (8) fires.
"""

from __future__ import annotations

import random
from typing import List, Optional

from games.base import GRID_H, GRID_W, Context, PixelGrid, Screen

ALIEN_FRAMES = (
    ("..#..", ".###.", "##.##", "#.#.#"),
    ("..#..", ".###.", "##.##", ".#.#."),
)
ALIEN_W, ALIEN_H = 5, 4
SHIP_W, SHIP_H = 5, 3
SHIP_SPRITE = ("..#..", ".###.", "#####")
COLS, ROWS = 6, 3
GAP_X, GAP_Y = 8, 5
FORMATION_Y = 9
SHIP_Y = GRID_H - SHIP_H
DEATH_LINE = SHIP_Y - 1  # aliens touching this row end the game


class Alien:
    __slots__ = ("x", "y", "alive")

    def __init__(self, x: int, y: int) -> None:
        self.x, self.y, self.alive = x, y, True


class InvadersGame(Screen):
    tick_ms = 40
    GAME = "invaders"

    def __init__(self, ctx: Context, rng: Optional[random.Random] = None) -> None:
        super().__init__(ctx)
        self.rng = rng or random.Random()
        self.reset()

    # ------------------------------------------------------------- state
    def reset(self) -> None:
        self.score = 0
        self.lives = 3
        self.level = 1
        self.state = "ready"  # ready | play | over
        self.new_best = False
        self.ship_x = (GRID_W - SHIP_W) // 2
        self.bullet: Optional[List[int]] = None  # [x, y]
        self.bombs: List[List[int]] = []
        self.invuln = 0
        self.frame = 0
        self._acc = 0
        self._wave()

    def _wave(self) -> None:
        self.aliens = [
            Alien(6 + c * GAP_X, FORMATION_Y + r * GAP_Y) for r in range(ROWS) for c in range(COLS)
        ]
        self.dir = 1
        self.bullet = None
        self.bombs = []
        self._acc = 0

    def alive(self) -> List[Alien]:
        return [a for a in self.aliens if a.alive]

    @property
    def step_ms(self) -> int:
        n = len(self.alive())
        return max(50, 150 + n * 9 - (self.level - 1) * 25)

    # ------------------------------------------------------------- input
    def on_key(self, token: str) -> None:
        token = self.norm(token)
        if token in ("back", "menu"):
            self.ctx.pop()
            return
        if self.state != "play":
            if token == "ok":
                self.reset()
                self.state = "play"
            return
        if token == "left":
            self.ship_x = max(0, self.ship_x - 3)
        elif token == "right":
            self.ship_x = min(GRID_W - SHIP_W, self.ship_x + 3)
        elif token in ("ok", "up") and self.bullet is None:
            self.bullet = [self.ship_x + SHIP_W // 2, SHIP_Y - 2]

    # -------------------------------------------------------------- tick
    def tick(self) -> None:
        if self.state != "play":
            return
        if self.invuln:
            self.invuln -= 1
        self._move_bullet()
        self._move_bombs()
        self._acc += self.tick_ms
        if self._acc >= self.step_ms:
            self._acc = 0
            self._step_aliens()
        if self.state == "play" and not self.alive():
            self.level += 1
            self.score += 50
            self._wave()

    def _move_bullet(self) -> None:
        if not self.bullet:
            return
        self.bullet[1] -= 2
        bx, by = self.bullet
        if by < 0:
            self.bullet = None
            return
        for a in self.alive():
            if a.x <= bx < a.x + ALIEN_W and a.y <= by + 1 and by < a.y + ALIEN_H:
                a.alive = False
                self.score += 10
                self.bullet = None
                return

    def _move_bombs(self) -> None:
        kept = []
        for b in self.bombs:
            b[1] += 1
            if b[1] >= GRID_H:
                continue
            if (not self.invuln and SHIP_Y <= b[1] + 1 and b[1] < SHIP_Y + SHIP_H
                    and self.ship_x <= b[0] < self.ship_x + SHIP_W):
                self._hit()
                continue
            kept.append(b)
        self.bombs = kept

    def _hit(self) -> None:
        self.lives -= 1
        self.invuln = 30
        if self.lives <= 0:
            self._game_over()

    def _step_aliens(self) -> None:
        self.frame ^= 1
        live = self.alive()
        if not live:
            return
        left = min(a.x for a in live)
        right = max(a.x + ALIEN_W for a in live)
        if (self.dir > 0 and right + 2 > GRID_W) or (self.dir < 0 and left - 2 < 0):
            self.dir *= -1
            for a in live:
                a.y += 2
        else:
            for a in live:
                a.x += 2 * self.dir
        if max(a.y + ALIEN_H for a in live) >= DEATH_LINE:
            self._game_over()
            return
        # drop a bomb from a random bottom-most alien
        if len(self.bombs) < 2 + self.level and self.rng.random() < 0.5:
            columns = {}
            for a in live:
                if a.x not in columns or a.y > columns[a.x].y:
                    columns[a.x] = a
            shooter = self.rng.choice(list(columns.values()))
            self.bombs.append([shooter.x + ALIEN_W // 2, shooter.y + ALIEN_H])

    def _game_over(self) -> None:
        self.state = "over"
        self.new_best = self.ctx.scores.submit(self.GAME, self.score)

    # ------------------------------------------------------------ render
    def render(self, g: PixelGrid) -> None:
        for a in self.alive():
            g.sprite(a.x, a.y, ALIEN_FRAMES[self.frame])
        if not (self.invuln and (self.invuln // 3) % 2):
            g.sprite(self.ship_x, SHIP_Y, SHIP_SPRITE)
        if self.bullet:
            g.plot(self.bullet[0], self.bullet[1])
            g.plot(self.bullet[0], self.bullet[1] + 1)
        for bx, by in self.bombs:
            g.plot(bx, by)
            g.plot(bx, by + 1)
        g.text(0, 0, f"{self.score:04d}")
        for i in range(max(0, self.lives)):
            g.text(GRID_W - 6 * (i + 1), 0, "♥")
        if self.state == "ready":
            g.rect(8, 8, GRID_W - 16, 17, 0)
            g.rect(8, 8, GRID_W - 16, 17, 1, fill=False)
            g.text_center(11, "INVADERS")
            g.text_center(18, "OK=START")
        elif self.state == "over":
            g.rect(8, 6, GRID_W - 16, 22, 0)
            g.rect(8, 6, GRID_W - 16, 22, 1, fill=False)
            g.text_center(9, "GAME OVER")
            g.text_center(17, "NEW BEST!" if self.new_best else f"SC {self.score}")
