"""Pick the right input controller for the current platform."""

from __future__ import annotations

from typing import Optional

from .base import FakeInput, InputController


def get_input(kind: str = "auto", **kwargs) -> InputController:
    """Return an input controller.

    ``kind`` is one of: ``auto`` (X11 on Linux, else fake), ``x11``, ``fake``.
    ``fake`` is what the test-suite and dry-runs use.
    """

    kind = (kind or "auto").lower()
    if kind == "fake":
        return FakeInput()
    if kind in ("x11", "auto"):
        try:
            from .linux_x11 import X11Input

            return X11Input(**kwargs)
        except Exception:
            if kind == "x11":
                raise
            # auto -> fall back to a no-op controller so dry runs still work
            return FakeInput()
    raise ValueError(f"Unknown input kind: {kind}")
