"""Reusable UI building blocks for the VClicker interface."""

from __future__ import annotations

import math
import os
from typing import Iterable

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QRectF, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QCheckBox, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QSizePolicy, QSlider, QVBoxLayout, QWidget)

from .. import icons, keys as keymap, theme
from ..core.backend_base import WindowInfo


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value) -> None:
    widget.setProperty(name, value)
    repolish(widget)


def label(text: str = "", role: str | None = None, parent: QWidget | None = None,
          wrap: bool = False) -> QLabel:
    widget = QLabel(text, parent)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    return widget


def icon_button(name: str, tooltip: str = "", color: str = theme.MUTED, size: int = 17,
                variant: str = "icon", parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(parent)
    button.setProperty("variant", variant)
    button.setIcon(icons.icon(name, color, size))
    button.setIconSize(QSize(size, size))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        button.setToolTip(tooltip)
    button.setFixedSize(32, 32)
    return button


def button(text: str, variant: str = "default", icon_name: str | None = None,
           icon_color: str | None = None, parent: QWidget | None = None) -> QPushButton:
    widget = QPushButton(text, parent)
    widget.setProperty("variant", variant)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        color = icon_color
        if color is None:
            color = theme.ON_ACCENT if variant in ("primary", "hero") else theme.TEXT
        widget.setIcon(icons.icon(icon_name, color, 17))
        widget.setIconSize(QSize(17, 17))
    return widget


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def hspacer() -> QWidget:
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return spacer


def soft_shadow(widget: QWidget, blur: int = 28, alpha: int = 90, y_offset: int = 6) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def icon_badge(name: str, color: str, soft: str, size: int = 34, icon_size: int = 18) -> QLabel:
    holder = QLabel()
    holder.setFixedSize(size, size)
    holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    holder.setPixmap(icons.pixmap(name, color, icon_size))
    holder.setStyleSheet(
        f"background: {soft}; border-radius: {size // 2 - 2}px; border: 1px solid "
        f"{theme._with_alpha(color, 0.18)};"
    )
    return holder


def letter_spacing(widget: QWidget, spacing: float, weight: int | None = None) -> None:
    font = widget.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    if weight is not None:
        font.setWeight(QFont.Weight(weight))
    widget.setFont(font)


# --------------------------------------------------------------------------- #
#  Card
# --------------------------------------------------------------------------- #
class Card(QFrame):
    """Rounded panel with an optional icon header.

    Content is top-packed by default (a trailing stretch absorbs spare height);
    adding a child with ``stretch`` lets that child take the spare height instead.
    """

    def __init__(self, title: str = "", subtitle: str = "", icon_name: str | None = None,
                 parent: QWidget | None = None, padding: int = 16,
                 spacing: int = 12) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(padding, padding, padding, padding)
        self._outer.setSpacing(spacing)
        self.header_row: QHBoxLayout | None = None
        self._title_label: QLabel | None = None
        self._spacer_active = False
        self._has_stretch = False
        if title:
            self._build_header(title, subtitle, icon_name)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(spacing)
        self._outer.addLayout(self.body, 1)
        self._add_spacer()

    def _build_header(self, title: str, subtitle: str, icon_name: str | None) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        if icon_name:
            _main, _hover, _press, soft, _label = theme.accent_tuple(_accent_name())
            row.addWidget(icon_badge(icon_name, _main, soft), 0, Qt.AlignmentFlag.AlignTop)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self._title_label = label(title, "cardTitle")
        text_col.addWidget(self._title_label)
        if subtitle:
            text_col.addWidget(label(subtitle, "cardDesc", wrap=True))
        row.addLayout(text_col, 1)
        self.header_row = row
        self._outer.addLayout(row)

    # -- spacer bookkeeping ------------------------------------------------ #
    def _add_spacer(self) -> None:
        if self._has_stretch or self._spacer_active:
            return
        self.body.addStretch(1)
        self._spacer_active = True

    def _drop_spacer(self) -> None:
        if self._spacer_active:
            spacer = self.body.takeAt(self.body.count() - 1)
            if spacer is not None:
                spacer.widget()  # no-op keeps ownership explicit
                del spacer
            self._spacer_active = False

    # -- content ----------------------------------------------------------- #
    def add(self, widget: QWidget, stretch: int = 0) -> None:
        self._drop_spacer()
        self.body.addWidget(widget, stretch)
        if stretch:
            self._has_stretch = True
        self._add_spacer()

    def add_layout(self, layout, stretch: int = 0) -> None:
        self._drop_spacer()
        self.body.addLayout(layout, stretch)
        if stretch:
            self._has_stretch = True
        self._add_spacer()

    def add_header_widget(self, widget: QWidget) -> None:
        if self.header_row is not None:
            self.header_row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_title(self, text: str) -> None:
        if self._title_label:
            self._title_label.setText(text)


def _accent_name() -> str:
    from .. import theme as theme_module
    return getattr(theme_module, "CURRENT_ACCENT", "indigo")


class StatTile(QFrame):
    def __init__(self, caption: str, value: str = "—", unit: str = "",
                 icon_name: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "tile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.caption = label(caption.upper(), "statLabel")
        letter_spacing(self.caption, 0.8)
        top.addWidget(self.caption)
        top.addStretch(1)
        if icon_name:
            icon_label = QLabel()
            icon_label.setPixmap(icons.pixmap(icon_name, theme.DIM, 15))
            top.addWidget(icon_label)
        layout.addLayout(top)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(5)
        self.value = label(value, "statValue")
        self.unit = label(unit, "statUnit")
        value_row.addWidget(self.value)
        value_row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)
        layout.addLayout(value_row)

    def set_value(self, value: str, unit: str | None = None) -> None:
        self.value.setText(value)
        if unit is not None:
            self.unit.setText(unit)


# --------------------------------------------------------------------------- #
#  Toggle switch
# --------------------------------------------------------------------------- #
class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        main, _hover, _press, soft, _label = theme.accent_tuple(_accent_name())
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = rect.height() / 2

        base = QColor("#1C212B")
        if self.isChecked():
            color = QColor(main)
        else:
            color = base
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, radius, radius)

        knob_d = rect.height() - 8
        travel = rect.width() - knob_d - 8
        x = rect.left() + 4 + travel * self._offset
        knob = QRectF(x, rect.top() + 4, knob_d, knob_d)
        painter.setBrush(QColor("#0A0B0F") if self.isChecked() else QColor("#FFFFFF"))
        painter.drawEllipse(knob)
        painter.end()


