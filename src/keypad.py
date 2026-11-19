"""Keypad widgets: tactile keys with SHIFT/ALPHA legends, and the round D-pad."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.themes import Theme, shade


@dataclass(frozen=True)
class KeySpec:
    id: str
    text: str
    kind: str  # num | func | op | ctrl | del | ac | eq | shift | alpha
    shift: str = ""  # gold legend (SHIFT + key)
    alpha: str = ""  # red legend  (ALPHA + key)


def _k(id_: str, text: str, kind: str, shift: str = "", alpha: str = "") -> KeySpec:
    return KeySpec(id_, text, kind, shift, alpha)


KEYS: Dict[str, KeySpec] = {s.id: s for s in [
    _k("shift", "SHIFT", "shift"), _k("alpha", "ALPHA", "alpha"),
    _k("mode", "MODE", "ctrl", "SETUP"), _k("on", "ON", "ctrl"),
    _k("calc", "CALC", "func"), _k("integ", "∫dx", "func", "d/dx"),
    _k("inv", "x⁻¹", "func", "x!"), _k("logb", "log□", "func"),
    _k("frac", "a/b", "func", "Abs"), _k("sqrt", "√", "func", "∛"),
    _k("sq", "x²", "func", "x³"), _k("pow", "x^y", "func", "ˣ√"),
    _k("log", "log", "func", "10ˣ"), _k("ln", "ln", "func", "eˣ"),
    _k("neg", "(−)", "func", "", "A"), _k("dms", "°′″", "func", "", "B"),
    _k("hyp", "hyp", "func", "", "C"), _k("sin", "sin", "func", "sin⁻¹", "D"),
    _k("cos", "cos", "func", "cos⁻¹", "E"), _k("tan", "tan", "func", "tan⁻¹", "F"),
    _k("rcl", "RCL", "func", "STO"), _k("eng", "ENG", "func"),
    _k("lpar", "(", "func"), _k("rpar", ")", "func", ",", "X"),
    _k("sd", "S⇔D", "func", "", "Y"), _k("mplus", "M+", "func", "M−", "M"),
    _k("7", "7", "num"), _k("8", "8", "num"), _k("9", "9", "num", "CLR"),
    _k("del", "DEL", "del"), _k("ac", "AC", "ac", "OFF"),
    _k("4", "4", "num"), _k("5", "5", "num"), _k("6", "6", "num"),
    _k("mul", "×", "op", "nPr"), _k("div", "÷", "op", "nCr"),
    _k("1", "1", "num"), _k("2", "2", "num"), _k("3", "3", "num"),
    _k("add", "+", "op"), _k("sub", "−", "op"),
    _k("0", "0", "num"), _k("dot", "•", "num", "Ran#"),
    _k("exp", "×10ˣ", "num", "π", "e"), _k("ans", "Ans", "num", "DRG▸"),
    _k("eq", "=", "eq"),
]}


class KeyButton(QPushButton):
    """A key. The look comes entirely from the theme's QSS via the ``kind`` property."""

    def __init__(self, spec: KeySpec, height: int, parent=None) -> None:
        super().__init__(spec.text, parent)
        self.spec = spec
        self.setProperty("kind", spec.kind)
        self.setProperty("active", False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keystrokes belong to the window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(height)
        if spec.id == "del":
            self.setAutoRepeat(True)
            self.setAutoRepeatDelay(400)
            self.setAutoRepeatInterval(70)

    def flash(self) -> None:
        """Visual feedback for physical-keyboard presses."""
        self.setDown(True)
        QTimer.singleShot(90, lambda: self.setDown(False))

    def set_active(self, on: bool) -> None:
        if bool(self.property("active")) != on:
            self.setProperty("active", on)
            self.style().unpolish(self)
            self.style().polish(self)


class KeyCell(QWidget):
    """A key with its SHIFT (gold, left) and ALPHA (red, right) legends above it."""

    def __init__(self, spec: KeySpec, height: int, parent=None) -> None:
        super().__init__(parent)
        self.button = KeyButton(spec, height, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(1)
        legends = QHBoxLayout()
        legends.setContentsMargins(2, 0, 2, 0)
        legends.setSpacing(0)
        shift_lbl, alpha_lbl = QLabel(spec.shift), QLabel(spec.alpha)
        shift_lbl.setObjectName("shiftLabel")
        alpha_lbl.setObjectName("alphaLabel")
        for lbl in (shift_lbl, alpha_lbl):
            lbl.setFixedHeight(11)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        legends.addWidget(shift_lbl)
        legends.addStretch(1)
        legends.addWidget(alpha_lbl)
        outer.addLayout(legends)
        outer.addWidget(self.button)


class DPad(QWidget):
    """Round 4-way pad (the REPLAY key on a real Casio). Emits 'up'/'down'/'left'/'right'."""

    pressed = pyqtSignal(str)

    # Qt arc angles are counter-clockwise from 3 o'clock, in degrees.
    _START = {"right": -45, "up": 45, "left": 135, "down": 225}

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setFixedSize(94, 80)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._down = ""
        self._hover = ""
        self._repeat = QTimer(self)
        self._repeat.setInterval(80)
        self._repeat.timeout.connect(self._fire)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(380)
        self._delay.timeout.connect(self._repeat.start)

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.update()

    def flash(self, direction: str) -> None:
        self._down = direction
        self.update()
        QTimer.singleShot(90, self._clear_flash)

    def _clear_flash(self) -> None:
        if not self._delay.isActive() and not self._repeat.isActive():
            self._down = ""
            self.update()

    # -- geometry
    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _radius(self) -> float:
        return min(self.width(), self.height()) / 2 - 2

    def _hit(self, pos: QPointF) -> str:
        c = self._center()
        dx, dy = pos.x() - c.x(), pos.y() - c.y()
        r = math.hypot(dx, dy)
        if r > self._radius() or r < self._radius() * 0.30:
            return ""
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"

    # -- mouse
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        d = self._hit(e.position())
        if d:
            self._down = d
            self.pressed.emit(d)
            self._delay.start()
            self.update()

    def mouseReleaseEvent(self, _e: QMouseEvent) -> None:
        self._delay.stop()
        self._repeat.stop()
        self._down = ""
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        h = self._hit(e.position())
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, _e) -> None:
        self._hover = ""
        self.update()

    def _fire(self) -> None:
        if self._down:
            self.pressed.emit(self._down)

    # -- paint
    def paintEvent(self, _event) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, r = self._center(), self._radius()
        bg = t.key_ctrl
        rim = QColor(shade(t.key_ctrl_text if t.glow else bg, 0.5 if not t.glow else 0.9))

        # drop shadow lip
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawEllipse(QPointF(c.x(), c.y() + 2.5), r, r)
        face = QRadialGradient(QPointF(c.x(), c.y() - r * 0.35), r * 1.5)
        face.setColorAt(0.0, QColor(shade(bg, 1.3)))
        face.setColorAt(1.0, QColor(shade(bg, 0.72)))
        p.setBrush(QBrush(face))
        p.setPen(QPen(rim, 1.2))
        p.drawEllipse(c, r, r)

        for name in ("up", "down", "left", "right"):
            if name == self._down or name == self._hover:
                path = QPainterPath()
                path.moveTo(c)
                path.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), self._START[name], 90)
                path.closeSubpath()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 70 if name == self._down else 26))
                p.drawPath(path)

        # arrows
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.key_ctrl_text))
        w = r * 0.15
        tip, base = r * 0.84, r * 0.58
        shapes = {
            "up": [(0, -tip), (-w * 1.4, -base), (w * 1.4, -base)],
            "down": [(0, tip), (-w * 1.4, base), (w * 1.4, base)],
            "left": [(-tip, 0), (-base, -w * 1.4), (-base, w * 1.4)],
            "right": [(tip, 0), (base, -w * 1.4), (base, w * 1.4)],
        }
        for pts in shapes.values():
            p.drawPolygon(QPolygonF([QPointF(c.x() + x, c.y() + y) for x, y in pts]))

        # centre cap
        cap = QRadialGradient(QPointF(c.x(), c.y() - r * 0.1), r * 0.4)
        cap.setColorAt(0.0, QColor(shade(bg, 1.15)))
        cap.setColorAt(1.0, QColor(shade(bg, 0.65)))
        p.setBrush(QBrush(cap))
        p.setPen(QPen(rim, 1))
        p.drawEllipse(c, r * 0.28, r * 0.28)
        p.end()
