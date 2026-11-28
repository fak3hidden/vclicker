"""Input controllers for the BSS macro."""

from __future__ import annotations

from .base import FakeInput, InputController
from .linux_x11 import X11Input, X11Unavailable
from .select import get_input

__all__ = ["FakeInput", "InputController", "X11Input", "X11Unavailable", "get_input"]
