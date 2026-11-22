"""Backend facade: pick the right native input layer for this machine."""

from __future__ import annotations

import sys

from .. import keys as keymap
from .backend_base import Backend, BackendUnavailable, Capabilities, ClickAction, InputEvent, WindowInfo
from .monitor import BaseMonitor

_CACHE: Backend | None = None


class NullBackend(Backend):
    """Used when no native backend is available (headless / unsupported OS)."""

    os_name = sys.platform
    name = "Unavailable"
    needs_permissions_hint = ""

    def __init__(self, reason: str = "") -> None:
        super().__init__()
        self.caps = Capabilities(
            clicking=False, key_send=False, targeted_hold=False, window_list=False,
            recording=False, recording_quality="unavailable", hotkeys=False, scroll=False,
            notes=[reason] if reason else ["No native input backend available."],
        )
        self.reason = reason

    def build_click(self, button="left", double=False, x=None, y=None, burst=1) -> ClickAction:
        return ClickAction(lambda: None, 1)

    def key_down(self, key: str) -> None:
        pass

    def key_up(self, key: str) -> None:
        pass

    def mouse_down(self, button: str = "left") -> None:
        pass

    def mouse_up(self, button: str = "left") -> None:
        pass

    def move_to(self, x: int, y: int) -> None:
        pass

    def scroll(self, delta: int, x=None, y=None) -> None:
        pass

    def is_key_down(self, key: str) -> bool:
        return False

    def create_monitor(self):
        return _NullMonitor()

    def describe(self) -> str:
        return f"No input backend ({self.reason or 'unsupported platform'})"


class _NullMonitor(BaseMonitor):
    def start(self) -> bool:
        self._running = True
        return True


def _create() -> Backend:
    platform = sys.platform
    if platform.startswith("win"):
        try:
            from .backend_win import WindowsBackend
            return WindowsBackend()
        except Exception as exc:  # pragma: no cover - platform specific
            return NullBackend(f"Windows backend failed: {exc}")
    if platform.startswith("linux"):
        try:
            from .backend_x11 import X11Backend
            return X11Backend()
        except BackendUnavailable as exc:
            return NullBackend(str(exc))
        except Exception as exc:  # pragma: no cover
            return NullBackend(f"X11 backend failed: {exc}")
    if platform == "darwin":
        try:
            from .backend_mac import MacBackend
            return MacBackend()
        except BackendUnavailable as exc:
            return NullBackend(str(exc))
        except Exception as exc:  # pragma: no cover
            return NullBackend(f"macOS backend failed: {exc}")
    return NullBackend(f"Unsupported OS: {platform}")


def get_backend() -> Backend:
    global _CACHE
    if _CACHE is None:
        _CACHE = _create()
    return _CACHE


def reset_backend() -> Backend:
    global _CACHE
    _CACHE = None
    return get_backend()


__all__ = [
    "Backend", "BackendUnavailable", "Capabilities", "ClickAction", "InputEvent",
    "WindowInfo", "NullBackend", "get_backend", "reset_backend", "keymap",
]
