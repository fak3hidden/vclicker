"""Input controllers for the BSS macro."""

from __future__ import annotations

from .base import FakeInput, InputController
from .linux_uinput import UinputInput, UinputUnavailable, uinput_available
from .linux_x11 import X11Input, X11Unavailable
from .select import describe_auto, get_input
from .ydotool import YdotoolInput, YdotoolUnavailable

__all__ = [
    "FakeInput", "InputController", "get_input", "describe_auto",
    "X11Input", "X11Unavailable",
    "UinputInput", "UinputUnavailable", "uinput_available",
    "YdotoolInput", "YdotoolUnavailable",
]
