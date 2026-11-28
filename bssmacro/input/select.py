"""Pick the right input controller for the current platform / display server.

Selection order for ``auto``:

1. **X11 / XWayland** — ``X11Input`` (XTest) when ``DISPLAY`` is set and the X
   libraries load. Works for Sober-under-XWayland and plain X11 sessions.
2. **Native Wayland** — ``UinputInput`` (virtual device via /dev/uinput) when
   the kernel interface is writable. Works on GNOME/KDE/wlroots Wayland.
3. **ydotool** (explicit only) — shells out to the ``ydotool`` CLI; requires a
   running ``ydotoold``.
4. **FakeInput** — last resort for dry runs and tests; never injects anything.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import FakeInput, InputController


def get_input(kind: str = "auto", **kwargs) -> InputController:
    """Return an input controller.

    ``kind`` is one of: ``auto`` (X11, then uinput, then fake), ``x11``,
    ``uinput`` (alias ``wayland``), ``ydotool``, ``fake``.
    """

    kind = (kind or "auto").lower()
    if kind == "fake":
        return FakeInput()

    if kind == "x11":
        from .linux_x11 import X11Input

        return X11Input(**kwargs)

    if kind in ("uinput", "wayland"):
        from .linux_uinput import UinputInput

        return UinputInput(**kwargs)

    if kind == "ydotool":
        from .ydotool import YdotoolInput

        return YdotoolInput(**kwargs)

    if kind == "auto":
        # 1) X11/XWayland: XTest is precise and needs no extra permissions.
        if os.environ.get("DISPLAY"):
            try:
                from .linux_x11 import X11Input

                return X11Input(**kwargs)
            except Exception:
                pass
        # 2) Native Wayland: virtual device via /dev/uinput.
        try:
            from .linux_uinput import UinputInput

            return UinputInput(**kwargs)
        except Exception:
            pass
        # 3) Give up gracefully — dry runs and tests still work.
        return FakeInput()

    raise ValueError(f"Unknown input kind: {kind}")


def describe_auto() -> str:
    """Human-readable summary of what ``auto`` would pick here (for CLI)."""

    if os.environ.get("DISPLAY"):
        return "x11 (DISPLAY set)"
    try:
        from .linux_uinput import uinput_available

        if uinput_available():
            return "uinput (Wayland virtual device)"
    except Exception:
        pass
    return "fake (no display / no permissions — dry-run only)"
