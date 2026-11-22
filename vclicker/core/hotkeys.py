"""Global hotkey manager built on top of the input monitor."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal

from .. import keys as keymap
from .monitor import BaseMonitor

DEFAULT_BINDINGS: dict[str, str] = {
    "toggle_clicker": "f8",
    "toggle_keyhold": "f9",
    "record_macro": "f10",
    "play_macro": "f11",
    "panic": "f12",
}

ACTION_LABELS: dict[str, tuple[str, str]] = {
    "toggle_clicker": ("Start / stop auto clicker", "Fires the clicker on and off."),
    "toggle_keyhold": ("Hold / release keys", "Engages the key holder with the current setup."),
    "record_macro": ("Start / stop recording", "Records a new macro from raw input."),
    "play_macro": ("Play selected macro", "Replays the macro selected in the library."),
    "panic": ("Emergency stop", "Stops the clicker, key holder and playback at once."),
}

class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self, monitor: BaseMonitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.monitor = monitor
        self.enabled = True
        self.bindings: dict[str, str] = dict(DEFAULT_BINDINGS)
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._armed: set[str] = set()
        self._capture_cb: Callable[[str | None], None] | None = None
        self._suspended = 0
        self._attached = False

    # -- setup ------------------------------------------------------------- #
    def attach(self) -> None:
        if not self._attached:
            self.monitor.add_listener(self._on_event)
            self._attached = True

    def detach(self) -> None:
        if self._attached:
            self.monitor.remove_listener(self._on_event)
            self._attached = False

    def set_bindings(self, bindings: dict[str, str]) -> None:
        merged = dict(DEFAULT_BINDINGS)
        merged.update({k: v for k, v in bindings.items() if k in DEFAULT_BINDINGS})
        self.bindings = merged

    def on(self, action: str, callback: Callable[[], None]) -> None:
        self._callbacks[action] = callback

    def suspend(self) -> None:
        self._suspended += 1

    def resume(self) -> None:
        self._suspended = max(0, self._suspended - 1)

    @property
    def capturing(self) -> bool:
        return self._capture_cb is not None

    def capture_next(self, callback: Callable[[str | None], None]) -> None:
        """Ask for the next key combo; callback receives 'ctrl+k' style text."""
        previous = self._capture_cb
        self._capture_cb = callback
        if previous is not None:
            try:
                previous(None)
            except Exception:
                pass

    def cancel_capture(self) -> None:
        if self._capture_cb:
            cb = self._capture_cb
            self._capture_cb = None
            cb(None)

    # -- matching ---------------------------------------------------------- #
    def _on_event(self, ev) -> None:
        if ev.kind == "key_up" and ev.key:
            self._armed.discard(ev.key)
            return
        if ev.kind != "key_down" or not ev.key:
            return

        pressed = set(self.monitor._pressed_keys) | {ev.key}
        mods = {keymap.info(k).mod for k in pressed if keymap.info(k).mod}

        if self._capture_cb is not None:
            if keymap.is_modifier(ev.key):
                return
            combo = "+".join([m for m in keymap.MODIFIER_ORDER if m in mods] + [ev.key])
            cb = self._capture_cb
            self._capture_cb = None
            cb(combo)
            return

        if ev.key in self._armed:
            return

        for action, combo in self.bindings.items():
            if not combo:
                continue
            if action == "panic":
                pass
            elif not self.enabled or self._suspended:
                continue
            parts = keymap.parse_parts(combo)
            if not parts:
                continue
            main = parts[-1]
            expected_mods = {keymap.info(p).mod for p in parts[:-1] if keymap.info(p).mod}
            if ev.key != main or mods != expected_mods:
                continue
            self._armed.add(ev.key)
            callback = self._callbacks.get(action)
            if callback:
                try:
                    callback()
                except Exception:
                    pass
            try:
                self.triggered.emit(action)
            except RuntimeError:
                pass
            break
