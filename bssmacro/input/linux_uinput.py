"""Native Wayland input via the kernel's ``uinput`` interface (no X needed).

Wayland, by design, does not let clients inject input into other clients —
XTest is an X11-only trick. The one input path that works on *every* Wayland
compositor (GNOME, KDE, sway, Hyprland, …) is a **virtual input device**
created through ``/dev/uinput``: the kernel sees it as real hardware and the
compositor processes its events like any keyboard/mouse.

This module needs **zero extra Python packages** — it drives ``/dev/uinput``
directly with ``os.write`` + ``fcntl.ioctl``. It only needs the kernel module
and write permission::

    sudo modprobe uinput
    # one-time udev rule so the device is writable without root:
    echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \
        | sudo tee /etc/udev/rules.d/70-uinput.rules
    sudo udevadm control --reload && sudo udevadm trigger
    sudo usermod -aG input "$USER"     # then log out/in

The virtual device presents itself as a touchscreen-style absolute pointer
(ABS_X/ABS_Y + BTN_TOUCH, INPUT_PROP_DIRECT) *plus* a keyboard. Taps land at
exact screen coordinates on all compositors and WASD reaches the game as
regular key events — which is everything the macro needs.

Compositor notes
----------------
* Hover-only pointer movement is not guaranteed for touch devices (a real
  touchscreen does not move the cursor on hover). The macro never relies on
  hover: movement is keyboard-driven and every click passes explicit x/y.
* If your compositor mangles absolute positions, install ``ydotool`` with its
  daemon (``ydotoold``) and set ``input_kind = "ydotool"`` — see
  :mod:`bssmacro.input.ydotool`.
"""

from __future__ import annotations

import os
import struct
import threading
import time
from typing import Optional

from ..capture.window import find_window_any, focus_window

# --- kernel constants (linux/uinput.h + linux/input-event-codes.h) ----------
UI_SET_EVBIT = 0x40045564       # _IOW('U', 100, int)
UI_SET_KEYBIT = 0x40045565      # _IOW('U', 101, int)
UI_SET_RELBIT = 0x40045566      # _IOW('U', 102, int)
UI_SET_ABSBIT = 0x40045567      # _IOW('U', 103, int)
UI_SET_PROPBIT = 0x4004556D     # _IOW('U', 109, int)
UI_DEV_CREATE = 0x00005565      # _IO('U', 101)
UI_DEV_DESTROY = 0x00005566     # _IO('U', 102)

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
SYN_REPORT = 0
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
ABS_X, ABS_Y = 0, 1
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
BTN_TOUCH, BTN_TOOL_PEN = 0x14A, 0x140
INPUT_PROP_DIRECT = 0x02
BUS_USB = 0x03

ABS_MAX_COORD = 32767           # virtual digitizer resolution
DEFAULT_DEVICE = "/dev/uinput"

# EV_KEY codes for every key name the macro's config can reference. These are
# the same numeric codes ``ydotool key`` accepts, so the ydotool adapter
# reuses this table.
UINPUT_KEY_CODES: dict[str, int] = {
    "esc": 1, "escape": 1,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6,
    "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "minus": 12, "equal": 13, "backspace": 14, "tab": 15,
    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21,
    "u": 22, "i": 23, "o": 24, "p": 25,
    "leftbrace": 26, "rightbrace": 27, "enter": 28, "return": 28,
    "leftctrl": 29, "ctrl": 29, "a": 30, "s": 31, "d": 32,
    "f": 33, "g": 34, "h": 35, "j": 36, "k": 37, "l": 38,
    "semicolon": 39, "apostrophe": 40, "grave": 41,
    "leftshift": 42, "shift": 42, "backslash": 43,
    "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
    "comma": 51, "dot": 52, "period": 52, "slash": 53,
    "rightshift": 54, "leftalt": 56, "alt": 56, "space": 57,
    "capslock": 58,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    "up": 103, "left": 105, "right": 106, "down": 108,
    "kp1": 79, "kp2": 80, "kp3": 81, "kp4": 75, "kp6": 77,
    "kp7": 71, "kp8": 72, "kp9": 73, "kp0": 82,
}

_BUTTON_CODES = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}

