"""Macro recorder: listens to the global input monitor and timestamps events."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from .backend import Backend, get_backend
from .backend_base import InputEvent
from .macros import Macro, MacroEvent, new_default_name
from .monitor import BaseMonitor


class MacroRecorder(QObject):
    state_changed = Signal(bool)
    counted = Signal(int, float)      # events, elapsed seconds
    finished = Signal(object)         # Macro

    def __init__(self, monitor: BaseMonitor, backend: Backend | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.monitor = monitor
        self.backend = backend or get_backend()
        self._events: list[MacroEvent] = []
        self._start = 0.0
        self._last_move = 0.0
        self._last_pos: tuple[int, int] | None = None
        self._recording = False
        self._lock = threading.Lock()
        self.ignore_injected = True
        self.ignore_keys: set[str] = set()
        self._last_emit = 0.0

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return len(self._events)

    # -- lifecycle --------------------------------------------------------- #
    def start(self) -> bool:
        if self._recording:
            return False
        if not self.monitor.running and not self.monitor.start():
            return False
        with self._lock:
            self._events = []
            self._start = time.perf_counter()
            self._last_move = self._start
            self._last_pos = None
            self._recording = True
            self._last_emit = 0.0
        self.monitor.add_listener(self._on_event)
        self.state_changed.emit(True)
        return True

    def stop(self, name: str | None = None) -> Macro | None:
        if not self._recording:
            return None
        self.monitor.remove_listener(self._on_event)
        with self._lock:
            self._recording = False
            events = self._events
            duration = max(0.0, time.perf_counter() - self._start)
        self.state_changed.emit(False)
        if not events:
            self.finished.emit(None)
            return None
        macro = Macro(name=name or new_default_name(), events=events, duration=duration)
        self.finished.emit(macro)
        return macro

    def events_snapshot(self) -> list:
        with self._lock:
            return list(self._events)

    def elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self._start) if self._recording else 0.0

    # -- capture ----------------------------------------------------------- #
    def _on_event(self, ev: InputEvent) -> None:
        if not self._recording:
            return
        if self.ignore_injected and ev.injected:
            return
        if ev.kind in ("key_down", "key_up") and ev.key in self.ignore_keys:
            return

        now = time.perf_counter()
        offset = now - self._start

        if ev.kind == "move":
            if self._last_pos is not None:
                dx = abs(ev.x - self._last_pos[0])
                dy = abs(ev.y - self._last_pos[1])
                if dx < 2 and dy < 2 and (now - self._last_move) < 0.02:
                    return
            self._last_pos = (ev.x, ev.y)
            self._last_move = now
            item = MacroEvent(t=offset, kind="move", x=ev.x, y=ev.y)
        elif ev.kind in ("mouse_down", "mouse_up"):
            item = MacroEvent(t=offset, kind="down" if ev.kind == "mouse_down" else "up",
                              button=ev.button or "left", x=ev.x, y=ev.y)
        elif ev.kind == "wheel":
            item = MacroEvent(t=offset, kind="wheel", delta=ev.delta, x=ev.x, y=ev.y)
        elif ev.kind in ("key_down", "key_up"):
            item = MacroEvent(t=offset, kind=ev.kind, key=ev.key)
        else:
            return

        with self._lock:
            self._events.append(item)
            count = len(self._events)
            should_emit = (now - self._last_emit) > 0.1
            if should_emit:
                self._last_emit = now
        if should_emit:
            self.counted.emit(count, offset)
