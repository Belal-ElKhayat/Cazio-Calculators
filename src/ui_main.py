"""Main window: frameless calculator body, keypad layout, keyboard handling, menus."""

from __future__ import annotations

from collections import deque
from functools import partial
from typing import Dict, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QGuiApplication, QKeyEvent, QLinearGradient, QPainter, QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QMenu, QToolButton, QVBoxLayout, QWidget,
)

from games.base import Context, Screen
from games.menu import MenuScreen, TextScreen
from src import __version__
from src.arcade_games import build_arcade_menu
from src.calculator_engine import ANGLE_NAMES, CalcSession
from src.config import Config
from src.keypad import KEYS, DPad, KeyCell
from src.lcd import LCDWidget
from src.settings_dialog import SettingsDialog
from src.themes import CUSTOM_KEY, Theme, build_custom_theme, build_qss, load_presets, shade

SHADOW = 14
KONAMI = ["up", "up", "down", "down", "left", "right", "left", "right"]

# physical keyboard -> calculator key id (by typed character)
TEXT_KEYS: Dict[str, str] = {
    "+": "add", "-": "sub", "*": "mul", "/": "div", "^": "pow", "(": "lpar", ")": "rpar",
    ".": "dot", ",": "dot", "=": "eq", "e": "exp", "s": "sin", "c": "cos", "t": "tan",
    "l": "log", "n": "ln", "r": "sqrt", "a": "ans", "q": "sq", "i": "inv", "m": "mode",
    "h": "hyp",
}
TEXT_ATOMS: Dict[str, str] = {"p": "π", "!": "!", "%": "%", "x": "X", "E": "e"}
QT_KEYS = {
    Qt.Key.Key_Return: "eq", Qt.Key.Key_Enter: "eq", Qt.Key.Key_Backspace: "del",
    Qt.Key.Key_Delete: "ac", Qt.Key.Key_Escape: "ac", Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right", Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_F2: "shift", Qt.Key.Key_F3: "alpha",
}
# on-screen key id -> token for LCD screens (games, menus)
PIXEL_TOKENS = {
    "up": "up", "down": "down", "left": "left", "right": "right", "eq": "ok", "ac": "back",
    "del": "del", "mode": "menu", "dot": "char:.", "add": "char:+", "sub": "char:-",
    "mul": "char:*", "div": "char:/",
}


class HeaderWidget(QWidget):
    """Brand + model name on the left, decorative solar panel on the right."""

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setFixedHeight(40)

    def paintEvent(self, _e) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont("Segoe UI", 1)
        f.setPixelSize(21)
        f.setBold(True)
        f.setItalic(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(f)
        p.setPen(QColor(t.brand))
        p.drawText(QPointF(2, 22), "CAZIO")
        f2 = QFont("Segoe UI", 1)
        f2.setPixelSize(10)
        f2.setItalic(True)
        f2.setBold(True)
        p.setFont(f2)
        p.setPen(QColor(t.label_text))
        p.drawText(QPointF(3, 36), "cz-991ES PLUS  FUN-DISPLAY")
        panel = QRectF(self.width() - 112, 4, 112, 30)
        g = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        g.setColorAt(0, QColor("#3b2224"))
        g.setColorAt(1, QColor("#1b0f10"))
        p.setPen(QPen(QColor(t.body_edge), 1.2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(panel, 4, 4)
        p.setPen(QPen(QColor(255, 255, 255, 38), 1))
        for i in range(1, 5):
            x = panel.left() + i * panel.width() / 5
            p.drawLine(QPointF(x, panel.top() + 2), QPointF(x, panel.bottom() - 2))
        p.end()


class CalcBody(QWidget):
    """The calculator shell: gradient, bevel, optional translucent PCB / neon outline."""

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.theme = theme

    def paintEvent(self, _e) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        top, bot = QColor(t.body_top), QColor(t.body_bottom)
        if t.translucent:
            top.setAlpha(205)
            bot.setAlpha(225)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, top)
        g.setColorAt(1, bot)
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(t.body_edge), 2))
        p.drawRoundedRect(r, 26, 26)
        if t.translucent:  # peek at the "circuit board" inside the jelly shell
            p.setPen(QPen(QColor(255, 255, 255, 34), 1.5))
            for i in range(9):
                y = r.top() + 150 + i * 46
                p.drawLine(QPointF(r.left() + 18, y), QPointF(r.right() - 18 - (i % 3) * 40, y))
                p.drawLine(QPointF(r.left() + 30 + i * 28, y), QPointF(r.left() + 30 + i * 28, y + 24))
            p.setBrush(QColor(0, 0, 0, 40))
            p.drawRoundedRect(QRectF(r.right() - 120, r.top() + 340, 90, 60), 5, 5)
        if t.glow:
            c = QColor(t.glow_color)
            for w, a in ((7, 18), (4, 34), (2, 70)):
                c.setAlpha(a)
                p.setPen(QPen(c, w))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 25, 25)
        p.setBrush(Qt.BrushStyle.NoBrush)  # bevel highlight
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRoundedRect(r.adjusted(3, 3, -3, -3), 23, 23)
        p.end()


