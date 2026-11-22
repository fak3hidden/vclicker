"""Windows backend (SendInput + low-level hooks + PostMessage targeting).

No third-party packages: everything talks to user32/kernel32 through ctypes.
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

from .. import keys as keymap
from .backend_base import Backend, Capabilities, ClickAction, InputEvent, WindowInfo
from .monitor import BaseMonitor

# --------------------------------------------------------------------------- #
#  ctypes plumbing
# --------------------------------------------------------------------------- #
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_QUIT = 0x0012

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

KBDLLHOOKSTRUCT_PTR = ctypes.POINTER  # forward declaration for typing only


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostMessageW.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.restype = LRESULT
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

_HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, _HOOKPROC, wintypes.HMODULE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.GetMessageW.restype = ctypes.c_int
user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
user32.DispatchMessageW.restype = LRESULT
user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
user32.EnumWindows.argtypes = (_ENUMPROC, wintypes.LPARAM)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowLongW.restype = ctypes.c_long

_EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,   # pgup/pgdn/end/home/arrows
    0x2D, 0x2E, 0x2C, 0x90, 0x5B, 0x5C, 0x5D, 0x6F,   # ins/del/prtsc/numlock/wins/menu/div
    0xA3, 0xA5,                                        # right ctrl / right alt
}

_BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 0),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 0),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP, 0),
    "back": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON1),
    "forward": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON2),
}


def _mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_MOUSE
    item.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
    return item


def _key_input(vk: int, flags: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    # Including the hardware scan code makes the event look native to apps that
    # inspect the key message (and to DirectInput-style polling).
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    item.ki = KEYBDINPUT(vk & 0xFFFF, scan, flags, 0, 0)
    return item


def _abs_coords(x: int, y: int) -> tuple[int, int]:
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = max(1, user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1)
    vh = max(1, user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1)
    return (int(round((x - vx) * 65535 / vw)), int(round((y - vy) * 65535 / vh)))


def _key_lparam(vk: int, keyup: bool = False, repeat: int = 1) -> int:
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    lp = repeat & 0xFFFF
    lp |= scan << 16
    if vk in _EXTENDED_VKS:
        lp |= 1 << 24
    if keyup:
        lp |= (1 << 30) | (1 << 31)
    return lp


class WinClickAction(ClickAction):
    pass


# --------------------------------------------------------------------------- #
#  Backend
# --------------------------------------------------------------------------- #
class WindowsBackend(Backend):
    os_name = "windows"
    name = "Windows · SendInput"
    needs_permissions_hint = (
        "Some games only accept input when the clicker runs as administrator."
    )

    def __init__(self) -> None:
        super().__init__()
        self.caps = Capabilities(
            clicking=True,
            key_send=True,
            targeted_hold=True,
            window_list=True,
            recording=True,
            recording_quality="Low-level hooks (exact timestamps)",
            hotkeys=True,
            scroll=True,
            notes=[
                "Background key-hold uses PostMessage, so windows never need focus.",
                "DirectInput / Raw Input games may ignore background key messages.",
                "Run VClicker as administrator for elevated game windows.",
            ],
        )

    # -- mouse ------------------------------------------------------------- #
    def build_click(self, button: str = "left", double: bool = False,
                    x: int | None = None, y: int | None = None,
                    burst: int = 1) -> ClickAction:
        down_flag, up_flag, data = _BUTTON_FLAGS.get(button, _BUTTON_FLAGS["left"])
        burst = max(1, int(burst))
        items: list[INPUT] = []
        move = None
        if x is not None and y is not None:
            ax, ay = _abs_coords(int(x), int(y))
            move = _mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                                ax, ay)
        for _ in range(burst):
            if move is not None:
                items.append(move)
            for _ in range(2 if double else 1):
                items.append(_mouse_input(down_flag, data=data))
                items.append(_mouse_input(up_flag, data=data))
        arr = (INPUT * len(items))(*items)
        count = len(items)
        size = ctypes.sizeof(INPUT)
        send = user32.SendInput
        # Pre-bind for the tight loop.
        def fire() -> None:
            send(count, arr, size)

        return ClickAction(fire, burst * (2 if double else 1))

    def mouse_down(self, button: str = "left") -> None:
        down_flag, _up, data = _BUTTON_FLAGS.get(button, _BUTTON_FLAGS["left"])
        item = _mouse_input(down_flag, data=data)
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))

    def mouse_up(self, button: str = "left") -> None:
        _down, up_flag, data = _BUTTON_FLAGS.get(button, _BUTTON_FLAGS["left"])
        item = _mouse_input(up_flag, data=data)
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))

    def move_to(self, x: int, y: int) -> None:
        user32.SetCursorPos(int(x), int(y))

    def cursor_pos(self) -> tuple[int, int]:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    def scroll(self, delta: int, x: int | None = None, y: int | None = None) -> None:
        items: list[INPUT] = []
        if x is not None and y is not None:
            ax, ay = _abs_coords(int(x), int(y))
            items.append(_mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                                      ax, ay))
        items.append(_mouse_input(MOUSEEVENTF_WHEEL, data=int(delta) * 120))
        arr = (INPUT * len(items))(*items)
        user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))

    # -- keyboard ---------------------------------------------------------- #
    def key_down(self, key: str) -> None:
        info = keymap.info(key)
        if not info.vk:
            return
        item = _key_input(info.vk)
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))

    def key_up(self, key: str) -> None:
        info = keymap.info(key)
        if not info.vk:
            return
        item = _key_input(info.vk, KEYEVENTF_KEYUP)
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))

    def hold_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        if not windows:
            for key in keys:
                self.key_down(key)
            return
        for window in windows:
            for key in keys:
                self._post_key(window.ident, key, down=True)

    def release_keys(self, keys: list[str], windows: list[WindowInfo] | None = None) -> None:
        if not windows:
            for key in reversed(keys):
                self.key_up(key)
            return
        for window in windows:
            for key in reversed(keys):
                self._post_key(window.ident, key, down=False)

    def post_key_repeat(self, windows: list[WindowInfo], keys: list[str]) -> None:
        for window in windows:
            for key in keys:
                self._post_key(window.ident, key, down=True, repeat=1)

    def _post_key(self, hwnd: int, key: str, down: bool, repeat: int = 1) -> None:
        info = keymap.info(key)
        if not info.vk:
            return
        msg = WM_KEYDOWN if down else WM_KEYUP
        if info.vk in (0x12,):  # Alt needs the SYS variant to register as held
            msg = WM_SYSKEYDOWN if down else WM_SYSKEYUP
        user32.PostMessageW(hwnd, msg, info.vk, _key_lparam(info.vk, keyup=not down, repeat=repeat))

    def is_key_down(self, key: str) -> bool:
        info = keymap.info(key)
        if not info.vk:
            return False
        return bool(user32.GetAsyncKeyState(info.vk) & 0x8000)

    # -- windows ----------------------------------------------------------- #
    def list_windows(self) -> list[WindowInfo]:
        results: list[WindowInfo] = []

        @_ENUMPROC
        def _callback(hwnd, _lparam):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if exstyle & WS_EX_TOOLWINDOW:
                    return True
                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    return True
                if rect.right - rect.left < 40 or rect.bottom - rect.top < 20:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if not title:
                    return True
                pid = wintypes.DWORD(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process = _process_name(pid.value)
                results.append(WindowInfo(int(hwnd), title, process, int(pid.value)))
            except Exception:
                pass
            return True

        user32.EnumWindows(_callback, 0)
        results.sort(key=lambda w: (w.process.lower(), w.title.lower()))
        return results

    def foreground_window(self) -> WindowInfo | None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return WindowInfo(int(hwnd), buf.value, _process_name(pid.value), int(pid.value))

    def screen_size(self) -> tuple[int, int]:
        return (user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
                user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))

    def create_monitor(self):
        return WindowsMonitor()

    def describe(self) -> str:
        return "Windows · SendInput + low-level hooks"


def _process_name(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


# --------------------------------------------------------------------------- #
#  Global monitor (low-level hooks)
# --------------------------------------------------------------------------- #
class WindowsMonitor(BaseMonitor):
    """Keyboard + mouse capture through WH_KEYBOARD_LL / WH_MOUSE_LL."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._kb_hook = None
        self._ms_hook = None
        self._kb_proc_ref = None
        self._ms_proc_ref = None
        self._last_pos = (-1, -1)
        self.use_dispatch_thread = True

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            self._running = True
            return True
        super().start()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="VClickerInputHook", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)
        return self._kb_hook is not None

    def stop(self) -> None:
        super().stop()
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = 0

    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        self._thread_id = int(kernel32.GetCurrentThreadId())
        module = kernel32.GetModuleHandleW(None)

        def kb_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION:
                try:
                    kb = KBDLLHOOKSTRUCT.from_address(l_param)
                    name = keymap.VK_TO_NAME.get(int(kb.vkCode))
                    if name:
                        if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            kind = "key_down"
                        elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                            kind = "key_up"
                        else:
                            kind = None
                        if kind:
                            self._emit_raw(InputEvent(
                                kind=kind, key=name,
                                injected=bool(kb.flags & LLKHF_INJECTED)))
                except Exception:
                    pass
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        def ms_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION:
                try:
                    ms = MSLLHOOKSTRUCT.from_address(l_param)
                    injected = bool(ms.flags & LLMHF_INJECTED)
                    x, y = int(ms.pt.x), int(ms.pt.y)
                    kind = None
                    button = None
                    delta = 0
                    if w_param == WM_MOUSEMOVE:
                        if (x, y) != self._last_pos:
                            self._last_pos = (x, y)
                            self._emit_raw(InputEvent(kind="move", x=x, y=y,
                                                      injected=injected))
                        return user32.CallNextHookEx(None, n_code, w_param, l_param)
                    if w_param in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                        button = "left"
                        kind = "mouse_down" if w_param == WM_LBUTTONDOWN else "mouse_up"
                    elif w_param in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                        button = "right"
                        kind = "mouse_down" if w_param == WM_RBUTTONDOWN else "mouse_up"
                    elif w_param in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                        button = "middle"
                        kind = "mouse_down" if w_param == WM_MBUTTONDOWN else "mouse_up"
                    elif w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                        high = (int(ms.mouseData) >> 16) & 0xFFFF
                        button = "back" if high == XBUTTON1 else "forward"
                        kind = "mouse_down" if w_param == WM_XBUTTONDOWN else "mouse_up"
                    elif w_param == WM_MOUSEWHEEL:
                        raw = int(ms.mouseData) & 0xFFFFFFFF
                        signed = raw - 0x100000000 if raw & 0x80000000 else raw
                        delta = int(signed / 120)
                        kind = "wheel"
                    if kind:
                        self._emit_raw(InputEvent(kind=kind, button=button, x=x, y=y,
                                                  delta=delta, injected=injected))
                except Exception:
                    pass
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._kb_proc_ref = _HOOKPROC(kb_proc)
        self._ms_proc_ref = _HOOKPROC(ms_proc)
        try:
            # Force this thread's message queue into existence so a very early
            # stop() cannot lose the WM_QUIT.
            peek = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(peek), None, 0, 0, 0)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc_ref, module, 0)
            self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc_ref, module, 0)
            if not self._kb_hook:
                self.error = f"SetWindowsHookEx failed ({ctypes.get_last_error()})"
        finally:
            self._ready.set()

        if not self._kb_hook:
            return

        msg = wintypes.MSG()
        while self._running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._kb_hook:
            user32.UnhookWindowsHookEx(self._kb_hook)
            self._kb_hook = None
        if self._ms_hook:
            user32.UnhookWindowsHookEx(self._ms_hook)
            self._ms_hook = None
        self._running = False

    def is_key_down(self, key: str) -> bool:
        if key in self._pressed_keys:
            return True
        info = keymap.info(key)
        if not info.vk:
            return False
        return bool(user32.GetAsyncKeyState(info.vk) & 0x8000)
