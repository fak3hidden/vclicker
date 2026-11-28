"""Input via ``ydotool`` — the battle-tested uinput automation daemon.

Some users already run ``ydotoold`` (the ydotool daemon) for Wayland
automation. Instead of creating a second virtual device, this adapter shells
out to the ``ydotool`` CLI, which talks to the daemon over its unix socket.

Requirements::

    sudo apt install ydotool          # or build from ReimuNotMoe/ydotool
    sudo systemctl enable --now ydotool   # runs ydotoold (needs /dev/uinput)

All commands use raw EV_KEY keycodes (same table as
:mod:`bssmacro.input.linux_uinput`), so custom keyboard layouts are not an
issue. Mouse clicks use the documented button masks (``0xC0`` left,
``0xC1`` right).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

from .linux_uinput import UINPUT_KEY_CODES

CLICK_CODES = {"left": 0xC0, "right": 0xC1, "middle": 0xC2}


class YdotoolUnavailable(RuntimeError):
    """Raised when the ydotool binary is not installed."""


class YdotoolInput:
    """Drives the game through ``ydotool`` (ydotoold must be running)."""

    def __init__(self, binary: str = "ydotool",
                 runner: Optional[Callable[[list[str]], int]] = None,
                 timeout: float = 5.0) -> None:
        self._binary = binary
        self._timeout = timeout
        self._runner = runner or self._run
        self._held_keys: set[str] = set()
        self._lock = threading.Lock()
        if runner is None and shutil.which(binary) is None:
            raise YdotoolUnavailable(
                f"'{binary}' not found — install ydotool and start ydotoold "
                "(e.g. `sudo systemctl enable --now ydotool`).")

    # -- plumbing ----------------------------------------------------------
    def _run(self, argv: list[str]) -> int:
        proc = subprocess.run([self._binary] + argv,
                              capture_output=True, timeout=self._timeout)
        return proc.returncode

    def _cmd(self, argv: list[str]) -> None:
        with self._lock:
            rc = self._runner(argv)
        if rc != 0:
            raise RuntimeError(f"ydotool {' '.join(argv)} failed (rc={rc}) — "
                               "is ydotoold running?")

    def _code(self, key: str) -> Optional[int]:
        return UINPUT_KEY_CODES.get(str(key).lower())

    # -- mouse ---------------------------------------------------------------
    def move(self, x: int, y: int) -> None:
        self._cmd(["mousemove", "--absolute", "-x", str(int(x)),
                   "-y", str(int(y))])

    def move_rel(self, dx: int, dy: int) -> None:
        self._cmd(["mousemove", "-x", str(int(dx)), "-y", str(int(dy))])

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None, count: int = 1) -> None:
        if x is not None and y is not None:
            self.move(int(x), int(y))
        code = CLICK_CODES.get(button, CLICK_CODES["left"])
        argv = ["click", "--repeat", str(max(1, int(count))),
                "--next-delay", "10", hex(code)]
        self._cmd(argv)

    def down(self, button: str = "left") -> None:
        # ydotool's click tool always pairs press+release; holding a button is
        # not something the macro ever needs (movement is keyboard-driven).
        self.click(button)

    def up(self, button: str = "left") -> None:  # pragma: no cover - symmetry
        pass

    def scroll(self, delta: int) -> None:
        raise NotImplementedError("ydotool CLI has no scroll tool; "
                                  "use the uinput input backend instead.")

    # -- keyboard ------------------------------------------------------------
    def key_down(self, key: str) -> None:
        code = self._code(key)
        if not code:
            return
        self._cmd(["key", f"{code}:1"])
        self._held_keys.add(str(key).lower())

    def key_up(self, key: str) -> None:
        code = self._code(key)
        if not code:
            return
        self._cmd(["key", f"{code}:0"])
        self._held_keys.discard(str(key).lower())

    def tap(self, key: str, delay: float = 0.02) -> None:
        code = self._code(key)
        if not code:
            return
        time.sleep(0)
        self._cmd(["key", f"{code}:1", f"{code}:0"])

    def is_key_down(self, key: str) -> bool:
        return str(key).lower() in self._held_keys

    # -- focus ---------------------------------------------------------------
    def focus_sober(self, title_contains: Optional[list[str]] = None,
                    process_contains: Optional[list[str]] = None) -> bool:
        """Click-to-focus: ydotool cannot raise windows, but a tap in the
        window centre usually does."""
        from ..capture.window import find_window_any

        win = find_window_any(title_contains=title_contains,
                              process_contains=process_contains)
        if win is None:
            return False
        self.click("left", win.x + win.w // 2, win.y + win.h // 2)
        return True

    def close(self) -> None:
        self._held_keys.clear()