class MainWindow(QWidget):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.presets = load_presets()
        self.theme_key = cfg["theme"] if (cfg["theme"] in self.presets or cfg["theme"] == CUSTOM_KEY) \
            else next(iter(self.presets))
        self.theme = self.theme_for(self.theme_key)
        self.session = CalcSession(cfg["angle"])
        self.ctx = Context(cfg["arcade"], cfg.save)
        self._seq: deque = deque(maxlen=8)
        self._settings: Optional[SettingsDialog] = None

        self.setWindowTitle("Cazio")
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if cfg["always_on_top"]:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build()
        self.apply_theme(self.theme_key, persist=False)
        self._restore_position()

    # ------------------------------------------------------------- build
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW, SHADOW, SHADOW, SHADOW)
        self.body = CalcBody(self.theme, self)
        outer.addWidget(self.body)
        v = QVBoxLayout(self.body)
        v.setContentsMargins(14, 8, 14, 16)
        v.setSpacing(4)

        chrome = QHBoxLayout()
        chrome.setContentsMargins(4, 0, 4, 0)
        self.gear = self._chrome_btn("⚙", "Models & colours (F1)", self.open_settings)
        chrome.addWidget(self.gear)
        chrome.addStretch(1)
        chrome.addWidget(self._chrome_btn("–", "Minimise", self.showMinimized))
        chrome.addWidget(self._chrome_btn("✕", "Close", self.close))
        v.addLayout(chrome)

        self.header = HeaderWidget(self.theme)
        v.addWidget(self.header)
        self.lcd = LCDWidget(self.session, self.ctx, self.theme)
        v.addWidget(self.lcd, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(6)

        self.cells: Dict[str, KeyCell] = {}
        top = QGridLayout()
        top.setHorizontalSpacing(7)
        top.setVerticalSpacing(3)
        for c in range(6):
            top.setColumnStretch(c, 1)
        placements = {
            "shift": (0, 0), "alpha": (0, 1), "mode": (0, 4), "on": (0, 5),
            "calc": (1, 0), "integ": (1, 1), "inv": (1, 4), "logb": (1, 5),
        }
        for kid, (r, c) in placements.items():
            top.addWidget(self._cell(kid, 24), r, c)
        self.dpad = DPad(self.theme)
        self.dpad.pressed.connect(self.on_key)
        top.addWidget(self.dpad, 0, 2, 2, 2, Qt.AlignmentFlag.AlignCenter)
        rows = [
            ["frac", "sqrt", "sq", "pow", "log", "ln"],
            ["neg", "dms", "hyp", "sin", "cos", "tan"],
            ["rcl", "eng", "lpar", "rpar", "sd", "mplus"],
        ]
        for r, row in enumerate(rows, start=2):
            for c, kid in enumerate(row):
                top.addWidget(self._cell(kid, 26), r, c)
        v.addLayout(top)
        v.addSpacing(4)

        num = QGridLayout()
        num.setHorizontalSpacing(7)
        num.setVerticalSpacing(3)
        for c in range(5):
            num.setColumnStretch(c, 1)
        layout = [
            ["7", "8", "9", "del", "ac"],
            ["4", "5", "6", "mul", "div"],
            ["1", "2", "3", "add", "sub"],
            ["0", "dot", "exp", "ans", "eq"],
        ]
        for r, row in enumerate(layout):
            for c, kid in enumerate(row):
                num.addWidget(self._cell(kid, 36), r, c)
        v.addLayout(num)

    def _cell(self, kid: str, height: int) -> KeyCell:
        cell = KeyCell(KEYS[kid], height)
        cell.button.pressed.connect(partial(self.on_key, kid))
        self.cells[kid] = cell
        return cell

    def _chrome_btn(self, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setObjectName("chrome")
        b.setText(text)
        b.setToolTip(tip)
        b.setFixedSize(20, 20)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    # ------------------------------------------------------------ themes
    def theme_for(self, key: str) -> Theme:
        if key == CUSTOM_KEY:
            c = self.cfg["custom"]
            return build_custom_theme(c["body"], c["buttons"], c["lcd"])
        return self.presets.get(key) or next(iter(self.presets.values()))

    def apply_theme(self, key: str, persist: bool = True) -> None:
        self.theme_key = key
        self.theme = self.theme_for(key)
        self.setStyleSheet(build_qss(self.theme))
        for w in (self.body, self.header, self.dpad):
            if hasattr(w, "set_theme"):
                w.set_theme(self.theme)
            else:
                w.theme = self.theme
                w.update()
        self.lcd.set_theme(self.theme)
        self._apply_glow()
        if persist:
            self.cfg["theme"] = key
            self.cfg.save()
        if self._settings is not None:
            self._settings.sync()

    def apply_custom(self, body: str, buttons: str, lcd: str, persist: bool = True) -> None:
        self.cfg.set_custom(body, buttons, lcd)
        self.apply_theme(CUSTOM_KEY, persist=persist)
        if persist:
            self.cfg.save()

    def _apply_glow(self) -> None:
        for kid, cell in self.cells.items():
            btn = cell.button
            if self.theme.glow:
                eff = QGraphicsDropShadowEffect(btn)
                eff.setBlurRadius(13)
                eff.setOffset(0, 0)
                eff.setColor(QColor(self.theme.kind_colors(btn.spec.kind)[1]))
                btn.setGraphicsEffect(eff)
            else:
                btn.setGraphicsEffect(None)

    def set_always_on_top(self, on: bool) -> None:
        self.cfg["always_on_top"] = bool(on)
        self.cfg.save()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
        self.show()

    def open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsDialog(self)
            self._settings.finished.connect(lambda _=0: setattr(self, "_settings", None))
        self._settings.show()
        self._settings.raise_()

    # ------------------------------------------------------------- paint
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        base = QRectF(self.rect()).adjusted(SHADOW, SHADOW + 4, -SHADOW, -SHADOW + 4)
        for i in range(SHADOW):  # soft drop shadow
            p.setBrush(QColor(0, 0, 0, 7))
            p.drawRoundedRect(base.adjusted(-i, -i, i, i), 26 + i, 26 + i)
        p.end()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        for key, th in list(self.presets.items()) + [(CUSTOM_KEY, self.theme_for(CUSTOM_KEY))]:
            act = menu.addAction(th.name)
            act.setCheckable(True)
            act.setChecked(key == self.theme_key)
            act.triggered.connect(partial(self.apply_theme, key))
        menu.addSeparator()
        menu.addAction("Models && colours...", self.open_settings)
        menu.addAction("Arcade", self.open_arcade)
        menu.addSeparator()
        menu.addAction("Quit", self.close)
        menu.exec(e.globalPos())

    # --------------------------------------------------------- key input
    def on_key(self, kid: str) -> None:
        """Entry point for on-screen keys, the D-pad and the physical keyboard."""
        if not self.lcd.powered:
            if kid == "on":
                self.lcd.set_power(True)
            return
        screen = self.ctx.current
        if screen is None:
            self._press_calc(kid)
        else:
            self._press_screen(kid, screen)
        self._sync_indicators()

    def _press_calc(self, kid: str) -> None:
        self._seq.append(kid)
        seq = list(self._seq)
        if seq == KONAMI or seq[-5:] == ["1", "3", "3", "7", "eq"]:
            self._seq.clear()
            self.open_arcade()
            return
        event = self.session.press(kid)
        if event == "mode":
            self.open_mode_menu()
        elif event == "setup":
            self.open_setup_menu()
        elif event == "off":
            self.lcd.set_power(False)
        elif event == "angle":
            self.cfg["angle"] = self.session.angle
            self.cfg.save()
        self.lcd.refresh()

    def _press_screen(self, kid: str, screen: Screen) -> None:
        token = PIXEL_TOKENS.get(kid)
        if token is None and kid.isdigit():
            token = "char:" + kid
        if token:
            screen.on_key(token)
        self.lcd.update()

    def _sync_indicators(self) -> None:
        self.cells["shift"].button.set_active(self.session.shift)
        self.cells["alpha"].button.set_active(self.session.alpha)

    def _flash(self, kid: str) -> None:
        if kid in self.cells:
            self.cells[kid].button.flash()
        elif kid in ("up", "down", "left", "right"):
            self.dpad.flash(kid)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key, text = e.key(), e.text()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
            QGuiApplication.clipboard().setText(self.session.result_text)
            return
        if key == Qt.Key.Key_F1:
            self.open_settings()
            return
        screen = self.ctx.current
        if not self.lcd.powered:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
                self.on_key("on")
            return
        if screen is not None:
            token = self._screen_token(e, screen)
            if token:
                screen.on_key(token)
                if token in ("up", "down", "left", "right"):
                    self.dpad.flash(token)
                self.lcd.update()
            return
        kid = QT_KEYS.get(key)
        if kid is None and text:
            if text in TEXT_ATOMS:
                self.session.insert_atom(TEXT_ATOMS[text])
                self.lcd.refresh()
                return
            ch = text if text.isdigit() else text.lower()
            kid = ch if ch.isdigit() else TEXT_KEYS.get(ch)
        if kid:
            self._flash(kid)
            self.on_key(kid)

    @staticmethod
    def _screen_token(e: QKeyEvent, screen: Screen) -> Optional[str]:
        base = {
            Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down", Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right", Qt.Key.Key_Return: "ok", Qt.Key.Key_Enter: "ok",
            Qt.Key.Key_Escape: "back", Qt.Key.Key_Backspace: "del", Qt.Key.Key_Delete: "del",
        }
        k, t = e.key(), e.text()
        if k in base:
            return base[k]
        if k == Qt.Key.Key_Space:
            return "char: " if screen.text_input else "ok"
        if not t or not t.isprintable():
            return None
        if screen.text_input:
            return "char:" + t.upper()
        wasd = {"w": "up", "a": "left", "s": "down", "d": "right"}
        if t.lower() in wasd:
            return wasd[t.lower()]
        if t.lower() == "m":
            return "menu"
        return "char:" + t if t.isdigit() else None

    # ------------------------------------------------------------- menus
    def open_arcade(self) -> None:
        self.ctx.exit()
        self.ctx.push(build_arcade_menu(self.ctx))

    def open_mode_menu(self) -> None:
        items = [
            ("CALCULATE", self.ctx.exit),
            ("THEMES", self.open_theme_menu),
            ("ARCADE", lambda: self.ctx.push(build_arcade_menu(self.ctx))),
            ("SETUP", self.open_setup_menu),
            ("ABOUT", self.open_about),
        ]
        self.ctx.push(MenuScreen(self.ctx, "MODE", items))

    def open_theme_menu(self) -> None:
        items = []
        for key, th in list(self.presets.items()) + [(CUSTOM_KEY, self.theme_for(CUSTOM_KEY))]:
            items.append((
                (lambda k=key, s=th.short: ("*" if self.theme_key == k else " ") + s),
                partial(self.apply_theme, key),
            ))
        items.append((" EDIT COLORS", self.open_settings))
        self.ctx.push(MenuScreen(self.ctx, "THEMES", items))

    def open_setup_menu(self) -> None:
        def cycle_angle() -> None:
            self.session.cycle_angle()
            self.cfg["angle"] = self.session.angle
            self.cfg.save()

        def clear_memory() -> None:
            self.session.clear_memory()
            self.ctx.exit()

        items = [
            (lambda: "ANGLE: " + ANGLE_NAMES[self.session.angle], cycle_angle),
            ("CLEAR MEMORY", clear_memory),
            ("CLEAR SCORES", self.ctx.scores.clear),
        ]
        self.ctx.push(MenuScreen(self.ctx, "SETUP", items))

    def open_about(self) -> None:
        self.ctx.push(TextScreen(self.ctx, ["CAZIO", f"VERSION {__version__}", "MADE W/ PYQT6", "ANY KEY=BACK"]))

    # ------------------------------------------------------------ window
    def _restore_position(self) -> None:
        pos = self.cfg["window"]
        self.adjustSize()
        if isinstance(pos, dict) and "x" in pos and "y" in pos:
            screen = QGuiApplication.screenAt(self.mapToGlobal(self.rect().center()))
            geo = QGuiApplication.primaryScreen().availableGeometry()
            x, y = int(pos["x"]), int(pos["y"])
            if geo.left() - 50 <= x <= geo.right() - 100 and geo.top() - 10 <= y <= geo.bottom() - 100:
                self.move(x, y)
            del screen

    def closeEvent(self, e) -> None:
        self.cfg["window"] = {"x": self.x(), "y": self.y()}
        self.cfg["angle"] = self.session.angle
        self.cfg.save()
        super().closeEvent(e)