# --------------------------------------------------------------------------- #
#  Segmented control
# --------------------------------------------------------------------------- #
class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options: Iterable[tuple[str, str]], current: str | None = None,
                 parent: QWidget | None = None, stretch: bool = True) -> None:
        super().__init__(parent)
        self._options = list(options)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setProperty("role", "segmented")
        self.frame.setSizePolicy(QSizePolicy.Policy.Expanding if stretch else QSizePolicy.Policy.Maximum,
                                 QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self.frame)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in self._options:
            btn = QPushButton(text)
            btn.setProperty("variant", "segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if stretch:
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(btn)
            self.group.addButton(btn)
            self.buttons[key] = btn
            btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
        outer.addWidget(self.frame)
        self._current = ""
        if current is None and self._options:
            current = self._options[0][0]
        if current:
            self.set_value(current, emit=False)

    def _select(self, key: str) -> None:
        if key == self._current:
            return
        self._current = key
        self.buttons[key].setChecked(True)
        self.changed.emit(key)

    def value(self) -> str:
        return self._current

    def set_value(self, key: str, emit: bool = False) -> None:
        if key not in self.buttons:
            return
        self._current = key
        self.buttons[key].setChecked(True)
        if emit:
            self.changed.emit(key)

    def set_option_enabled(self, key: str, enabled: bool) -> None:
        if key in self.buttons:
            self.buttons[key].setEnabled(enabled)


# --------------------------------------------------------------------------- #
#  Key capture button
# --------------------------------------------------------------------------- #
class KeyCapture(QPushButton):
    captured = Signal(str)

    def __init__(self, hotkeys, allow_combo: bool = False, placeholder: str = "Click to set",
                 parent: QWidget | None = None) -> None:
        super().__init__(placeholder, parent)
        self.hotkeys = hotkeys
        self.allow_combo = allow_combo
        self.placeholder = placeholder
        self._value = ""
        self.setProperty("variant", "chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)
        self.clicked.connect(self._begin)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value or ""
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self.property("capturing"):
            self.setText("Press a key…")
        elif self._value:
            self.setText(keymap.combo_text(self._value) if self.allow_combo else keymap.label(self._value))
        else:
            self.setText(self.placeholder)

    def _set_capturing(self, active: bool) -> None:
        self.setProperty("capturing", "true" if active else "false")
        repolish(self)
        self._refresh_text()

    def _begin(self) -> None:
        if self.property("capturing") == "true":
            self.hotkeys.cancel_capture()
            self._set_capturing(False)
            return
        if not self.hotkeys:
            return
        self.hotkeys.suspend()
        self._set_capturing(True)
        self.hotkeys.capture_next(self._done)

    def _done(self, combo: str | None) -> None:
        self.hotkeys.resume()
        self._set_capturing(False)
        if combo is None:
            return
        if not self.allow_combo:
            parts = keymap.parse_parts(combo)
            if not parts:
                return
            non_mods = [p for p in parts if not keymap.is_modifier(p)]
            value = (non_mods or parts)[-1]
        else:
            value = combo
        self._value = value
        self._refresh_text()
        self.captured.emit(value)

    def hideEvent(self, event) -> None:
        if self.property("capturing") == "true":
            self.hotkeys.cancel_capture()
        super().hideEvent(event)


# --------------------------------------------------------------------------- #
#  Live CPS graph
# --------------------------------------------------------------------------- #
class CpsGraph(QWidget):
    def __init__(self, points: int = 90, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points = points
        self._samples: list[float] = []
        self._peak = 1.0
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pulse = 0.0
        self._pulse_anim = QPropertyAnimation(self, b"pulse", self)
        self._pulse_anim.setDuration(420)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, get_pulse, set_pulse)

    def push(self, value: float) -> None:
        self._samples.append(max(0.0, float(value)))
        if len(self._samples) > self._points:
            self._samples = self._samples[-self._points:]
        self._peak = max(1.0, max(self._samples) if self._samples else 1.0)
        self.update()

    def reset(self) -> None:
        self._samples.clear()
        self._peak = 1.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(theme.CARD))
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        main, _h, _p, _soft, _l = theme.accent_tuple(_accent_name())
        base = QColor("#1D2430")
        painter.setPen(QPen(base, 1, Qt.PenStyle.DashLine))
        for fraction in (0.25, 0.5, 0.75):
            y = rect.top() + rect.height() * fraction
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        if len(self._samples) < 2:
            painter.setPen(QColor(theme.DIM))
            font = painter.font()
            font.setPointSizeF(max(8.0, font.pointSizeF() - 0.5))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Waiting for clicks…")
            painter.end()
            return

        values = self._samples
        step = rect.width() / max(1, self._points - 1)
        path = QPainterPath()
        start_x = rect.left() + (self._points - len(values)) * step
        for index, value in enumerate(values):
            x = start_x + index * step
            ratio = min(1.0, value / max(1.0, self._peak))
            y = rect.bottom() - ratio * (rect.height() - 6) - 2
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        fill = QPainterPath(path)
        fill.lineTo(start_x + (len(values) - 1) * step, rect.bottom())
        fill.lineTo(start_x, rect.bottom())
        fill.closeSubpath()

        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        top_color = QColor(main)
        top_color.setAlpha(90)
        bottom_color = QColor(main)
        bottom_color.setAlpha(0)
        gradient.setColorAt(0.0, top_color)
        gradient.setColorAt(1.0, bottom_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(fill)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(main), 2.0))
        painter.drawPath(path)
        painter.end()


