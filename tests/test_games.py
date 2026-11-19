import random

from games.base import GRID_H, GRID_W, Context, PixelGrid
from games.flappy import FlappyGame
from games.invaders import InvadersGame
from games.menu import MenuScreen
from games.pixel_art import MarqueeScreen, PixelArtScreen
from games.snake import SnakeGame
from src.arcade_games import GAMES, build_arcade_menu


def make_ctx():
    saved = []
    return Context({}, lambda: saved.append(1)), saved


def run(screen, ticks):
    g = PixelGrid()
    for _ in range(ticks):
        screen.tick()
        g.clear()
        screen.render(g)
    return g


def test_font_and_grid_text():
    g = PixelGrid()
    width = g.text(0, 0, "HI")
    assert width == 11 and sum(g.cells) > 10
    assert g.rows()[0].count("#") > 0


def test_every_screen_renders_without_error():
    ctx, _ = make_ctx()
    for _label, factory, _key in GAMES:
        run(factory(ctx), 20)
    run(build_arcade_menu(ctx), 5)


def test_snake_moves_dies_and_records_score():
    ctx, saved = make_ctx()
    game = SnakeGame(ctx, random.Random(1))
    game.on_key("ok")
    head0 = game.body[0]
    run(game, 10)
    assert game.state == "play" and game.body[0] != head0
    game.food = (game.body[0][0] + 1, game.body[0][1])
    game.step()
    assert game.score == 1 and len(game.body) == 4
    run(game, 3000)  # runs into the wall
    assert game.state == "over" and ctx.scores.get("snake") == 1 and saved


def test_snake_ignores_reverse():
    ctx, _ = make_ctx()
    game = SnakeGame(ctx, random.Random(2))
    game.on_key("ok")
    game.on_key("char:4")  # left while heading right: ignored
    assert game.queue == []
    game.on_key("char:8")  # numpad up works
    assert game.queue == ["up"]


def test_invaders_fire_and_hit():
    ctx, _ = make_ctx()
    game = InvadersGame(ctx, random.Random(3))
    game.on_key("ok")
    target = game.aliens[-1]
    game.ship_x = target.x
    game.on_key("ok")
    assert game.bullet is not None
    run(game, 40)
    assert game.score >= 10


def test_invaders_game_over_when_out_of_lives():
    ctx, _ = make_ctx()
    game = InvadersGame(ctx, random.Random(3))
    game.on_key("ok")
    game.lives = 1
    game.ship_x = 10
    game.bombs = [[12, 28]]
    game.tick()
    assert game.state == "over"


def test_flappy_falls_and_flaps():
    ctx, _ = make_ctx()
    game = FlappyGame(ctx, random.Random(4))
    game.on_key("ok")
    assert game.state == "play"
    run(game, 200)
    assert game.state == "over"


def test_pixel_art_draw_and_persist():
    ctx, saved = make_ctx()
    art = PixelArtScreen(ctx)
    art.on_key("ok")
    art.on_mouse(5, 5, True, False)
    art.on_mouse(6, 5, True, True)
    art.on_mouse(6, 5, False, False)
    art.on_key("char:3")
    rows = ctx.store["pixel_art"]
    assert len(rows) == GRID_H and len(rows[0]) == GRID_W and rows[5][5] == "#"
    again = PixelArtScreen(ctx)
    assert again.canvas.get(5, 5) == 1


def test_marquee_edit_and_scroll():
    ctx, _ = make_ctx()
    m = MarqueeScreen(ctx)
    for _ in range(len(m.text)):
        m.on_key("del")
    for ch in "HI 5":
        m.on_key("char:" + ch)
    assert m.text == "HI 5"
    m.on_key("ok")
    first = m.offset
    run(m, 30)
    assert m.offset < first


def test_menu_navigation_and_back():
    ctx, _ = make_ctx()
    hit = []
    menu = MenuScreen(ctx, "T", [("A", lambda: hit.append("a")), ("B", lambda: hit.append("b"))])
    ctx.push(menu)
    menu.on_key("down")
    menu.on_key("ok")
    assert hit == ["b"]
    menu.on_key("back")
    assert ctx.current is None
