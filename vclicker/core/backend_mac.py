"""macOS backend (experimental) using CoreGraphics events and polling capture.

Requires Accessibility permission for the app/terminal running VClicker:
System Settings -> Privacy & Security -> Accessibility.
"""

from __future__ import annotations

import ctypes
import threading
import time

from .. import keys as keymap
from .backend_base import Backend, BackendUnavailable, Capabilities, ClickAction, InputEvent, WindowInfo
from .monitor import BaseMonitor

CGEventTapLocation = ctypes.c_uint32
CGEventType = ctypes.c_uint32
CGMouseButton = ctypes.c_uint32
CGScrollEventUnit = ctypes.c_uint32

K_CG_HID_EVENT_TAP = 0
K_CG_SCROLL_EVENT_UNIT_LINE = 1

EVENT_LEFT_DOWN = 1
EVENT_LEFT_UP = 2
EVENT_RIGHT_DOWN = 3
EVENT_RIGHT_UP = 4
EVENT_MOUSE_MOVED = 5
EVENT_KEY_DOWN = 10
EVENT_KEY_UP = 11
EVENT_SCROLL = 22
EVENT_OTHER_DOWN = 25
EVENT_OTHER_UP = 26

BUTTON_UUIDS = {
    "left": (EVENT_LEFT_DOWN, EVENT_LEFT_UP, 0),
    "right": (EVENT_RIGHT_DOWN, EVENT_RIGHT_UP, 1),
    "middle": (EVENT_OTHER_DOWN, EVENT_OTHER_UP, 2),
}


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def _load():
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    except OSError as exc:
        raise BackendUnavailable(f"CoreGraphics unavailable: {exc}") from exc

    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = (ctypes.c_void_p, CGEventType, CGPoint, CGMouseButton)
    cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    cg.CGEventCreateKeyboardEvent.argtypes = (ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool)
    cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
    cg.CGEventCreateScrollWheelEvent.argtypes = (
        ctypes.c_void_p, CGScrollEventUnit, ctypes.c_uint32, ctypes.c_int32)
    cg.CGEventPost.argtypes = (CGEventTapLocation, ctypes.c_void_p)
    cg.CGEventCreate.restype = ctypes.c_void_p
    cg.CGEventCreate.argtypes = (ctypes.c_void_p,)
    cg.CGEventGetLocation.restype = CGPoint
    cg.CGEventGetLocation.argtypes = (ctypes.c_void_p,)
    cg.CGWarpMouseCursorPosition.argtypes = (CGPoint,)
    cg.CGEventSourceKeyState.restype = ctypes.c_bool
    cg.CGEventSourceKeyState.argtypes = (ctypes.c_int32, ctypes.c_uint16)
    cg.CGEventSourceButtonState.restype = ctypes.c_bool
    cg.CGEventSourceButtonState.argtypes = (ctypes.c_int32, CGMouseButton)
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    return cg, cf


