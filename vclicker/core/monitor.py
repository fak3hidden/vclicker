"""Global input monitoring base class.

The platform backends push low-level events into :meth:`_emit_raw`, which calls
any registered raw listeners on the capturing thread (cheap, allocation-light)
and republishes kit events through the Qt signal ``event`` for the UI.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

from .backend_base import InputEvent

Listener = Callable[[InputEvent], None]

# Event kinds that are worth forwarding to the UI thread.
_SIGNAL_KINDS = {"key_down", "key_up", "mouse_down", "mouse_up", "wheel"}


class BaseMonitor(QObject):
    event = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._listeners: list[Listener] = []
        self._lock = threading.RLock()
        self._running = False
        self._last_move = 0.0
        self.error = ""
        self._pressed_keys: set[str] = set()
        # Only publish through the Qt signal once something subscribes; emitting
        # cross-thread events with no event loop running would queue forever.
        self._signal_enabled = False
        # Low-level OS hooks must return fast, so they enqueue and a worker
        # thread (this one) runs the listeners.
        self.use_dispatch_thread = False
        self._queue: queue.Queue | None = None
        self._dispatcher: threading.Thread | None = None

    # -- lifecycle --------------------------------------------------------- #
    def start(self) -> bool:
        self._running = True
        if self.use_dispatch_thread and self._dispatcher is None:
            self._queue = queue.Queue(maxsize=100000)
            self._dispatcher = threading.Thread(target=self._dispatch_loop,
                                                name="VClickerDispatch", daemon=True)
            self._dispatcher.start()
        return True

    def stop(self) -> None:
        self._running = False
        self._signal_enabled = False
        dispatcher = self._dispatcher
        if dispatcher is not None and self._queue is not None:
            self._dispatcher = None
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
            if dispatcher is not threading.current_thread():
                dispatcher.join(timeout=0.5)
            self._queue = None

    @property
    def running(self) -> bool:
        return self._running

    def connect_event(self, callback) -> None:
        """Subscribe a UI callback to key/click/wheel events (Qt signal)."""
        self.event.connect(callback)
        self._signal_enabled = True

    # -- listeners --------------------------------------------------------- #
    def add_listener(self, listener: Listener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    # -- internal ---------------------------------------------------------- #
    def _track(self, ev: InputEvent) -> None:
        if ev.kind == "key_down" and ev.key:
            self._pressed_keys.add(ev.key)
        elif ev.kind == "key_up" and ev.key:
            self._pressed_keys.discard(ev.key)

    def _dispatch_loop(self) -> None:
        while True:
            ev = self._queue.get() if self._queue is not None else None
            if ev is None:
                return
            try:
                self._deliver(ev)
            except Exception:
                pass

    def _emit_raw(self, ev: InputEvent) -> None:
        if not self._running:
            return
        if self._queue is not None:
            try:
                self._queue.put_nowait(ev)
            except queue.Full:
                pass
            return
        self._deliver(ev)

    def _deliver(self, ev: InputEvent) -> None:
        if not self._running:
            return
        # Drop auto-repeat: a key that is already down should not fire again.
        if ev.kind == "key_down" and ev.key and ev.key in self._pressed_keys:
            return
        self._track(ev)
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            try:
                listener(ev)
            except Exception:  # a listener must never break input capture
                pass
        if self._signal_enabled and ev.kind in _SIGNAL_KINDS:
            try:
                self.event.emit(ev)
            except RuntimeError:
                pass

    def is_key_down(self, key: str) -> bool:
        return key in self._pressed_keys