# --------------------------------------------------------------------------- #
#  Status pill
# --------------------------------------------------------------------------- #
class StatusPill(QLabel):
    def __init__(self, text: str = "Idle", state: str = "off", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "pill")
        self.set_state(state)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_state(self, state: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("state", state)
        repolish(self)


# --------------------------------------------------------------------------- #
#  Slider + numeric field row
# --------------------------------------------------------------------------- #
class SliderRow(QWidget):
    """Label + value readout + slider, with optional logarithmic scaling."""

    value_changed = Signal(float)

    def __init__(self, title: str, minimum: float, maximum: float, value: float,
                 suffix: str = "", decimals: int = 0, step: float = 1.0,
                 parent: QWidget | None = None, log: bool = False,
                 tooltip: str = "") -> None:
        super().__init__(parent)
        self.decimals = decimals
        self._log = log and minimum > 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        title_label = label(title, "muted")
        if tooltip:
            title_label.setToolTip(tooltip)
            self.setToolTip(tooltip)
        top.addWidget(title_label)
        top.addStretch(1)
        self.readout = label("", "badge")
        self.readout.setProperty("tone", "accent")
        top.addWidget(self.readout)
        layout.addLayout(top)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setFixedHeight(22)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.slider)

        self._minimum = minimum
        self._maximum = maximum
        self._suffix = suffix
        self._step = step
        self._value = value
        self.slider.valueChanged.connect(self._from_slider)
        self.set_value(value, emit=False)

    # -- mapping ----------------------------------------------------------- #
    def _to_slider(self, value: float) -> int:
        value = max(self._minimum, min(self._maximum, value))
        if self._log:
            ratio = math.log(value / self._minimum) / math.log(self._maximum / self._minimum)
        else:
            ratio = (value - self._minimum) / max(1e-9, self._maximum - self._minimum)
        return int(round(max(0.0, min(1.0, ratio)) * 1000))

    def _from_slider(self, raw: int) -> None:
        ratio = raw / 1000.0
        if self._log:
            value = self._minimum * (self._maximum / self._minimum) ** ratio
        else:
            value = self._minimum + ratio * (self._maximum - self._minimum)
        if self._step >= 1:
            value = round(value / self._step) * self._step
        self._value = max(self._minimum, min(self._maximum, round(value, 3)))
        self._refresh()
        self.value_changed.emit(float(self._value))

    def value(self) -> float:
        return self._value

    def set_value(self, value: float, emit: bool = True) -> None:
        self._value = max(self._minimum, min(self._maximum, float(value)))
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_slider(self._value))
        self.slider.blockSignals(False)
        self._refresh()
        if emit:
            self.value_changed.emit(float(self._value))

    def _refresh(self) -> None:
        if self.decimals <= 0:
            text = f"{int(round(self._value)):,}"
        else:
            text = f"{self._value:.{self.decimals}f}"
        self.readout.setText(f"{text}{self._suffix}")


