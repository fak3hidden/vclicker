"""Logic tests for the X11 backend, driven by a fake libX11/libXtst.

There is no X server in CI, so the real libraries cannot run here. These tests
replace the ctypes entry points with recording fakes and check that VClicker
builds the right X11 calls: button numbers, press/release order, focus
save/restore for multi-window key holds, property parsing and the polling
monitor.

Out-parameters that are pointers (window properties, child lists) are provided
through CFUNCTYPE callbacks, because ctypes only writes those back through a
real C call — the same thing libX11 does.

    QT_QPA_PLATFORM=offscreen python tools/x11_mock_test.py
"""

from __future__ import annotations

import os
import sys
import time
from ctypes import (CFUNCTYPE, POINTER, c_int, c_long, c_ubyte, c_uint, c_ulong,
                    c_void_p, cast)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vclicker.core.backend_base import Capabilities, WindowInfo  # noqa: E402
from vclicker.core.backend_x11 import X11Backend, X11Monitor  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []

PROP_CB = CFUNCTYPE(c_int, c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
                    POINTER(c_ulong), POINTER(c_int), POINTER(c_ulong),
                    POINTER(c_ulong), POINTER(POINTER(c_ubyte)))
TREE_CB = CFUNCTYPE(c_int, c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong),
                    POINTER(POINTER(c_ulong)), POINTER(c_uint))

ATOM_IDS = {
    b"_NET_CLIENT_LIST": 1001,
    b"_NET_WM_PID": 1002,
    b"_NET_WM_NAME": 1003,
    b"WM_NAME": 1004,
    b"UTF8_STRING": 1005,
}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))


class FakeXtst:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def XTestFakeButtonEvent(self, dpy, button, press, delay):
        self.calls.append(("button", int(button), int(press)))
        return 1

    def XTestFakeMotionEvent(self, dpy, screen, x, y, delay):
        self.calls.append(("motion", int(screen), int(x), int(y)))
        return 1

    def XTestFakeKeyEvent(self, dpy, code, press, delay):
        self.calls.append(("key", int(code), int(press)))
        return 1

    def buttons(self) -> list[tuple[int, int]]:
        return [(n, p) for kind, n, p in self.calls if kind == "button"]

    def keys(self) -> list[tuple[int, int]]:
        return [(n, p) for kind, n, p in self.calls if kind == "key"]


