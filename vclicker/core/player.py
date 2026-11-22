"""Macro playback engine with speed control and looping."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from .backend import Backend, get_backend
from .backend_base import spin_sleep
from .macros import Macro


class MacroPlayer(QObject):
    state_changed = Signal(bool)
    progress = Signal(float, int)     # fraction 0..1, event index
    finished = Signal(str)

    def __init__(self, backend: Backend | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.backend = backend or get_backend()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._macro: Macro | None = None
        self._speed = 1.0
        self._loops = 1
        self._instant = False

    @property
    def playing(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop.is_set()

    def play(self, macro: Macro, speed: float = 1.0, loops: int = 1,
             instant: bool = False) -> bool:
        if self.playing:
            return False
        if not macro.events:
            self.finished.emit("Macro is empty")
            return False
        self._macro = macro
        self._speed = max(0.05, float(speed))
        self._loops = max(1, int(loops))
        self._instant = instant
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="VClickerPlayback", daemon=True)
        self._thread.start()
        self.state_changed.emit(True)
        return True

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    # -- engine ------------------------------------------------------------ #
    def _apply(self, event) -> None:
        backend = self.backend
        kind = event.kind
        if kind == "move":
            backend.move_to(event.x, event.y)
        elif kind == "down":
            backend.move_to(event.x, event.y)
            backend.mouse_down(event.button or "left")
        elif kind == "up":
            backend.mouse_up(event.button or "left")
        elif kind == "wheel":
            backend.scroll(event.delta, event.x, event.y)
        elif kind == "key_down" and event.key:
            backend.key_down(event.key)
        elif kind == "key_up" and event.key:
            backend.key_up(event.key)

    def _release_all(self, events) -> None:
        """Safety: undo anything the macro left pressed."""
        for event in events:
            if event.kind == "down" and event.button:
                try:
                    self.backend.mouse_up(event.button)
                except Exception:
                    pass
            elif event.kind == "key_down" and event.key:
                try:
                    self.backend.key_up(event.key)
                except Exception:
                    pass

    def _run(self) -> None:
        macro = self._macro
        assert macro is not None
        speed = self._speed
        loops = self._loops
        reason = "Playback finished"
        total = len(macro.events)

        try:
            for loop_index in range(loops):
                if self._stop.is_set():
                    reason = "Playback stopped"
                    break
                origin = time.perf_counter()
                for index, event in enumerate(macro.events):
                    if self._stop.is_set():
                        reason = "Playback stopped"
                        break
                    if not self._instant:
                        target = origin + (event.t / speed)
                        now = time.perf_counter()
                        if target > now:
                            if target - now > 0.25:
                                # long idle gap: poll the stop flag while sleeping
                                while not self._stop.is_set():
                                    remaining = target - time.perf_counter()
                                    if remaining <= 0.25:
                                        break
                                    self._stop.wait(min(0.25, remaining))
                            spin_sleep(target)
                    if self._stop.is_set():
                        reason = "Playback stopped"
                        break
                    try:
                        self._apply(event)
                    except Exception as exc:  # pragma: no cover
                        reason = f"Playback error: {exc}"
                        break
                    if index % 16 == 0 or index == total - 1:
                        fraction = (index + 1 + loop_index * total) / max(1, total * loops)
                        try:
                            self.progress.emit(min(1.0, fraction), index)
                        except RuntimeError:
                            pass
                if reason != "Playback finished":
                    break
        finally:
            try:
                self._release_all(macro.events)
            except Exception:
                pass
            self._thread = None
            self.state_changed.emit(False)
            self.finished.emit(reason)