# --------------------------------------------------------------------------- #
#  Window picker
# --------------------------------------------------------------------------- #
class WindowRow(QWidget):
    toggled = Signal(int, bool)

    def __init__(self, info: WindowInfo, checked: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        self.check = QCheckBox()
        self.check.setChecked(checked)
        self.check.toggled.connect(lambda state: self.toggled.emit(self.info.ident, state))
        layout.addWidget(self.check)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        title = label(info.display_title[:90], "muted")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 12.5px; font-weight: 500;")
        text_col.addWidget(title)
        subtitle = label(info.subtitle or "unknown process", "dim")
        subtitle.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        text_col.addWidget(subtitle)
        layout.addLayout(text_col, 1)


class WindowPicker(QWidget):
    selection_changed = Signal()

    def __init__(self, backend, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.backend = backend
        self._windows: list[WindowInfo] = []
        self._selected: dict[int, WindowInfo] = {}
        self._rows: list[WindowRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter open windows…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)
        self.refresh_button = icon_button("refresh", "Refresh window list", theme.MUTED)
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setMinimumHeight(250)
        self.list.setMaximumHeight(320)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list)

        self.empty_label = label("No windows found — open the app you want to target, then refresh.",
                                 "dim", wrap=True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.count_label = label("0 selected", "dim")
        link_all = QPushButton("Select all")
        link_all.setProperty("variant", "ghost")
        link_all.setCursor(Qt.CursorShape.PointingHandCursor)
        link_all.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        link_all.clicked.connect(self.select_all)
        link_clear = QPushButton("Clear")
        link_clear.setProperty("variant", "ghost")
        link_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        link_clear.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        link_clear.clicked.connect(self.clear_selection)
        bottom.addWidget(self.count_label, 1)
        bottom.addWidget(link_all)
        bottom.addWidget(link_clear)
        layout.addLayout(bottom)

        self._filter = ""

    # -- api --------------------------------------------------------------- #
    def selected(self) -> list[WindowInfo]:
        return list(self._selected.values())

    def selected_idents(self) -> list[int]:
        return list(self._selected.keys())

    def set_selection(self, windows: list[WindowInfo]) -> None:
        self._selected = {w.ident: w for w in windows}
        self._rebuild_rows()

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        try:
            windows = self.backend.list_windows()
        except Exception:
            windows = []
        own_pid = os.getpid()
        windows = [w for w in windows if w.pid != own_pid]
        self._windows = windows
        # keep selections that still exist
        idents = {w.ident for w in windows}
        self._selected = {k: v for k, v in self._selected.items() if k in idents}
        self._rebuild_rows()
        self.refresh_button.setEnabled(True)

    def select_all(self) -> None:
        for info in self._windows:
            self._selected[info.ident] = info
        self._rebuild_rows()

    def clear_selection(self) -> None:
        self._selected.clear()
        self._rebuild_rows()

    # -- internals --------------------------------------------------------- #
    def _rebuild_rows(self) -> None:
        self.list.clear()
        self._rows = []
        for info in self._windows:
            row = WindowRow(info, info.ident in self._selected)
            row.toggled.connect(self._on_toggled)
            item = QListWidgetItem(self.list)
            item.setData(Qt.ItemDataRole.UserRole, info.ident)
            item.setSizeHint(QSize(0, 46))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self._rows.append(row)
        self._apply_filter(self.search.text())
        self._update_count()

    def _on_toggled(self, ident: int, checked: bool) -> None:
        info = next((w for w in self._windows if w.ident == ident), None)
        if checked and info:
            self._selected[ident] = info
        else:
            self._selected.pop(ident, None)
        self._update_count()
        self.selection_changed.emit()

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        self._filter = needle
        visible = 0
        for index in range(self.list.count()):
            item = self.list.item(index)
            row = self.list.itemWidget(item)
            haystack = ""
            if isinstance(row, WindowRow):
                haystack = f"{row.info.title} {row.info.process}".lower()
            match = (not needle) or needle in haystack
            item.setHidden(not match)
            if match:
                visible += 1
        has_any = len(self._windows) > 0
        self.list.setVisible(has_any and visible > 0)
        self.empty_label.setVisible(visible == 0)
        if not has_any:
            self.empty_label.setText(
                "No windows found — open the app you want to target, then hit refresh.")
        elif visible == 0:
            self.empty_label.setText("Nothing matches that filter.")

    def _update_count(self) -> None:
        count = len(self._selected)
        self.count_label.setText(f"{count} selected" if count else "No windows selected")


# --------------------------------------------------------------------------- #
#  Macro timeline
# --------------------------------------------------------------------------- #
class MacroTimeline(QWidget):
    def __init__(self, parent: QWidget | None = None, empty_text: str = "No macro selected") -> None:
        super().__init__(parent)
        self.setMinimumHeight(58)
        self._events = []
        self._duration = 0.0
        self._empty_text = empty_text

    def set_events(self, events, duration: float) -> None:
        self._events = list(events or [])
        self._duration = max(0.01, float(duration or 0.01))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 2, 0, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.SURFACE))
        painter.drawRoundedRect(rect, 8, 8)

        if not self._events:
            painter.setPen(QColor(theme.DIM))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._empty_text)
            painter.end()
            return

        main, _h, _p, _soft, _l = theme.accent_tuple(_accent_name())
        buckets = 160
        width = rect.width() / buckets
        buckets_data: list[dict[str, int]] = [dict() for _ in range(buckets)]
        for ev in self._events:
            index = int((ev.t / self._duration) * (buckets - 1))
            index = max(0, min(buckets - 1, index))
            key = "click" if ev.kind in ("down", "up") else ("key" if ev.kind.startswith("key") else "move")
            buckets_data[index][key] = buckets_data[index].get(key, 0) + 1

        painter.setClipRect(rect)
        for index, data in enumerate(buckets_data):
            if not data:
                continue
            height = rect.height() * min(1.0, 0.18 + (sum(data.values()) * 0.16))
            x = rect.left() + index * width
            color = QColor(main)
            if data.get("click"):
                color = QColor(theme.DANGER)
            elif data.get("key"):
                color = QColor(theme.WARN)
            else:
                color = QColor(theme.BORDER)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, rect.bottom() - height, max(1.4, width - 1.0), height), 2, 2)
        painter.setClipping(False)
        painter.end()