class FakeXlib:
    """The subset of Xlib VClicker uses, recording every call."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.keepalive: list = []
        self.focus = 900
        self.root = 0x42
        self.client_list: list[int] = []
        self.window_titles: dict[int, str] = {}
        self.pids: dict[int, int] = {}
        self.tree_children: list[int] = []
        self.keymap = bytearray(32)
        self.pointer = (10, 20)
        self.mask = 0
        self._prop_cb = PROP_CB(self._on_prop)
        self._tree_cb = TREE_CB(self._on_tree)
        self.XGetWindowProperty = self._prop_cb
        self.XQueryTree = self._tree_cb

    # -- display ---------------------------------------------------------- #
    def XOpenDisplay(self, name):
        return 1

    def XCloseDisplay(self, dpy):
        self.calls.append(("close",))

    def XDefaultRootWindow(self, dpy):
        return self.root

    def XFlush(self, dpy):
        self.calls.append(("flush",))

    def XSync(self, dpy, discard):
        self.calls.append(("sync",))

    def XInternAtom(self, dpy, name, only_if_exists):
        return ATOM_IDS.get(name, 999)

    # -- keyboard --------------------------------------------------------- #
    def XStringToKeysym(self, name):
        return sum(name) + 1000

    def XKeysymToKeycode(self, dpy, sym):
        return 8 if sym else 0

    def XKeysymToString(self, sym):
        return b"space"

    def XDisplayKeycodes(self, dpy, first, count):
        first._obj.value = 8
        count._obj.value = 200

    def XGetKeyboardMapping(self, dpy, first, count, per):
        per._obj.value = 0
        return None

    def XFree(self, ptr):
        self.calls.append(("free",))

    def XQueryKeymap(self, dpy, bitmap):
        bitmap._obj.raw = bytes(self.keymap)

    def XGetInputFocus(self, dpy, window, revert):
        window._obj.value = self.focus
        revert._obj.value = 2

    def XSetInputFocus(self, dpy, window, revert, stamp):
        self.calls.append(("focus", int(window)))

    def XRaiseWindow(self, dpy, window):
        self.calls.append(("raise", int(window)))

    # -- pointer ---------------------------------------------------------- #
    def XQueryPointer(self, dpy, window, root, child, rx, ry, wx, wy, mask):
        root._obj.value = self.root
        child._obj.value = 0
        rx._obj.value, ry._obj.value = self.pointer
        wx._obj.value, wy._obj.value = self.pointer
        mask._obj.value = self.mask
        return 1

    # -- property callbacks ------------------------------------------------ #
    def _on_prop(self, dpy, window, atom, long_off, long_len, delete, req_type,
                 actual_type, actual_format, nitems, bytes_after, prop):
        longs: list[int] | None = None
        text = b""
        if atom == ATOM_IDS[b"_NET_CLIENT_LIST"]:
            longs = [int(w) for w in self.client_list]
        elif atom == ATOM_IDS[b"_NET_WM_PID"]:
            longs = [int(self.pids.get(int(window), 0))]
        elif atom == ATOM_IDS[b"_NET_WM_NAME"]:
            text = self.window_titles.get(int(window), "").encode()
        elif atom == ATOM_IDS[b"WM_NAME"]:
            text = self.window_titles.get(int(window), "").encode("latin-1")

        bytes_after[0] = 0
        if longs is None and not text:
            actual_type[0] = 0
            actual_format[0] = 0
            nitems[0] = 0
            prop[0] = POINTER(c_ubyte)()
            return 1

        actual_type[0] = int(req_type or 1)
        if longs is not None:
            actual_format[0] = 32
            nitems[0] = len(longs)
            arr = (c_ulong * len(longs))(*longs)
            self.keepalive.append(arr)
            prop[0] = cast(arr, POINTER(c_ubyte))
        else:
            actual_format[0] = 8
            nitems[0] = len(text)
            buf = (c_ubyte * max(1, len(text))).from_buffer_copy(text.ljust(max(1, len(text)), b"\x00"))
            self.keepalive.append(buf)
            prop[0] = cast(buf, POINTER(c_ubyte))
        return 0

    def _on_tree(self, dpy, window, root_ret, parent_ret, children, count):
        root_ret[0] = self.root
        parent_ret[0] = 0
        if not self.tree_children:
            count[0] = 0
            children[0] = POINTER(c_ulong)()
            return 1
        arr = (c_ulong * len(self.tree_children))(*self.tree_children)
        self.keepalive.append(arr)
        count[0] = len(self.tree_children)
        children[0] = cast(arr, POINTER(c_ulong))
        return 1


def make_backend() -> tuple[X11Backend, FakeXlib, FakeXtst]:
    xlib = FakeXlib()
    xtst = FakeXtst()
    backend = X11Backend.__new__(X11Backend)
    backend._xlib = xlib
    backend._xtst = xtst
    backend._dpy = 1
    backend._root = xlib.root
    backend._keycodes = {"space": 65, "a": 38, "f8": 74, "shift": 50}
    backend._name_by_keycode = {65: "space", 38: "a"}
    backend.caps = Capabilities(clicking=True, key_send=True, targeted_hold=True,
                                window_list=True, recording=True, recording_quality="fake",
                                hotkeys=True, scroll=True)
    backend.name = "Linux · X11 / XTest"
    backend.os_name = "linux"
    backend.needs_permissions_hint = ""
    return backend, xlib, xtst


def test_mouse() -> None:
    backend, xlib, xtst = make_backend()

    backend.build_click("right").fire()
    check("right click uses X11 button 3", xtst.buttons() == [(3, 1), (3, 0)], str(xtst.buttons()))

    xtst.calls.clear()
    backend.build_click("middle", burst=3).fire()
    check("burst sends 3 press/release pairs", len(xtst.buttons()) == 6, str(xtst.buttons()))

    xtst.calls.clear()
    backend.build_click("left", double=True).fire()
    check("double click sends 4 events", len(xtst.buttons()) == 4)

    xtst.calls.clear()
    backend.build_click("left", x=300, y=400).fire()
    check("fixed point moves before clicking",
          bool(xtst.calls) and xtst.calls[0] == ("motion", -1, 300, 400), str(xtst.calls[:2]))

    xtst.calls.clear()
    backend.build_click("left").fire()
    check("cursor clicks do not move the pointer",
          all(call[0] != "motion" for call in xtst.calls))

    xtst.calls.clear()
    backend.scroll(3)
    check("scroll up uses button 4", xtst.buttons() == [(4, 1), (4, 0)] * 3, str(xtst.buttons()[:4]))

    xtst.calls.clear()
    backend.scroll(-2)
    check("scroll down uses button 5", xtst.buttons() == [(5, 1), (5, 0)] * 2)

    xtst.calls.clear()
    backend.mouse_down("left")
    backend.mouse_up("left")
    check("press/hold events map to button 1", xtst.buttons() == [(1, 1), (1, 0)])


def test_keys() -> None:
    backend, xlib, xtst = make_backend()
    backend.key_down("space")
    backend.key_up("space")
    check("key press/release uses the keysym keycode", xtst.keys() == [(65, 1), (65, 0)],
          str(xtst.keys()))

    xtst.calls.clear()
    backend.key_down("unknown-key")
    check("unknown keys are ignored", xtst.keys() == [])

    xlib.keymap[65 // 8] |= 1 << (65 % 8)
    check("is_key_down reads the polled bitmap", backend.is_key_down("space") is True)
    xlib.keymap[65 // 8] = 0
    check("is_key_down clears when released", backend.is_key_down("space") is False)


def test_window_hold() -> None:
    backend, xlib, xtst = make_backend()
    windows = [WindowInfo(11, "Game", "game", 1), WindowInfo(12, "Chat", "chat", 2)]

    backend.hold_keys(["space", "a"], windows)
    focus_calls = [call for call in xlib.calls if call[0] == "focus"]
    check("each target window is focused", focus_calls[:2] == [("focus", 11), ("focus", 12)],
          str(focus_calls))
    check("keys are pressed on every window", xtst.keys() == [(65, 1), (38, 1)] * 2,
          str(xtst.keys()))
    check("focus returns to the previous window", focus_calls[-1] == ("focus", 900),
          str(focus_calls))

    xtst.calls.clear()
    xlib.calls.clear()
    backend.release_keys(["space", "a"], windows)
    check("release sends key-ups in reverse order",
          xtst.keys() == [(38, 0), (65, 0)] * 2, str(xtst.keys()))

    xtst.calls.clear()
    xlib.calls.clear()
    backend.hold_keys(["space"])
    check("global hold does not touch focus",
          xtst.keys() == [(65, 1)] and not any(c[0] in ("focus", "raise") for c in xlib.calls),
          str(xlib.calls))


def test_windows() -> None:
    backend, xlib, xtst = make_backend()
    xlib.client_list = [11, 12, 13, 12]
    xlib.window_titles = {11: "World of Warcraft", 12: "Discord", 13: ""}
    xlib.pids = {11: os.getpid(), 12: 999999}

    windows = backend.list_windows()
    names = [w.title for w in windows]
    check("client list is read and de-duplicated", len(windows) == 2, str(names))
    check("titles decode from _NET_WM_NAME", "World of Warcraft" in names, str(names))
    check("untitled windows are skipped", "" not in names)
    check("pid resolves to a process name", any(w.process for w in windows),
          str([w.process for w in windows]))

    xlib.client_list = []
    xlib.window_titles = {21: "Fallback window"}
    xlib.tree_children = [21]
    fallback = backend.list_windows()
    check("falls back to XQueryTree without a window manager",
          [w.title for w in fallback] == ["Fallback window"], str(fallback))

    xlib.pointer = (640, 480)
    check("cursor position is read from the server", backend.cursor_pos() == (640, 480))


def _pump(app, seconds: float) -> None:
    """Deliver queued monitor signals (they hop threads through Qt)."""
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.004)


def test_monitor() -> None:
    backend, xlib, xtst = make_backend()
    xlib.keymap[65 // 8] |= 1 << (65 % 8)
    xlib.mask = 1 << 8  # Button1Mask
    monitor = X11Monitor(backend)
    monitor._dpy = 1

    events: list[tuple] = []
    monitored: list[tuple] = []
    monitor.connect_event(lambda event: events.append((event.kind, event.key, event.button)))
    monitor.add_listener(lambda event: monitored.append((event.kind, event.x, event.y)))

    from PySide6.QtCore import QCoreApplication

    qt = QCoreApplication.instance() or QCoreApplication([])
    monitor.start()
    _pump(qt, 0.08)
    xlib.keymap[65 // 8] = 0
    xlib.mask = 0
    xlib.pointer = (700, 500)
    _pump(qt, 0.08)
    monitor.stop()
    _pump(qt, 0.05)

    kinds = [event[0] for event in events]
    raw_kinds = [event[0] for event in monitored]
    check("monitor reports the key being pressed", "key_down" in kinds, str(kinds))
    check("monitor reports the key release", "key_up" in kinds, str(kinds))
    check("monitor reports button press/release",
          "mouse_down" in kinds and "mouse_up" in kinds, str(kinds))
    check("raw listener sees pointer movement", "move" in raw_kinds, str(raw_kinds))
    check("pointer coordinates come from the server",
          (700, 500) in [(x, y) for kind, x, y in monitored if kind == "move"],
          str([(x, y) for kind, x, y in monitored if kind == "move"][-3:]))


def main() -> int:
    test_mouse()
    test_keys()
    test_window_hold()
    test_windows()
    test_monitor()

    failures = [row for row in RESULTS if not row[1]]
    print()
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} X11 backend checks passed")
    for name, _ok, detail in failures:
        print(f"  failed: {name} ({detail})")
    code = 1 if failures else 0
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
