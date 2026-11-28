"""Linux/X11 input controller using XTest (no Qt, no extra packages).

Self-contained ctypes XTest path: injects mouse + keyboard events into the
focused window and knows how to focus the Sober window before injecting, which
matters because a game only receives synthetic key events while it owns input
focus.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p
from typing import Optional

from ..capture.window import WindowFinderUnavailable, find_window, focus_window
from .keys import KEYS, MOUSE_BUTTONS


class X11Unavailable(RuntimeError):
    """Raised when X11 / XTest cannot be initialised on this machine."""


_BTN_MASKS = {1: (1 << 8, "left"), 2: (1 << 9, "middle"), 3: (1 << 10, "right")}
_SCROLL_UP, _SCROLL_DOWN = 4, 5


def _load_libs():
    xlib = None
    for name in ("libX11.so.6", "libX11.so"):
        try:
            xlib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if xlib is None:
        raise X11Unavailable("libX11 not found — install libx11-6 (Debian/Ubuntu) or libx11 (Arch).")

    xtst = None
    for name in ("libXtst.so.6", "libXtst.so"):
        try:
            xtst = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if xtst is None:
        raise X11Unavailable("libXtst not found — install libxtst6 (Debian/Ubuntu) or libxtst (Arch).")

    try:
        xlib.XInitThreads.restype = c_int
        xlib.XInitThreads.argtypes = ()
        xlib.XInitThreads()
    except AttributeError:  # pragma: no cover - ancient libX11
        pass

    xlib.XOpenDisplay.restype = c_void_p
    xlib.XOpenDisplay.argtypes = (c_char_p,)
    xlib.XCloseDisplay.argtypes = (c_void_p,)
    xlib.XFlush.argtypes = (c_void_p,)
    xlib.XStringToKeysym.restype = c_ulong
    xlib.XStringToKeysym.argtypes = (c_char_p,)
    xlib.XKeysymToKeycode.restype = c_ubyte
    xlib.XKeysymToKeycode.argtypes = (c_void_p, c_ulong)
    xlib.XQueryKeymap.argtypes = (c_void_p, c_void_p)

    xtst.XTestFakeButtonEvent.argtypes = (c_void_p, c_uint, c_int, c_ulong)
    xtst.XTestFakeButtonEvent.restype = c_int
    xtst.XTestFakeMotionEvent.argtypes = (c_void_p, c_int, c_int, c_int, c_ulong)
    xtst.XTestFakeMotionEvent.restype = c_int
    xtst.XTestFakeKeyEvent.argtypes = (c_void_p, c_uint, c_int, c_ulong)
    xtst.XTestFakeKeyEvent.restype = c_int
    return xlib, xtst


class X11Input:
    """Injects mouse + keyboard events into the focused X11 window via XTest."""

    def __init__(self, display: Optional[str] = None) -> None:
        self._xlib, self._xtst = _load_libs()
        self._dpy = self._xlib.XOpenDisplay(display.encode() if display else None)
        if not self._dpy:
            raise X11Unavailable("Could not open an X display (are you on X11, not bare Wayland?).")
        self._keycodes: dict[str, int] = {}
        self._build_keymaps()
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()
        self._lock = threading.Lock()

    # -- setup ------------------------------------------------------------
    def _build_keymaps(self) -> None:
        for name, info in KEYS.items():
            sym = info.x11 if hasattr(info, "x11") else None
            if not sym:
                continue
            sym_id = self._xlib.XStringToKeysym(sym.encode())
            if not sym_id:
                continue
            code = int(self._xlib.XKeysymToKeycode(self._dpy, sym_id))
            if code:
                self._keycodes.setdefault(name, code)

    def _keycode(self, key: str) -> int:
        return self._keycodes.get(key, 0)

    # -- mouse ------------------------------------------------------------
    def move(self, x: int, y: int) -> None:
        self._xtst.XTestFakeMotionEvent(self._dpy, -1, int(x), int(y), 0)
        self._xlib.XFlush(self._dpy)

    def _click_at(self, button: str, x: Optional[int], y: Optional[int],
                  repeat: int) -> None:
        number = int(MOUSE_BUTTONS.get(button, 1))
        if x is not None and y is not None:
            self._xtst.XTestFakeMotionEvent(self._dpy, -1, int(x), int(y), 0)
        for _ in range(max(1, repeat)):
            self._xtst.XTestFakeButtonEvent(self._dpy, number, 1, 0)
            self._xtst.XTestFakeButtonEvent(self._dpy, number, 0, 0)
        self._xlib.XFlush(self._dpy)

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None, count: int = 1) -> None:
        self._click_at(button, x, y, max(1, int(count)))

    def down(self, button: str = "left") -> None:
        number = int(MOUSE_BUTTONS.get(button, 1))
        self._xtst.XTestFakeButtonEvent(self._dpy, number, 1, 0)
        self._xlib.XFlush(self._dpy)
        self._held_buttons.add(button)

    def up(self, button: str = "left") -> None:
        number = int(MOUSE_BUTTONS.get(button, 1))
        self._xtst.XTestFakeButtonEvent(self._dpy, number, 0, 0)
        self._xlib.XFlush(self._dpy)
        self._held_buttons.discard(button)

    def scroll(self, delta: int) -> None:
        button = _SCROLL_UP if delta > 0 else _SCROLL_DOWN
        for _ in range(max(1, abs(int(delta)))):
            self._xtst.XTestFakeButtonEvent(self._dpy, button, 1, 0)
            self._xtst.XTestFakeButtonEvent(self._dpy, button, 0, 0)
        self._xlib.XFlush(self._dpy)

    # -- keyboard ---------------------------------------------------------
    def key_down(self, key: str) -> None:
        code = self._keycode(key)
        if not code:
            return
        with self._lock:
            self._xtst.XTestFakeKeyEvent(self._dpy, code, 1, 0)
            self._xlib.XFlush(self._dpy)
            self._held_keys.add(key)

    def key_up(self, key: str) -> None:
        code = self._keycode(key)
        if not code:
            return
        with self._lock:
            self._xtst.XTestFakeKeyEvent(self._dpy, code, 0, 0)
            self._xlib.XFlush(self._dpy)
            self._held_keys.discard(key)

    def tap(self, key: str, delay: float = 0.02) -> None:
        self.key_down(key)
        time.sleep(max(0.0, delay))
        self.key_up(key)

    def hold(self, keys: list[str]) -> None:
        for key in keys:
            self.key_down(key)

    def release(self, keys: list[str]) -> None:
        for key in reversed(keys):
            self.key_up(key)

    def is_key_down(self, key: str) -> bool:
        return key in self._held_keys

    # -- window focus -----------------------------------------------------
    def focus_sober(self, title_contains: Optional[list[str]] = None,
                    process_contains: Optional[list[str]] = None) -> bool:
        """Find and focus the Sober/Roblox window so input lands in the game."""

        try:
            win = find_window(title_contains=title_contains,
                              process_contains=process_contains)
        except WindowFinderUnavailable:
            return False
        if win is None:
            return False
        try:
            focus_window(win.ident)
            return True
        except Exception:
            return False

    # -- teardown ---------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            for key in list(self._held_keys):
                self.key_up(key)
            for btn in list(self._held_buttons):
                self.up(btn)
        try:
            if self._dpy:
                self._xlib.XCloseDisplay(self._dpy)
        except Exception:
            pass
        self._dpy = None
