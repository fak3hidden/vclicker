"""Inline SVG icon set (Lucide-style, MIT) rendered on demand."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

_SVG_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
)

PATHS: dict[str, tuple[str, float]] = {
    "cursor": ('<path d="M4 3.5l7.2 17 2.3-6.6 6.6-2.3z"/>', 1.9),
    "keyboard": ('<rect x="2" y="6" width="20" height="12" rx="2.5"/>'
                 '<path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M7.5 14h9"/>', 1.8),
    "film": ('<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
             '<path d="M7.5 4v16M16.5 4v16M3 9.5h4.5M3 14.5h4.5M16.5 9.5H21M16.5 14.5H21"/>', 1.8),
    "command": ('<path d="M9 6.5a2.5 2.5 0 1 0-2.5 2.5H17a2.5 2.5 0 1 0-2.5-2.5v11a2.5 2.5 0 1 0 2.5-2.5H6.5A2.5 2.5 0 1 0 9 17.5z"/>', 1.8),
    "sliders": ('<path d="M4 7h6M14 7h6M4 17h10M18 17h2"/>'
                '<circle cx="12" cy="7" r="2.2"/><circle cx="16" cy="17" r="2.2"/>', 1.8),
    "play": ('<path d="M8 5.2l11 6.8-11 6.8z"/>', 1.9),
    "stop": ('<rect x="6" y="6" width="12" height="12" rx="2.5"/>', 1.9),
    "record": ('<circle cx="12" cy="12" r="7.5"/>', 2.0),
    "save": ('<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
             '<path d="M7.5 3v5.5h8V3M7.5 21v-6.5h9V21"/>', 1.7),
    "trash": ('<path d="M3.5 6.5h17M9 6.5V4h6v2.5M6 6.5L7.2 20h9.6L18 6.5"/>', 1.8),
    "refresh": ('<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1M20.5 3v6h-6"/>', 1.9),
    "folder": ('<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.7l2 2.2H18.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>', 1.8),
    "target": ('<circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="2.4"/>'
               '<path d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22"/>', 1.7),
    "zap": ('<path d="M13 2.5L4.5 13.5H10l-1 8 8.5-11H12z"/>', 1.8),
    "info": ('<circle cx="12" cy="12" r="8.5"/><path d="M12 11.2v5.3M12 8h.01"/>', 1.8),
    "alert": ('<path d="M12 3.5l9 16H3z"/><path d="M12 9.5v4.5M12 17h.01"/>', 1.8),
    "clock": ('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.2v5l3.2 2"/>', 1.8),
    "mouse": ('<rect x="6" y="2.5" width="12" height="19" rx="6"/><path d="M12 6.5v4"/>', 1.8),
    "export": ('<path d="M12 3v12M7.5 10.5L12 15l4.5-4.5M4.5 20h15"/>', 1.9),
    "import": ('<path d="M12 21V9M7.5 13.5L12 9l4.5 4.5M4.5 4h15"/>', 1.9),
    "plus": ('<path d="M12 5v14M5 12h14"/>', 2.0),
    "close": ('<path d="M6 6l12 12M18 6L6 18"/>', 2.0),
    "check": ('<path d="M4.5 12.5l5 5L19.5 6.5"/>', 2.1),
    "chevron-right": ('<path d="M9 5l7 7-7 7"/>', 2.0),
    "edit": ('<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14.5 5.5l3 3"/>', 1.8),
    "copy": ('<rect x="9" y="9" width="11" height="11" rx="2.5"/>'
             '<path d="M15 6V5.5A2.5 2.5 0 0 0 12.5 3H6A2.5 2.5 0 0 0 3.5 5.5V12A2.5 2.5 0 0 0 6 14.5h.5"/>', 1.8),
    "power": ('<path d="M12 3v9"/><path d="M7.5 6.2a7 7 0 1 0 9 0"/>', 1.9),
    "layers": ('<path d="M12 3l8.5 4.5L12 12 3.5 7.5z"/><path d="M3.5 12.5L12 17l8.5-4.5"/>', 1.8),
    "eye": ('<path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>', 1.8),
    "shield": ('<path d="M12 3l7 2.8v6.1c0 4.3-2.8 7.4-7 9.1-4.2-1.7-7-4.8-7-9.1V5.8z"/>', 1.8),
    "clock-fast": ('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l4 2.5"/>', 1.8),
}

_cache: dict[tuple[str, str, int], QIcon] = {}


def svg_source(name: str, color: str) -> str:
    body, width = PATHS.get(name, PATHS["info"])
    return _SVG_HEAD.format(color=color, width=width) + body + "</svg>"


def pixmap(name: str, color: str = theme.TEXT, size: int = 18, ratio: float = 2.0) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_source(name, color).encode("utf-8")))
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(ratio)
    return px


def icon(name: str, color: str = theme.TEXT, size: int = 18) -> QIcon:
    key = (name, color, size)
    if key not in _cache:
        _cache[key] = QIcon(pixmap(name, color, size))
    return _cache[key]


def refresh_icon(name: str, color: str, size: int) -> QIcon:
    _cache.pop((name, color, size), None)
    return icon(name, color, size)


def size(value: int) -> QSize:
    return QSize(value, value)
