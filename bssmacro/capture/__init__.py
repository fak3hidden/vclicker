"""Screen capture for the BSS macro."""

from __future__ import annotations

from .capture import CaptureConfig, ScreenCapture, SyntheticCapture
from .window import find_window, focus_window, WindowFinderUnavailable, WindowHandle

__all__ = [
    "CaptureConfig", "ScreenCapture", "SyntheticCapture",
    "find_window", "focus_window", "WindowFinderUnavailable", "WindowHandle",
]
