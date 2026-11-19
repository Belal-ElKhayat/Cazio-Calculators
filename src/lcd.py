"""The LCD widget: draws the calculator display and any arcade/menu screen."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from games.base import GRID_H, GRID_W, Context, PixelGrid
from src.calculator_engine import CalcSession
from src.themes import Theme

CELL = 3.5
BEZEL = 6
LCD_W = int(GRID_W * CELL + BEZEL * 2)  # 292
LCD_H = int(GRID_H * CELL + BEZEL * 2)  # 124

MONO_FAMILIES = ["Consolas", "DejaVu Sans Mono", "Menlo", "Liberation Mono", "Courier New"]

ALIGN_L = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
ALIGN_R = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _font(px: int, bold: bool = True) -> QFont:
    f = QFont()
    f.setFamilies(MONO_FAMILIES)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


class LCDWidget(QWidget):
    """Shows the calculator when the screen stack is empty, otherwise the top screen."""

    def __init__(self, session: CalcSession, ctx: Context, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.ctx = ctx
        self.theme = theme
        self.powered = True
        self.grid = PixelGrid()
        self._blink = True
        self._scroll = 0.0
        self._ghost: Optional[QPixmap] = None
        self._ghost_key = None
        self._texture_pm: Optional[QPixmap] = None
        self._texture_key = None

        self.setFixedSize(LCD_W, LCD_H)
        self.setMouseTracking(False)

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._on_frame)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(530)
        self._blink_timer.timeout.connect(self._on_blink)
        self._blink_timer.start()
        ctx.on_change = self.sync

    # ------------------------------------------------------------ control
    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._ghost_key = self._texture_key = None
        self.update()

    def set_power(self, on: bool) -> None:
        self.powered = on
        self.sync()

    def refresh(self) -> None:
        self._blink = True
        self._blink_timer.start()
        self.update()

    def sync(self) -> None:
        """Re-time and repaint after the visible screen changed."""
        screen = self.ctx.current
        if screen is not None and self.powered:
            self._frame_timer.start(max(10, int(screen.tick_ms)))
        else:
            self._frame_timer.stop()
        self._scroll = 0.0
        self.update()

    def _on_frame(self) -> None:
        screen = self.ctx.current
        if screen is not None:
            screen.tick()
        self.update()

    def _on_blink(self) -> None:
        self._blink = not self._blink
        if self.ctx.current is None and self.powered:
            self.update()

    # -------------------------------------------------------------- mouse
    def _grid_pos(self, pos: QPointF):
        gx = int((pos.x() - BEZEL) / CELL)
        gy = int((pos.y() - BEZEL) / CELL)
        return gx, gy

    def _send_mouse(self, e: QMouseEvent, down: bool, moved: bool) -> None:
        screen = self.ctx.current
        if screen is None or not self.powered:
            e.ignore()
            return
        gx, gy = self._grid_pos(e.position())
        screen.on_mouse(gx, gy, down, moved)
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.ctx.current is not None:
            self._send_mouse(e, True, False)
        else:
            e.ignore()  # let the window handle dragging

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if e.buttons() & Qt.MouseButton.LeftButton and self.ctx.current is not None:
            self._send_mouse(e, True, True)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self.ctx.current is not None:
            self._send_mouse(e, False, False)

    # -------------------------------------------------------------- paint
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.theme

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(t.body_edge), 1))
        p.setBrush(QColor(t.bezel))
        p.drawRoundedRect(outer, 9, 9)

        inner = QRectF(BEZEL, BEZEL, self.width() - 2 * BEZEL, self.height() - 2 * BEZEL)
        bg = QColor(t.lcd_bg)
        grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        grad.setColorAt(0.0, bg.lighter(108))
        grad.setColorAt(1.0, bg.darker(108))
        clip = QPainterPath()
        clip.addRoundedRect(inner, 4, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(clip)

        p.save()
        p.setClipPath(clip)
        if self.powered:
            if self.ctx.current is None:
                self._paint_calc(p, inner)
            else:
                self._paint_pixels(p, inner)
        else:
            p.fillRect(inner, QColor(0, 0, 0, 38))
        # glass glare + inner shadow
        glare = QLinearGradient(inner.topLeft(), QPointF(inner.left(), inner.top() + inner.height() * 0.55))
        glare.setColorAt(0.0, QColor(255, 255, 255, 14 if t.lcd_glow else 38))
        glare.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(inner, QBrush(glare))
        p.setPen(QPen(QColor(0, 0, 0, 80), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(clip)
        p.restore()
        p.end()

    # ---- calculator face
    def _texture(self) -> QPixmap:
        key = (self.theme.lcd_ink,)
        if self._texture_pm is None or self._texture_key != key:
            pm = QPixmap(3, 3)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            c = QColor(self.theme.lcd_ink)
            c.setAlpha(20)
            q.fillRect(0, 0, 2, 2, c)
            q.end()
            self._texture_pm, self._texture_key = pm, key
        return self._texture_pm

    def _text(self, p: QPainter, rect: QRectF, flags, text: str, ink: QColor) -> None:
        if self.theme.lcd_glow:
            glow = QColor(ink)
            glow.setAlpha(55)
            p.setPen(glow)
            for dx, dy in ((-1.2, 0), (1.2, 0), (0, -1.2), (0, 1.2)):
                p.drawText(rect.translated(dx, dy), int(flags), text)
        p.setPen(ink)
        p.drawText(rect, int(flags), text)

    def _paint_calc(self, p: QPainter, inner: QRectF) -> None:
        s, t = self.session, self.theme
        ink = QColor(t.lcd_ink)
        p.drawTiledPixmap(inner.toRect(), self._texture())
        area = inner.adjusted(9, 5, -9, -5)

        # status bar
        p.setFont(_font(10))
        bar = QRectF(area.left(), area.top(), area.width(), 13)
        self._text(p, bar, ALIGN_L, "  ".join(s.status_left()), ink)
        self._text(p, bar, ALIGN_R, "  ".join(s.status_right()), ink)

        # expression line (scrolls horizontally so the caret stays visible)
        font = _font(19)
        fm = QFontMetricsF(font)
        expr = QRectF(area.left(), area.top() + 16, area.width(), 32)
        text, caret = s.expression_view()
        avail = expr.width() - 6
        caret_x = fm.horizontalAdvance(text[:caret])
        total = fm.horizontalAdvance(text)
        sc = min(max(self._scroll, caret_x + 6 - avail), caret_x)
        sc = max(0.0, min(sc, max(0.0, total + 6 - avail)))
        self._scroll = sc
        p.save()
        p.setClipRect(expr)
        p.setFont(font)
        self._text(p, expr.translated(-sc, 0), ALIGN_L, text, ink)
        if self._blink and not s.fresh and s.prompt is None and not s.error:
            p.fillRect(QRectF(expr.left() + caret_x - sc, expr.top() + 4, 2, expr.height() - 8), ink)
        p.restore()
        p.setFont(_font(9))
        if sc > 0:
            self._text(p, QRectF(expr.left() - 8, expr.top(), 10, expr.height()), ALIGN_L, "◀", ink)
        if total - sc > avail:
            self._text(p, QRectF(expr.right() - 2, expr.top(), 10, expr.height()), ALIGN_R, "▶", ink)

        # result line
        res_rect = QRectF(area.left(), area.top() + 50, area.width(), area.height() - 50)
        if s.prompt is not None:
            result = "X=" + s.prompt + ("_" if self._blink else " ")
            px = 20
        elif s.message and not s.error:
            result, px = s.message, 16
        else:
            result = s.result_text
            px = 22 if s.error else 32
        rf = _font(px)
        while px > 12 and QFontMetricsF(rf).horizontalAdvance(result) > res_rect.width():
            px -= 2
            rf = _font(px)
        p.setFont(rf)
        self._text(p, res_rect, ALIGN_R, result, ink)

    # ---- dot-matrix screens
    def _ghost_pixmap(self, inner: QRectF) -> QPixmap:
        dpr = self.devicePixelRatioF()
        key = (round(inner.width()), round(inner.height()), self.theme.lcd_ink, dpr)
        if self._ghost is None or key != self._ghost_key:
            pm = QPixmap(int(inner.width() * dpr), int(inner.height() * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setPen(Qt.PenStyle.NoPen)
            c = QColor(self.theme.lcd_ink)
            c.setAlpha(24)
            q.setBrush(c)
            size = CELL * 0.8
            off = (CELL - size) / 2
            for y in range(GRID_H):
                for x in range(GRID_W):
                    q.drawRoundedRect(QRectF(x * CELL + off, y * CELL + off, size, size), 0.6, 0.6)
            q.end()
            self._ghost, self._ghost_key = pm, key
        return self._ghost

    def _paint_pixels(self, p: QPainter, inner: QRectF) -> None:
        screen = self.ctx.current
        if screen is None:
            return
        self.grid.clear()
        screen.render(self.grid)
        p.drawPixmap(inner.topLeft(), self._ghost_pixmap(inner))
        ink = QColor(self.theme.lcd_ink)
        size = CELL * 0.8
        off = (CELL - size) / 2
        p.setPen(Qt.PenStyle.NoPen)
        pixels = list(self.grid.on_pixels())
        if self.theme.lcd_glow:
            glow = QColor(ink)
            glow.setAlpha(48)
            p.setBrush(glow)
            for x, y in pixels:
                p.drawRoundedRect(
                    QRectF(inner.left() + x * CELL - 0.9, inner.top() + y * CELL - 0.9,
                           CELL + 1.8, CELL + 1.8), 1.5, 1.5)
        p.setBrush(ink)
        for x, y in pixels:
            p.drawRoundedRect(
                QRectF(inner.left() + x * CELL + off, inner.top() + y * CELL + off, size, size),
                0.6, 0.6)
