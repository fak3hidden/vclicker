"""Screen capture for the BSS macro (X11/mss + Wayland screenshot-CLI)."""

from __future__ import annotations

from .capture import CaptureConfig, ScreenCapture, SyntheticCapture
from .wayland import ShotCapture, WaylandWindow, WaylandWindowFinder
from .window import (
    WindowFinderUnavailable,
    WindowHandle,
    find_window,
    find_window_any,
    focus_window,
)

__all__ = [
    "CaptureConfig", "ScreenCapture", "SyntheticCapture",
    "ShotCapture", "WaylandWindow", "WaylandWindowFinder",
    "find_window", "find_window_any", "focus_window",
    "WindowFinderUnavailable", "WindowHandle",
]
