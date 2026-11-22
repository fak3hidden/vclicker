"""Key holder engine: keeps one or more keys pressed, optionally per-window."""

from __future__ import annotations

import atexit
import threading
import weakref
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from .backend import Backend, get_backend
from .backend_base import WindowInfo


@dataclass
class KeyHolderConfig:
    keys: list[str] = field(default_factory=lambda: ["space"])
    timing: str = "hold"          # "hold" (until toggled off) or "timed"
    duration: float = 5.0         # seconds, when timing == "timed"
    repeat: bool = False          # re-send key-down events (for apps that need them)
    repeat_ms: float = 100.0
    target: str = "global"        # "global" or "windows"
    windows: list[WindowInfo] = field(default_factory=list)


class KeyHolder(QObject):
    state_changed = Signal(bool)
    released = Signal(str)

    def __init__(self, backend: Backend | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.backend = backend or get_backend()
        self.cfg = KeyHolderConfig()
        self._active = False
        self._keys: list[str] = []
        self._windows: list[WindowInfo] = []
        self._repeat_thread: threading.Thread | None = None
        self._stop_repeat = threading.Event()
        self._timer: threading.Timer | None = None
        self._lock = threading.RLock()
        # Safety net that does not keep the engine (or its signals) alive forever.
        reference = weakref.ref(self)
        atexit.register(lambda: (holder := reference()) and holder.force_release())

    # -- state ------------------------------------------------------------- #
    @property
    def active(self) -> bool:
        return self._active

    @property
    def keys(self) -> list[str]:
        return list(self._keys)

    # -- control ----------------------------------------------------------- #
    def engage(self, cfg: KeyHolderConfig | None = None) -> bool:
        with self._lock:
            if cfg is not None:
                self.cfg = cfg
            if self._active:
                return False
            keys = [k for k in (self.cfg.keys or []) if k]
            if not keys:
                self.released.emit("No key selected")
                return False
            if not self.backend.caps.key_send:
                self.released.emit("No keyboard backend available")
                return False
            windows = list(self.cfg.windows) if self.cfg.target == "windows" else []
            if self.cfg.target == "windows" and not windows:
                self.released.emit("No windows selected")
                return False
            if windows and not self.backend.caps.targeted_hold:
                self.released.emit("This platform cannot target windows")
                return False
            self._keys = keys
            self._windows = windows
            try:
                self.backend.hold_keys(keys, windows or None)
            except Exception as exc:  # pragma: no cover
                self.released.emit(f"Key hold failed: {exc}")
                return False
            self._active = True
            if self.cfg.repeat and windows:
                self._start_repeat()
            if self.cfg.timing == "timed" and self.cfg.duration > 0:
                self._timer = threading.Timer(self.cfg.duration, self.disengage)
                self._timer.daemon = True
                self._timer.start()
            self.state_changed.emit(True)
            return True

    def disengage(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._stop_repeat.set()
            if self._timer:
                self._timer.cancel()
                self._timer = None
            try:
                self.backend.release_keys(self._keys, self._windows or None)
            except Exception:
                pass
            self._keys = []
            self._windows = []
            self._active = False
            self.state_changed.emit(False)
            self.released.emit("Released")

    def toggle(self, cfg: KeyHolderConfig | None = None) -> bool:
        if self._active:
            self.disengage()
            return False
        return self.engage(cfg)

    def force_release(self) -> None:
        """Safety net: never leave a key stuck down when the app exits."""
        if not self._active:
            return
        try:
            self.backend.release_keys(self._keys, self._windows or None)
        except Exception:
            pass
        self._active = False

    # -- internals --------------------------------------------------------- #
    def _start_repeat(self) -> None:
        self._stop_repeat.clear()

        def loop() -> None:
            interval = max(0.01, self.cfg.repeat_ms / 1000.0)
            while not self._stop_repeat.wait(interval):
                if not self._active:
                    break
                post = getattr(self.backend, "post_key_repeat", None)
                if post:
                    try:
                        post(self._windows, self._keys)
                    except Exception:
                        break

        self._repeat_thread = threading.Thread(target=loop, name="VClickerKeyRepeat", daemon=True)
        self._repeat_thread.start()