class MacBackend(Backend):
    os_name = "darwin"
    name = "macOS · CoreGraphics"
    needs_permissions_hint = (
        "Grant Accessibility permission (System Settings → Privacy & Security → Accessibility) "
        "so VClicker can send and capture input."
    )

    def __init__(self) -> None:
        super().__init__()
        self._cg, self._cf = _load()
        self.caps = Capabilities(
            clicking=True,
            key_send=True,
            targeted_hold=False,
            window_list=False,
            recording=True,
            recording_quality="CoreGraphics polling (8 ms resolution)",
            hotkeys=True,
            scroll=True,
            notes=[
                "macOS support is experimental: multi-window key-hold is Windows-only.",
                "Accessibility permission is required for input injection.",
                "System Integrity Protection can block input into some apps.",
            ],
        )

    # -- mouse ------------------------------------------------------------- #
    def _post_mouse(self, ident: str, down: bool, x: int, y: int) -> None:
        down_type, up_type, button = BUTTON_UUIDS.get(ident, BUTTON_UUIDS["left"])
        event = self._cg.CGEventCreateMouseEvent(
            None, down_type if down else up_type, CGPoint(float(x), float(y)), button)
        if event:
            self._cg.CGEventPost(K_CG_HID_EVENT_TAP, event)
            self._cf.CFRelease(event)

    def build_click(self, button: str = "left", double: bool = False,
                    x: int | None = None, y: int | None = None,
                    burst: int = 1) -> ClickAction:
        cg = self._cg
        cf = self._cf
        down_type, up_type, btn = BUTTON_UUIDS.get(button, BUTTON_UUIDS["left"])
        repeats = (2 if double else 1) * max(1, int(burst))
        pos = CGPoint(float(x), float(y)) if x is not None and y is not None else None

        def fire() -> None:
            px, py = (pos.x, pos.y) if pos is not None else self._current()
            for _ in range(repeats):
                for event_type in (down_type, up_type):
                    event = cg.CGEventCreateMouseEvent(None, event_type, CGPoint(px, py), btn)
                    if event:
                        cg.CGEventPost(K_CG_HID_EVENT_TAP, event)
                        cf.CFRelease(event)

        return ClickAction(fire, (2 if double else 1) * max(1, int(burst)))

    def _current(self) -> tuple[float, float]:
        event = self._cg.CGEventCreate(None)
        if not event:
            return (0.0, 0.0)
        try:
            point = self._cg.CGEventGetLocation(event)
            return (point.x, point.y)
        finally:
            self._cf.CFRelease(event)

    def mouse_down(self, button: str = "left") -> None:
        x, y = self._current()
        self._post_mouse(button, True, int(x), int(y))

    def mouse_up(self, button: str = "left") -> None:
        x, y = self._current()
        self._post_mouse(button, False, int(x), int(y))

    def move_to(self, x: int, y: int) -> None:
        self._cg.CGWarpMouseCursorPosition(CGPoint(float(x), float(y)))

    def cursor_pos(self) -> tuple[int, int]:
        x, y = self._current()
        return (int(x), int(y))

    def scroll(self, delta: int, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self.move_to(int(x), int(y))
        event = self._cg.CGEventCreateScrollWheelEvent(
            None, K_CG_SCROLL_EVENT_UNIT_LINE, 1, int(delta))
        if event:
            self._cg.CGEventPost(K_CG_HID_EVENT_TAP, event)
            self._cf.CFRelease(event)

    # -- keyboard ---------------------------------------------------------- #
    def _post_key(self, key: str, down: bool) -> None:
        info = keymap.info(key)
        if info.mac is None:
            return
        event = self._cg.CGEventCreateKeyboardEvent(None, info.mac, down)
        if event:
            self._cg.CGEventPost(K_CG_HID_EVENT_TAP, event)
            self._cf.CFRelease(event)

    def key_down(self, key: str) -> None:
        self._post_key(key, True)

    def key_up(self, key: str) -> None:
        self._post_key(key, False)

    def is_key_down(self, key: str) -> bool:
        info = keymap.info(key)
        if info.mac is None:
            return False
        return bool(self._cg.CGEventSourceKeyState(0, info.mac))

    def list_windows(self) -> list[WindowInfo]:
        return []

    def screen_size(self) -> tuple[int, int]:
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                return (geo.width(), geo.height())
        except Exception:
            pass
        return (1920, 1080)

    def create_monitor(self):
        return MacPollMonitor(self)

    def describe(self) -> str:
        return "macOS · CoreGraphics (experimental)"


class MacPollMonitor(BaseMonitor):
    INTERVAL = 0.008

    def __init__(self, backend: MacBackend) -> None:
        super().__init__()
        self._backend = backend
        self._thread: threading.Thread | None = None
        self._keys: dict[int, str] = {}
        for name, info in keymap.KEYS.items():
            if info.mac is not None:
                self._keys.setdefault(info.mac, name)
        self._pressed: set[str] = set()
        self._buttons: set[str] = set()
        self._last_pos = (-1, -1)

    def start(self) -> bool:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="VClickerMacPoll", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        super().stop()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        cg = self._backend._cg
        while self._running:
            try:
                pressed: set[str] = set()
                for code, name in self._keys.items():
                    if cg.CGEventSourceKeyState(0, code):
                        pressed.add(name)
                if pressed != self._pressed:
                    for name in pressed - self._pressed:
                        self._emit_raw(InputEvent(kind="key_down", key=name))
                    for name in self._pressed - pressed:
                        self._emit_raw(InputEvent(kind="key_up", key=name))
                    self._pressed = pressed

                buttons: set[str] = set()
                for name, button in (("left", 0), ("right", 1), ("middle", 2)):
                    if cg.CGEventSourceButtonState(0, button):
                        buttons.add(name)
                x, y = self._backend.cursor_pos()
                if buttons != self._buttons:
                    for name in buttons - self._buttons:
                        self._emit_raw(InputEvent(kind="mouse_down", button=name, x=x, y=y))
                    for name in self._buttons - buttons:
                        self._emit_raw(InputEvent(kind="mouse_up", button=name, x=x, y=y))
                    self._buttons = buttons
                if (x, y) != self._last_pos:
                    self._last_pos = (x, y)
                    self._emit_raw(InputEvent(kind="move", x=x, y=y))
            except Exception:
                break
            time.sleep(self.INTERVAL)
