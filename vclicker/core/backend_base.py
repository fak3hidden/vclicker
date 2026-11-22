"""Shared pieces for the native input backends."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


# --------------------------------------------------------------------------- #
#  Events
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class InputEvent:
    """A single low-level input event captured by a monitor thread."""

    kind: str                      # key_down | key_up | mouse_down | mouse_up | move | wheel
    t: float = field(default_factory=time.perf_counter)
    key: str | None = None
    button: str | None = None
    x: int = 0
    y: int = 0
    delta: int = 0
    injected: bool = False


@dataclass(slots=True)
class WindowInfo:
    """A top-level window that keys can be held on."""

    ident: int
    title: str
    process: str = ""
    pid: int = 0

    @property
    def display_title(self) -> str:
        return self.title or self.process or f"Window {self.ident}"

    @property
    def subtitle(self) -> str:
        if self.process and self.pid:
            return f"{self.process} · PID {self.pid}"
        return self.process or (f"PID {self.pid}" if self.pid else "")


@dataclass(slots=True)
class Capabilities:
    clicking: bool = True
    key_send: bool = True
    targeted_hold: bool = False        # can hold keys on a window without focus
    window_list: bool = False
    recording: bool = False            # precise global recording
    recording_quality: str = ""        # e.g. "Low-level hooks (exact)" / "Polling (2 ms)"
    hotkeys: bool = True
    scroll: bool = True
    notes: list[str] = field(default_factory=list)


class BackendUnavailable(RuntimeError):
    """Raised when a platform backend cannot be initialised on this machine."""


# --------------------------------------------------------------------------- #
#  Click throwing
# --------------------------------------------------------------------------- #
class ClickAction:
    """A pre-built click that can be fired in a tight loop with no allocation."""

    __slots__ = ("_fire", "burst")

    def __init__(self, fire: Callable[[], None], burst: int):
        self._fire = fire
        self.burst = burst

    def fire(self) -> None:
        self._fire()


# --------------------------------------------------------------------------- #
#  Backend base
# --------------------------------------------------------------------------- #
class Backend:
    os_name = "unknown"
    name = "Unknown"
    needs_permissions_hint = ""

    def __init__(self) -> None:
        self.caps = Capabilities()
        self.last_error = ""

    # -- mouse ------------------------------------------------------------- #
    def build_click(self, button: str = "left", double: bool = False,
                    x: int | None = None, y: int | None = None,
                    burst: int = 1) -> ClickAction:
        raise NotImplementedError

    def click(self, button: str = "left", double: bool = False,
              x: int | None = None, y: int | None = None) -> None:
        self.build_click(button, double, x, y, 1).fire()

    def mouse_down(self, button: str = "left") -> None:
        raise NotImplementedError

    def mouse_up(self, button: str = "left") -> None:
        raise NotImplementedError

    def move_to(self, x: int, y: int) -> None:
        raise NotImplementedError

    def cursor_pos(self) -> tuple[int, int]:
        return (0, 0)

    def scroll(self, delta: int, x: int | None = None, y: int | None = None) -> None:
        raise NotImplementedError

    # -- keyboard ---------------------------------------------------------- #
    def key_down(self, key: str) -> None:
        raise NotImplementedError

    def key_up(self, key: str) -> None:
        raise NotImplementedError

    def key_press(self, key: str) -> None:
        self.key_down(key)
        self.key_up(key)

    def hold_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        """Press keys and keep them held (optionally on specific windows)."""
        for key in keys:
            self.key_down(key)

    def release_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        for key in reversed(keys):
            self.key_up(key)

    # -- windows ----------------------------------------------------------- #
    def list_windows(self) -> list[WindowInfo]:
        return []

    # -- misc -------------------------------------------------------------- #
    def screen_size(self) -> tuple[int, int]:
        return (1920, 1080)

    def is_key_down(self, key: str) -> bool:
        return False

    def create_monitor(self):
        raise NotImplementedError

    def describe(self) -> str:
        return self.name

    def shutdown(self) -> None:
        pass


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def spin_sleep(deadline: float) -> None:
    """Sleep until ``deadline`` (perf_counter) with sub-millisecond accuracy."""
    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return
        if remaining > 0.0015:
            time.sleep(min(remaining - 0.001, 0.02))
        else:
            end = deadline - 0.00002
            while time.perf_counter() < end:
                pass
            return
