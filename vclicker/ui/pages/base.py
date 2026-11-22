"""Base page scaffold: sticky header + scrollable content with a two-column grid."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..widgets import label


class Page(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        self.title_label = label(title, "pageTitle")
        text_col.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, "pageSub", wrap=True)
        text_col.addWidget(self.subtitle_label)
        header.addLayout(text_col, 1)
        self.header_actions = QHBoxLayout()
        self.header_actions.setContentsMargins(0, 0, 0, 0)
        self.header_actions.setSpacing(8)
        header.addLayout(self.header_actions, 0)
        outer.addLayout(header)
        outer.addSpacing(16)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)

        self.container = QWidget()
        self.scroll.setWidget(self.container)
        self.layout_ = QVBoxLayout(self.container)
        self.layout_.setContentsMargins(0, 2, 8, 26)
        self.layout_.setSpacing(16)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.grid.setColumnStretch(0, 3)
        self.grid.setColumnStretch(1, 2)
        self._next_row = 0
        self.layout_.addLayout(self.grid)
        self.layout_.addStretch(1)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)

    def add_header_widget(self, widget: QWidget) -> None:
        self.header_actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def _row(self, row: int) -> int:
        if row < 0:
            row = self._next_row
        self._next_row = max(self._next_row, row + 1)
        return row

    def add_row(self, widget: QWidget, row: int = -1) -> int:
        row = self._row(row)
        self.grid.addWidget(widget, row, 0, 1, 2)
        return row

    def add_pair(self, left: QWidget, right: QWidget, row: int = -1) -> int:
        row = self._row(row)
        self.grid.addWidget(left, row, 0)
        self.grid.addWidget(right, row, 1)
        return row

    def add_grid_widget(self, widget: QWidget, row: int, col: int, span: int = 1) -> None:
        self._row(row)
        self.grid.addWidget(widget, row, col, 1, span)


def row(*widgets, spacing: int = 10, stretch_last: bool = False) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            layout.addStretch(1)
        elif isinstance(widget, int):
            layout.addSpacing(widget)
        else:
            layout.addWidget(widget)
    if stretch_last:
        layout.addStretch(1)
    return layout


def labeled_field(text: str, widget: QWidget) -> QWidget:
    holder = QWidget()
    holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(label(text, "muted"))
    layout.addWidget(widget)
    return holder