# uinput_user_dev: name[80] + input_id(4*u16) + ff_effects_max(u32)
#                 + absmax/absmin/absfuzz/absflat (4 x 64 * s32)
_UUD_FMT = "<80sHHHHI64i64i64i64i"
_UUD_SIZE = struct.calcsize(_UUD_FMT)          # 1116 bytes

# input_event: struct timeval (2 x i64 on 64-bit) + u16 type + u16 code + s32
_EVENT_FMT = "llHHi"


class UinputUnavailable(RuntimeError):
    """Raised when /dev/uinput cannot be opened for writing."""


def uinput_available(device: str = DEFAULT_DEVICE) -> bool:
    """True when a virtual input device can be created (device + permission)."""

    if not os.path.exists(device):
        return False
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return False
    else:
        os.close(fd)
        return True


def _permission_hint() -> str:
    return (
        "Fix with:\n"
        "  sudo modprobe uinput\n"
        "  echo 'KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\", "
        "OPTIONS+=\"static_node=uinput\"' | sudo tee /etc/udev/rules.d/70-uinput.rules\n"
        "  sudo udevadm control --reload && sudo udevadm trigger\n"
        "  sudo usermod -aG input \"$USER\"   # log out and back in"
    )


class UinputInput:
    """Keyboard + absolute mouse backed by a virtual uinput device.

    Works on Wayland (and X11, and the text console) because events enter the
    input pipeline at the kernel level, not at the display server.

    ``set_screen_size`` is called by the engine once frames start flowing so
    pixel coordinates can be scaled into the virtual digitizer's range.
    """

    def __init__(self, device: Optional[str] = DEFAULT_DEVICE,
                 name: str = "bssmacro virtual device",
                 screen_size: Optional[tuple[int, int]] = None) -> None:
        self._lock = threading.RLock()   # reentrant: close() calls key_up()
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()
        self._screen = screen_size or (1920, 1080)
        self._fd: Optional[int] = None
        self._events: list[tuple[int, int, int]] = []   # recording mode log
        if device is None:
            return                                      # recording mode (tests)
        self._open_device(device, name.encode())

    # -- device setup ------------------------------------------------------
    def _open_device(self, device: str, name_bytes: bytes) -> None:
        try:
            fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        except OSError as exc:
            raise UinputUnavailable(
                f"Cannot open {device}: {exc}\n{_permission_hint()}") from exc
        try:
            self._configure_device(fd, name_bytes)
        except OSError as exc:
            os.close(fd)
            raise UinputUnavailable(
                f"Kernel rejected the virtual device setup: {exc}") from exc
        self._fd = fd

    def _configure_device(self, fd: int, name_bytes: bytes) -> None:
        ioc = fcntl_ioctl  # indirection for tests
        for bit in (EV_KEY, EV_REL, EV_ABS, EV_SYN):
            ioc(fd, UI_SET_EVBIT, bit)
        for code in set(UINPUT_KEY_CODES.values()):
            ioc(fd, UI_SET_KEYBIT, code)
        for code in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, BTN_TOUCH, BTN_TOOL_PEN):
            ioc(fd, UI_SET_KEYBIT, code)
        for code in (REL_X, REL_Y, REL_WHEEL):
            ioc(fd, UI_SET_RELBIT, code)
        for code in (ABS_X, ABS_Y):
            ioc(fd, UI_SET_ABSBIT, code)
        ioc(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)
        # Legacy device description write, then create.
        absmax = [0] * 64
        absmin = [0] * 64
        absmax[ABS_X] = absmax[ABS_Y] = ABS_MAX_COORD
        desc = struct.pack(_UUD_FMT, name_bytes[:80], BUS_USB, 0x1234, 0x5678, 1,
                           0, absmax, absmin, [0] * 64, [0] * 64)
        os.write(fd, desc)
        ioc(fd, UI_DEV_CREATE, 0)

    # -- low-level emission -------------------------------------------------
    def _emit(self, etype: int, code: int, value: int) -> None:
        self._write_event(etype, code, value)

    def _write_event(self, etype: int, code: int, value: int) -> None:
        if self._fd is None:      # recording mode (tests)
            self._events.append((etype, code, value))
            return
        now = time.time()
        buf = struct.pack(_EVENT_FMT, int(now), int((now % 1) * 1_000_000),
                          etype, code, value)
        os.write(self._fd, buf)

    def _syn(self) -> None:
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def _scale(self, px: int, axis_max: int, size_px: int) -> int:
        size = max(1, int(size_px))
        return max(0, min(ABS_MAX_COORD, int(px * ABS_MAX_COORD / size)))

    # -- public API ---------------------------------------------------------
    def set_screen_size(self, width: int, height: int) -> None:
        self._screen = (max(1, int(width)), max(1, int(height)))

    def move(self, x: int, y: int) -> None:
        w, h = self._screen
        ax = self._scale(int(x), ABS_MAX_COORD, w)
        ay = self._scale(int(y), ABS_MAX_COORD, h)
        with self._lock:
            self._emit(EV_ABS, ABS_X, ax)
            self._emit(EV_ABS, ABS_Y, ay)
            self._syn()

    def move_rel(self, dx: int, dy: int) -> None:
        with self._lock:
            self._emit(EV_REL, REL_X, int(dx))
            self._emit(EV_REL, REL_Y, int(dy))
            self._syn()

    def down(self, button: str = "left") -> None:
        code = _BUTTON_CODES.get(button, BTN_LEFT)
        with self._lock:
            self._emit(EV_KEY, BTN_TOOL_PEN, 1)   # enter proximity
            self._emit(EV_KEY, BTN_TOUCH, 1)
            self._emit(EV_KEY, code, 1)
            self._syn()
            self._held_buttons.add(button)

    def up(self, button: str = "left") -> None:
        code = _BUTTON_CODES.get(button, BTN_LEFT)
        with self._lock:
            self._emit(EV_KEY, code, 0)
            self._emit(EV_KEY, BTN_TOUCH, 0)
            self._emit(EV_KEY, BTN_TOOL_PEN, 0)
            self._syn()
            self._held_buttons.discard(button)

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None, count: int = 1) -> None:
        for _ in range(max(1, int(count))):
            if x is not None and y is not None:
                self.move(int(x), int(y))
            self.down(button)
            time.sleep(0.01)
            self.up(button)

    def scroll(self, delta: int) -> None:
        steps = max(1, abs(int(delta)))
        sign = 1 if delta > 0 else -1
        with self._lock:
            for _ in range(steps):
                self._emit(EV_REL, REL_WHEEL, sign)
                self._syn()

    def key_down(self, key: str) -> None:
        code = UINPUT_KEY_CODES.get(str(key).lower())
        if not code:
            return
        with self._lock:
            self._emit(EV_KEY, code, 1)
            self._syn()
            self._held_keys.add(str(key).lower())

    def key_up(self, key: str) -> None:
        code = UINPUT_KEY_CODES.get(str(key).lower())
        if not code:
            return
        with self._lock:
            self._emit(EV_KEY, code, 0)
            self._syn()
            self._held_keys.discard(str(key).lower())

    def tap(self, key: str, delay: float = 0.02) -> None:
        self.key_down(key)
        time.sleep(max(0.0, delay))
        self.key_up(key)

    def is_key_down(self, key: str) -> bool:
        return str(key).lower() in self._held_keys

    # -- window focus --------------------------------------------------------
    def focus_sober(self, title_contains: Optional[list[str]] = None,
                    process_contains: Optional[list[str]] = None) -> bool:
        """Bring Sober forward so the game receives our input.

        Wayland compositors don't expose "focus this window" to clients, so:

        * X11/XWayland sessions still use the reliable XSetInputFocus path.
        * Native Wayland: click the centre of the matched window
          (click-to-focus) — the virtual pointer can do that.
        """

        win = find_window_any(title_contains=title_contains,
                              process_contains=process_contains)
        if win is None:
            return False
        if getattr(win, "ident", None):        # X11 handle -> use XSetInputFocus
            try:
                focus_window(win.ident)
                return True
            except Exception:
                pass
        self.click("left", win.x + win.w // 2, win.y + win.h // 2)
        return True

    def close(self) -> None:
        with self._lock:
            for key in list(self._held_keys):
                self.key_up(key)
            for btn in list(self._held_buttons):
                self.up(btn)
        if self._fd is not None:
            try:
                fcntl_ioctl(self._fd, UI_DEV_DESTROY, 0)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None


def fcntl_ioctl(fd: int, request: int, arg: int) -> int:
    import fcntl

    return int(fcntl.ioctl(fd, request, arg))
