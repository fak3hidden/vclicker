"""Linux/X11 backend using XTest for input and XQueryKeymap polling for capture.

No extra packages: libX11/libXtst are loaded through ctypes.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p

from .. import keys as keymap
from .backend_base import Backend, BackendUnavailable, Capabilities, ClickAction, InputEvent, WindowInfo
from .monitor import BaseMonitor

XA_WINDOW = 33
XA_ATOM = 4
XA_CARDINAL = 6
PROP_MODE_REPLACE = 0
ANY_PROPERTY_TYPE = 0

BUTTON_MASKS = {
    1: (1 << 8, "left"),
    2: (1 << 9, "middle"),
    3: (1 << 10, "right"),
}

SCROLL_UP = 4
SCROLL_DOWN = 5


def _load_libs():
    try:
        xlib = ctypes.CDLL("libX11.so.6")
    except OSError as exc:  # pragma: no cover - depends on host
        raise BackendUnavailable(f"libX11 not found: {exc}") from exc
    try:
        xtst = ctypes.CDLL("libXtst.so.6")
    except OSError as exc:  # pragma: no cover
        raise BackendUnavailable(f"libXtst not found: {exc}") from exc

    xlib.XOpenDisplay.restype = c_void_p
    xlib.XOpenDisplay.argtypes = (c_char_p,)
    xlib.XCloseDisplay.argtypes = (c_void_p,)
    xlib.XDefaultRootWindow.restype = c_ulong
    xlib.XDefaultRootWindow.argtypes = (c_void_p,)
    xlib.XFlush.argtypes = (c_void_p,)
    xlib.XSync.argtypes = (c_void_p, c_int)
    xlib.XStringToKeysym.restype = c_ulong
    xlib.XStringToKeysym.argtypes = (c_char_p,)
    xlib.XKeysymToKeycode.restype = c_ubyte
    xlib.XKeysymToKeycode.argtypes = (c_void_p, c_ulong)
    xlib.XKeysymToString.restype = c_char_p
    xlib.XKeysymToString.argtypes = (c_ulong,)
    xlib.XDisplayKeycodes.argtypes = (c_void_p, ctypes.POINTER(c_int), ctypes.POINTER(c_int))
    xlib.XGetKeyboardMapping.restype = ctypes.POINTER(c_ulong)
    xlib.XGetKeyboardMapping.argtypes = (c_void_p, c_ubyte, c_int, ctypes.POINTER(c_int))
    xlib.XFree.argtypes = (c_void_p,)
    xlib.XQueryKeymap.argtypes = (c_void_p, c_void_p)
    xlib.XQueryPointer.restype = c_int
    xlib.XQueryPointer.argtypes = (
        c_void_p, c_ulong, ctypes.POINTER(c_ulong), ctypes.POINTER(c_ulong),
        ctypes.POINTER(c_int), ctypes.POINTER(c_int), ctypes.POINTER(c_int),
        ctypes.POINTER(c_int), ctypes.POINTER(c_uint))
    xlib.XGetInputFocus.argtypes = (c_void_p, ctypes.POINTER(c_ulong), ctypes.POINTER(c_int))
    xlib.XSetInputFocus.argtypes = (c_void_p, c_ulong, c_int, c_ulong)
    xlib.XRaiseWindow.argtypes = (c_void_p, c_ulong)
    xlib.XInternAtom.restype = c_ulong
    xlib.XInternAtom.argtypes = (c_void_p, c_char_p, c_int)
    xlib.XGetWindowProperty.restype = c_int
    xlib.XGetWindowProperty.argtypes = (
        c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
        ctypes.POINTER(c_ulong), ctypes.POINTER(c_int), ctypes.POINTER(c_ulong),
        ctypes.POINTER(c_ulong), ctypes.POINTER(ctypes.POINTER(c_ubyte)))
    xlib.XQueryTree.restype = c_int
    xlib.XQueryTree.argtypes = (
        c_void_p, c_ulong, ctypes.POINTER(c_ulong), ctypes.POINTER(c_ulong),
        ctypes.POINTER(ctypes.POINTER(c_ulong)), ctypes.POINTER(c_uint))

    xtst.XTestFakeButtonEvent.argtypes = (c_void_p, c_uint, c_int, c_ulong)
    xtst.XTestFakeButtonEvent.restype = c_int
    xtst.XTestFakeMotionEvent.argtypes = (c_void_p, c_int, c_int, c_int, c_ulong)
    xtst.XTestFakeMotionEvent.restype = c_int
    xtst.XTestFakeKeyEvent.argtypes = (c_void_p, c_uint, c_int, c_ulong)
    xtst.XTestFakeKeyEvent.restype = c_int
    return xlib, xtst


class X11Backend(Backend):
    os_name = "linux"
    name = "Linux · X11 / XTest"
    needs_permissions_hint = "X11 session required (Wayland needs XWayland or a native backend)."

    def __init__(self) -> None:
        super().__init__()
        self._xlib, self._xtst = _load_libs()
        self._dpy = self._xlib.XOpenDisplay(None)
        if not self._dpy:
            raise BackendUnavailable("Could not open X display ($DISPLAY is not reachable).")
        self._root = int(self._xlib.XDefaultRootWindow(self._dpy))
        self._keycodes: dict[str, int] = {}
        self._name_by_keycode: dict[int, str] = {}
        self._build_keymaps()
        self.caps = Capabilities(
            clicking=True,
            key_send=True,
            targeted_hold=True,
            window_list=True,
            recording=True,
            recording_quality="X11 polling (2 ms resolution)",
            hotkeys=True,
            scroll=True,
            notes=[
                "Multi-window key-hold focuses each selected window in turn (X11 has no safe background key delivery).",
                "Wayland sessions can only inject through XWayland windows.",
                "Mouse wheel is not captured while recording on X11.",
            ],
        )

    # -- internals --------------------------------------------------------- #
    def _build_keymaps(self) -> None:
        for name, info in keymap.KEYS.items():
            sym_name = info.x11
            if not sym_name:
                continue
            sym = self._xlib.XStringToKeysym(sym_name.encode())
            if not sym:
                continue
            code = int(self._xlib.XKeysymToKeycode(self._dpy, sym))
            if code:
                self._keycodes.setdefault(name, code)

        min_code, max_code = c_int(), c_int()
        self._xlib.XDisplayKeycodes(self._dpy, ctypes.byref(min_code), ctypes.byref(max_code))
        count = max(1, max_code.value - min_code.value + 1)
        per = c_int()
        syms = self._xlib.XGetKeyboardMapping(self._dpy, min_code.value, count, ctypes.byref(per))
        if not syms:
            return
        try:
            stride = per.value or 1
            for index in range(count):
                sym = int(syms[index * stride])
                if not sym:
                    continue
                raw = self._xlib.XKeysymToString(sym)
                if not raw:
                    continue
                lowered = raw.decode(errors="ignore").lower()
                name = keymap.X11_TO_NAME.get(lowered)
                if name is None and lowered in keymap.KEYS:
                    name = lowered
                if name:
                    self._name_by_keycode.setdefault(min_code.value + index, name)
        finally:
            self._xlib.XFree(syms)

    def _keycode(self, key: str) -> int:
        return self._keycodes.get(key, 0)

    # -- mouse ------------------------------------------------------------- #
    def build_click(self, button: str = "left", double: bool = False,
                    x: int | None = None, y: int | None = None,
                    burst: int = 1) -> ClickAction:
        dpy = self._dpy
        number = keymap.MOUSE_BUTTONS.get(button, 1)
        repeats = (2 if double else 1) * max(1, int(burst))
        fake_button = self._xtst.XTestFakeButtonEvent
        fake_motion = self._xtst.XTestFakeMotionEvent
        flush = self._xlib.XFlush
        pos = (int(x), int(y)) if x is not None and y is not None else None

        def fire() -> None:
            if pos is not None:
                fake_motion(dpy, -1, pos[0], pos[1], 0)
            for _ in range(repeats):
                fake_button(dpy, number, 1, 0)
                fake_button(dpy, number, 0, 0)
            flush(dpy)

        return ClickAction(fire, (2 if double else 1) * max(1, int(burst)))

    def mouse_down(self, button: str = "left") -> None:
        self._xtst.XTestFakeButtonEvent(self._dpy, keymap.MOUSE_BUTTONS.get(button, 1), 1, 0)
        self._xlib.XFlush(self._dpy)

    def mouse_up(self, button: str = "left") -> None:
        self._xtst.XTestFakeButtonEvent(self._dpy, keymap.MOUSE_BUTTONS.get(button, 1), 0, 0)
        self._xlib.XFlush(self._dpy)

    def move_to(self, x: int, y: int) -> None:
        self._xtst.XTestFakeMotionEvent(self._dpy, -1, int(x), int(y), 0)
        self._xlib.XFlush(self._dpy)

    def cursor_pos(self) -> tuple[int, int]:
        root_ret, child_ret = c_ulong(), c_ulong()
        rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
        mask = c_uint()
        self._xlib.XQueryPointer(self._dpy, self._root, ctypes.byref(root_ret),
                                 ctypes.byref(child_ret), ctypes.byref(rx), ctypes.byref(ry),
                                 ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
        return (rx.value, ry.value)

    def scroll(self, delta: int, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self.move_to(int(x), int(y))
        button = SCROLL_UP if delta > 0 else SCROLL_DOWN
        for _ in range(max(1, abs(int(delta)))):
            self._xtst.XTestFakeButtonEvent(self._dpy, button, 1, 0)
            self._xtst.XTestFakeButtonEvent(self._dpy, button, 0, 0)
        self._xlib.XFlush(self._dpy)

    # -- keyboard ---------------------------------------------------------- #
    def key_down(self, key: str) -> None:
        code = self._keycode(key)
        if code:
            self._xtst.XTestFakeKeyEvent(self._dpy, code, 1, 0)
            self._xlib.XFlush(self._dpy)

    def key_up(self, key: str) -> None:
        code = self._keycode(key)
        if code:
            self._xtst.XTestFakeKeyEvent(self._dpy, code, 0, 0)
            self._xlib.XFlush(self._dpy)

    def hold_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        if not windows:
            for key in keys:
                self.key_down(key)
            return
        previous = self._save_focus()
        for window in windows:
            self._focus(window.ident)
            for key in keys:
                code = self._keycode(key)
                if code:
                    self._xtst.XTestFakeKeyEvent(self._dpy, code, 1, 0)
        self._xlib.XFlush(self._dpy)
        self._restore_focus(previous)

    def release_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        if not windows:
            for key in reversed(keys):
                self.key_up(key)
            return
        previous = self._save_focus()
        for window in windows:
            self._focus(window.ident)
            for key in reversed(keys):
                code = self._keycode(key)
                if code:
                    self._xtst.XTestFakeKeyEvent(self._dpy, code, 0, 0)
        self._xlib.XFlush(self._dpy)
        self._restore_focus(previous)

    def _save_focus(self) -> int:
        win = c_ulong()
        revert = c_int()
        self._xlib.XGetInputFocus(self._dpy, ctypes.byref(win), ctypes.byref(revert))
        return int(win.value)

    def _restore_focus(self, ident: int) -> None:
        if not ident:
            return
        self._xlib.XSetInputFocus(self._dpy, ident, 2, 0)
        self._xlib.XFlush(self._dpy)

    def _focus(self, ident: int) -> None:
        try:
            self._xlib.XRaiseWindow(self._dpy, ident)
        except Exception:
            pass
        self._xlib.XSetInputFocus(self._dpy, ident, 2, 0)
        self._xlib.XSync(self._dpy, 0)

    def is_key_down(self, key: str) -> bool:
        code = self._keycode(key)
        if not code:
            return False
        bitmap = (ctypes.c_char * 32)()
        self._xlib.XQueryKeymap(self._dpy, ctypes.byref(bitmap))
        value = bitmap.raw[code // 8]
        return bool(value & (1 << (code % 8)))

    # -- windows ----------------------------------------------------------- #
    def _atom(self, name: str) -> int:
        return int(self._xlib.XInternAtom(self._dpy, name.encode(), False))

    def _prop_bytes(self, window: int, atom: int, prop_type: int = ANY_PROPERTY_TYPE) -> bytes:
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        data = ctypes.POINTER(c_ubyte)()
        status = self._xlib.XGetWindowProperty(
            self._dpy, window, atom, 0, 8192, False, prop_type,
            ctypes.byref(actual_type), ctypes.byref(actual_format), ctypes.byref(nitems),
            ctypes.byref(bytes_after), ctypes.byref(data))
        if status != 0 or not data:
            return b""
        try:
            if actual_format.value == 8:
                return ctypes.string_at(data, nitems.value)
            if actual_format.value == 16:
                return ctypes.string_at(data, nitems.value * 2)
            return b""
        finally:
            self._xlib.XFree(ctypes.cast(data, c_void_p))

    def _prop_longs(self, window: int, atom: int, prop_type: int = ANY_PROPERTY_TYPE) -> list[int]:
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        data = ctypes.POINTER(c_ubyte)()
        status = self._xlib.XGetWindowProperty(
            self._dpy, window, atom, 0, 8192, False, prop_type,
            ctypes.byref(actual_type), ctypes.byref(actual_format), ctypes.byref(nitems),
            ctypes.byref(bytes_after), ctypes.byref(data))
        if status != 0 or not data:
            return []
        try:
            if actual_format.value == 32:
                values = ctypes.cast(data, ctypes.POINTER(c_ulong))
                return [int(values[index]) for index in range(nitems.value)]
            if actual_format.value == 8:
                raw = ctypes.string_at(data, nitems.value)
                return [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw) - 3, 4)]
            return []
        finally:
            self._xlib.XFree(ctypes.cast(data, c_void_p))

    def _window_title(self, window: int) -> str:
        raw = self._prop_bytes(window, self._atom("_NET_WM_NAME"), self._atom("UTF8_STRING"))
        if raw:
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
        raw = self._prop_bytes(window, self._atom("WM_NAME"))
        return raw.split(b"\x00", 1)[0].decode("latin-1", errors="ignore").strip()

    def _window_pid(self, window: int) -> int:
        values = self._prop_longs(window, self._atom("_NET_WM_PID"), XA_CARDINAL)
        return values[0] if values else 0

    def list_windows(self) -> list[WindowInfo]:
        results: list[WindowInfo] = []
        idents = self._prop_longs(self._root, self._atom("_NET_CLIENT_LIST"), XA_WINDOW)
        if not idents:
            root_ret, parent_ret = c_ulong(), c_ulong()
            children = ctypes.POINTER(c_ulong)()
            nchildren = c_uint()
            if self._xlib.XQueryTree(self._dpy, self._root, ctypes.byref(root_ret),
                                     ctypes.byref(parent_ret), ctypes.byref(children),
                                     ctypes.byref(nchildren)):
                try:
                    for index in range(nchildren.value):
                        idents.append(int(children[index]))
                finally:
                    if children:
                        self._xlib.XFree(ctypes.cast(children, c_void_p))

        seen: set[int] = set()
        for ident in idents:
            if not ident or ident in seen:
                continue
            seen.add(ident)
            title = self._window_title(ident)
            if not title:
                continue
            pid = self._window_pid(ident)
            process = ""
            if pid:
                try:
                    with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as fh:
                        process = fh.read().strip()
                except OSError:
                    process = ""
            results.append(WindowInfo(ident, title, process, pid))
        results.sort(key=lambda w: (w.process.lower(), w.title.lower()))
        return results

    def screen_size(self) -> tuple[int, int]:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            return (geo.width(), geo.height())
        return (1920, 1080)

    def create_monitor(self):
        return X11Monitor(self)

    def describe(self) -> str:
        return "Linux · X11 XTest + 2 ms polling"


# --------------------------------------------------------------------------- #
#  Polling monitor
# --------------------------------------------------------------------------- #
class X11Monitor(BaseMonitor):
    """Key/button capture by polling the X server (2 ms)."""

    POLL_INTERVAL = 0.002

    def __init__(self, backend: X11Backend) -> None:
        super().__init__()
        self._backend = backend
        self._thread: threading.Thread | None = None
        self._last_buttons: set[str] = set()
        self._last_pos = (-1, -1)

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            self._running = True
            return True
        self._running = True
        self._thread = threading.Thread(target=self._run, name="VClickerX11Poll", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        super().stop()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        xlib = self._backend._xlib
        dpy = self._backend._dpy
        root = self._backend._root
        names = self._backend._name_by_keycode
        bitmap = (ctypes.c_char * 32)()
        pressed: set[int] = set()
        rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
        root_ret, child_ret = c_ulong(), c_ulong()
        mask = c_uint()

        while self._running:
            try:
                xlib.XQueryKeymap(dpy, ctypes.byref(bitmap))
                raw = bitmap.raw
                current: set[int] = set()
                for index, byte in enumerate(raw[:32]):
                    if not byte:
                        continue
                    for bit in range(8):
                        if byte & (1 << bit):
                            current.add(index * 8 + bit)
                if current != pressed:
                    for code in current - pressed:
                        name = names.get(code)
                        if name:
                            self._emit_raw(InputEvent(kind="key_down", key=name))
                    for code in pressed - current:
                        name = names.get(code)
                        if name:
                            self._emit_raw(InputEvent(kind="key_up", key=name))
                    pressed = current

                xlib.XQueryPointer(dpy, root, ctypes.byref(root_ret), ctypes.byref(child_ret),
                                   ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx),
                                   ctypes.byref(wy), ctypes.byref(mask))
                pos = (rx.value, ry.value)
                if pos != self._last_pos:
                    self._last_pos = pos
                    self._emit_raw(InputEvent(kind="move", x=pos[0], y=pos[1]))

                buttons: set[str] = set()
                for number, (bit, name) in BUTTON_MASKS.items():
                    if mask.value & bit:
                        buttons.add(name)
                if buttons != self._last_buttons:
                    for name in buttons - self._last_buttons:
                        self._emit_raw(InputEvent(kind="mouse_down", button=name,
                                                  x=pos[0], y=pos[1]))
                    for name in self._last_buttons - buttons:
                        self._emit_raw(InputEvent(kind="mouse_up", button=name,
                                                  x=pos[0], y=pos[1]))
                    self._last_buttons = buttons
            except Exception:
                break
            time.sleep(self.POLL_INTERVAL)