# --------------------------------------------------------------------------- #
#  Empty state
# --------------------------------------------------------------------------- #
class EmptyState(QWidget):
    def __init__(self, icon_name: str, title: str, subtitle: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 18, 0, 18)
        layout.setSpacing(8)
        badge = icon_badge(icon_name, theme.DIM, theme.SURFACE, 44, 20)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        heading = label(title, "cardTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        description = label(subtitle, "cardDesc", wrap=True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)


# --------------------------------------------------------------------------- #
#  Small info banner
# --------------------------------------------------------------------------- #
class Banner(QFrame):
    def __init__(self, text: str = "", tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "inset")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(9)
        self.icon = QLabel()
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        self.text = label(text, "dim", wrap=True)
        layout.addWidget(self.text, 1)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        colors = {
            "info": (theme.MUTED, theme.SURFACE),
            "warn": (theme.WARN, "rgba(251, 191, 36, 0.08)"),
            "bad": (theme.DANGER, "rgba(248, 113, 113, 0.08)"),
            "ok": (theme.SUCCESS, "rgba(74, 222, 128, 0.08)"),
        }
        color, bg = colors.get(tone, colors["info"])
        name = "info" if tone == "info" else ("alert" if tone in ("warn", "bad") else "check")
        self.icon.setPixmap(icons.pixmap(name, color, 15))
        self.setStyleSheet(f"QFrame[role='inset'] {{ background: {bg}; }}")

    def set_text(self, text: str) -> None:
        self.text.setText(text)


class Flash(QTimer):
    """Tiny helper: coalesce rapid UI refreshes."""

    def __init__(self, interval_ms: int, callback) -> None:
        super().__init__()
        self.setSingleShot(True)
        self.setInterval(interval_ms)
        self.timeout.connect(callback)


def tr_mmss(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    if minutes:
        return f"{minutes}:{rest:04.1f}"
    return f"{rest:.2f}s"


class ToggleRow(QWidget):
    """Label + description on the left, animated switch on the right."""

    toggled = Signal(bool)

    def __init__(self, title: str, subtitle: str = "", checked: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(label(title, "muted"))
        if subtitle:
            text_col.addWidget(label(subtitle, "dim", wrap=True))
        layout.addLayout(text_col, 1)
        self.switch = ToggleSwitch(checked)
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        self.switch.toggled.connect(self.toggled.emit)

    def isChecked(self) -> bool:  # noqa: N802 - Qt-style name
        return self.switch.isChecked()

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(value))
        self.switch.blockSignals(False)


class KeyCap(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "key")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


def keycap_row(*caps: str) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for text in caps:
        layout.addWidget(KeyCap(text))
    layout.addStretch(1)
    return holder
