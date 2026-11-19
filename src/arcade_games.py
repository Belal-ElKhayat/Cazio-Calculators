"""The hidden arcade: registry of LCD games/tools and the menus that launch them."""

from __future__ import annotations

from typing import Callable, List, Tuple

from games.base import Context, Screen
from games.flappy import FlappyGame
from games.invaders import InvadersGame
from games.menu import Item, MenuScreen, TextScreen
from games.pixel_art import MarqueeScreen, PixelArtScreen
from games.snake import SnakeGame

# (menu label, factory, high-score key or None)
GAMES: List[Tuple[str, Callable[[Context], Screen], str]] = [
    ("SNAKE", SnakeGame, "snake"),
    ("INVADERS", InvadersGame, "invaders"),
    ("FLAPPY PIXEL", FlappyGame, "flappy"),
    ("PIXEL ART", PixelArtScreen, ""),
    ("MARQUEE", MarqueeScreen, ""),
]


def high_score_screen(ctx: Context) -> Screen:
    lines = ["HIGH SCORES"]
    for label, _factory, key in GAMES:
        if key:
            lines.append(f"{label.split()[0][:8]} {ctx.scores.get(key)}")
    return TextScreen(ctx, lines[:4])


def build_arcade_menu(ctx: Context) -> MenuScreen:
    items: List[Item] = [
        (label, (lambda f=factory: ctx.push(f(ctx)))) for label, factory, _key in GAMES
    ]
    items.append(("HIGH SCORES", lambda: ctx.push(high_score_screen(ctx))))
    return MenuScreen(ctx, "ARCADE", items)
