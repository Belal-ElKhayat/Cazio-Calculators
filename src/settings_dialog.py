"""Models & Colours dialog (opened from the gear icon, the right-click menu or F1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from src.config import normalize_hex
from src.themes import CUSTOM_KEY, Theme

if TYPE_CHECKING:  # pragma: no cover
    from src.ui_main import MainWindow

DIALOG_QSS = """
QDialog { background: #20242c; color: #e6e9ef; }
QLabel { color: #e6e9ef; }
QGroupBox { color: #aab2c0; border: 1px solid #3a4150; border-radius: 8px; margin-top: 10px;
            padding: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton { background: #2f3644; color: #e6e9ef; border: 1px solid #454e61;
              border-radius: 7px; padding: 7px 12px; }
QPushButton:hover { background: #3a4254; }
QPushButton:checked { background: #3d5a8a; border-color: #7aa2e3; }
QLineEdit { background: #151920; color: #e6e9ef; border: 1px solid #3a4150;
            border-radius: 5px; padding: 4px 6px; }
QCheckBox { color: #e6e9ef; }
"""


def swatch_icon(theme: Theme, size: int = 34) -> QIcon:
    """Tiny three-colour preview: body | key | LCD."""
    pm = QPixmap(size * 3 + 8, size)
    pm.fill(Qt.GlobalColor.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, colour in enumerate(theme.swatches()):
        q.setBrush(QColor(colour))
        q.setPen(QColor(theme.body_edge))
        q.drawRoundedRect(i * (size + 4) + 1, 1, size - 2, size - 2, 6, 6)
    q.end()
    return QIcon(pm)


class ColorRow(QWidget):
    """Label + hex field + swatch button that opens the system colour picker."""

    changed = pyqtSignal(str, bool)  # (#rrggbb, final)

    def __init__(self, label: str, value: str, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.edit = QLineEdit(value)
        self.edit.setMaxLength(7)
        self.edit.setFixedWidth(92)
        self.edit.setPlaceholderText("#rrggbb")
        self.swatch = QPushButton()
        self.swatch.setFixedSize(34, 26)
        self.swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.edit)
        lay.addWidget(self.swatch)
        self._paint_swatch(value)
        self.edit.textChanged.connect(self._on_text)
        self.edit.editingFinished.connect(self._on_done)
        self.swatch.clicked.connect(self._pick)

    def value(self) -> str:
        return normalize_hex(self.edit.text()) or "#000000"

    def set_value(self, value: str) -> None:
        self.edit.blockSignals(True)
        self.edit.setText(value)
        self.edit.blockSignals(False)
        self._paint_swatch(value)

    def _paint_swatch(self, value: str) -> None:
        self.swatch.setStyleSheet(
            f"background: {value}; border: 1px solid #8a93a5; border-radius: 5px;")

    def _on_text(self, text: str) -> None:
        norm = normalize_hex(text)
        if norm and (len(text.lstrip('#')) in (3, 6)):
            self._paint_swatch(norm)
            self.changed.emit(norm, False)

    def _on_done(self) -> None:
        norm = normalize_hex(self.edit.text())
        if norm:
            self.edit.setText(norm)
            self.changed.emit(norm, True)

    def _pick(self) -> None:
        colour = QColorDialog.getColor(QColor(self.value()), self, "Pick a colour")
        if colour.isValid():
            hex_ = colour.name().lower()
            self.set_value(hex_)
            self.changed.emit(hex_, True)


class SettingsDialog(QDialog):
    def __init__(self, win: "MainWindow") -> None:
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Cazio - Models & Colours")
        self.setStyleSheet(DIALOG_QSS)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # -- model presets
        models = QGroupBox("Calculator model")
        grid = QGridLayout(models)
        grid.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: Dict[str, QPushButton] = {}
        entries = list(win.presets.items()) + [(CUSTOM_KEY, win.theme_for(CUSTOM_KEY))]
        for i, (key, theme) in enumerate(entries):
            btn = QPushButton(f"  {theme.name}")
            btn.setCheckable(True)
            btn.setIcon(swatch_icon(theme))
            btn.setIconSize(swatch_icon(theme).actualSize(btn.sizeHint()))
            btn.setToolTip(theme.description)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._choose(k))
            self.group.addButton(btn)
            self.buttons[key] = btn
            grid.addWidget(btn, i // 2, i % 2)
        root.addWidget(models)

        # -- custom colours
        custom = QGroupBox("Custom colours (hex)")
        form = QVBoxLayout(custom)
        c = win.cfg["custom"]
        self.rows = {
            "body": ColorRow("Calculator body", c["body"]),
            "buttons": ColorRow("Buttons", c["buttons"]),
            "lcd": ColorRow("LCD backlight", c["lcd"]),
        }
        for row in self.rows.values():
            row.changed.connect(self._custom_changed)
            form.addWidget(row)
        hint = QLabel("Changes apply live and are saved to config.json.")
        hint.setStyleSheet("color: #8a93a5; font-size: 11px;")
        form.addWidget(hint)
        root.addWidget(custom)

        # -- window
        self.on_top = QCheckBox("Keep Cazio on top of other windows")
        self.on_top.setChecked(bool(win.cfg["always_on_top"]))
        self.on_top.toggled.connect(win.set_always_on_top)
        root.addWidget(self.on_top)

        foot = QHBoxLayout()
        reset = QPushButton("Reset custom")
        reset.clicked.connect(self._reset_custom)
        close = QPushButton("Done")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        foot.addWidget(reset)
        foot.addStretch(1)
        foot.addWidget(close)
        root.addLayout(foot)
        self.sync()

    # ---------------------------------------------------------------- sync
    def sync(self) -> None:
        current = self.win.theme_key
        for key, btn in self.buttons.items():
            btn.setChecked(key == current)
        custom_theme = self.win.theme_for(CUSTOM_KEY)
        self.buttons[CUSTOM_KEY].setIcon(swatch_icon(custom_theme))

    def _choose(self, key: str) -> None:
        self.win.apply_theme(key)
        self.sync()

    def _custom_changed(self, _hex: str, final: bool) -> None:
        self.win.apply_custom(
            self.rows["body"].value(), self.rows["buttons"].value(), self.rows["lcd"].value(),
            persist=final)
        self.sync()

    def _reset_custom(self) -> None:
        from src.config import DEFAULTS

        d = DEFAULTS["custom"]
        for key, row in self.rows.items():
            row.set_value(d[key])
        self.win.apply_custom(d["body"], d["buttons"], d["lcd"], persist=True)
        self.sync()
