"""Shared application context: engines, settings and cross-page signals."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from . import keys as keymap
from .config import Config
from .core.backend import Backend, get_backend
from .core.clicker import AutoClicker, ClickerConfig
from .core.hotkeys import DEFAULT_BINDINGS, HotkeyManager
from .core.keyholder import KeyHolder, KeyHolderConfig
from .core.macros import Macro, MacroStore
from .core.monitor import BaseMonitor
from .core.player import MacroPlayer
from .core.recorder import MacroRecorder


class AppContext(QObject):
    notify = Signal(str, str)          # message, tone (info|ok|warn|bad)
    macro_recorded = Signal(object)    # Macro
    library_changed = Signal()
    accent_changed = Signal(str)
    bindings_changed = Signal()

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.backend: Backend = get_backend()
        self.monitor: BaseMonitor = self.backend.create_monitor()
        self.monitor.start()

        self.hotkeys = HotkeyManager(self.monitor, self)
        self.hotkeys.set_bindings(config.get("hotkeys", {}) or dict(DEFAULT_BINDINGS))
        self.hotkeys.enabled = bool(config.get("hotkeys_enabled", True))
        self.hotkeys.attach()

        self.clicker = AutoClicker(self.backend, self)
        self.keyholder = KeyHolder(self.backend, self)
        self.recorder = MacroRecorder(self.monitor, self.backend, self)
        self.player = MacroPlayer(self.backend, self)
        self.store = MacroStore()

        self.selected_macro: Macro | None = None
        self.clicker_cfg = self._load_clicker_cfg()
        self.keyholder_cfg = self._load_keyholder_cfg()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self.config.save)

        self.clicker.finished.connect(self._on_clicker_finished)
        self.keyholder.released.connect(lambda msg: self.notify.emit(msg, "info"))
        self.player.finished.connect(lambda msg: self.notify.emit(msg, "info"))
        self.recorder.finished.connect(self._on_recorded)
        self._wire_hotkeys()

    # ------------------------------------------------------------------ #
    #  Config helpers
    # ------------------------------------------------------------------ #
    def _load_clicker_cfg(self) -> ClickerConfig:
        data = self.config.section("clicker")
        cfg = ClickerConfig()
        for field_name in cfg.__dataclass_fields__:      # type: ignore[attr-defined]
            if field_name in data:
                try:
                    current = getattr(cfg, field_name)
                    value = data[field_name]
                    setattr(cfg, field_name, type(current)(value) if current is not None else value)
                except (TypeError, ValueError):
                    pass
        return cfg

    def _load_keyholder_cfg(self) -> KeyHolderConfig:
        data = self.config.section("keyholder")
        cfg = KeyHolderConfig()
        keys = data.get("keys") or ["space"]
        cfg.keys = [k for k in (keymap.normalize(k) for k in keys) if k and k in keymap.KEYS] or ["space"]
        cfg.timing = str(data.get("timing", "hold"))
        cfg.duration = float(data.get("duration", 5.0) or 5.0)
        cfg.repeat = bool(data.get("repeat", False))
        cfg.repeat_ms = float(data.get("repeat_ms", 100.0) or 100.0)
        cfg.target = str(data.get("target", "global"))
        return cfg

    def persist_clicker(self) -> None:
        data = self.config.data.setdefault("clicker", {})
        cfg = self.clicker_cfg
        data.update({
            "mode": cfg.mode, "cps": cfg.cps, "ms": cfg.ms, "button": cfg.button,
            "double": cfg.double, "burst": cfg.burst,
            "limit_mode": "clicks" if cfg.limit_clicks else ("seconds" if cfg.limit_seconds else "none"),
            "limit_clicks": cfg.limit_clicks or 100,
            "limit_seconds": cfg.limit_seconds or 10.0,
            "position": cfg.position, "x": cfg.x, "y": cfg.y, "jitter": cfg.jitter,
        })
        self._save_timer.start()

    def persist_keyholder(self, windows: list | None = None) -> None:
        data = self.config.data.setdefault("keyholder", {})
        cfg = self.keyholder_cfg
        data.update({
            "keys": list(cfg.keys), "timing": cfg.timing, "duration": cfg.duration,
            "repeat": cfg.repeat, "repeat_ms": cfg.repeat_ms,
            "target": cfg.target,
        })
        if windows is not None:
            self.config.data["keyholder"]["windows"] = []
        self._save_timer.start()

    def apply_clicker_config(self) -> None:
        if self.clicker.running:
            self.clicker.apply_config(self.clicker_cfg)

    def set_accent(self, name: str) -> None:
        self.config.set("ui.accent", name)
        self.accent_changed.emit(name)

    # ------------------------------------------------------------------ #
    #  Hotkey actions
    # ------------------------------------------------------------------ #
    def _wire_hotkeys(self) -> None:
        self.hotkeys.on("toggle_clicker", self.toggle_clicker)
        self.hotkeys.on("toggle_keyhold", self.toggle_keyhold)
        self.hotkeys.on("record_macro", self.toggle_recording)
        self.hotkeys.on("play_macro", self.play_selected)
        self.hotkeys.on("panic", self.panic)

    def toggle_clicker(self) -> None:
        if self.clicker.running:
            self.clicker.stop("Stopped by hotkey")
            return
        if self.recorder.recording:
            self.toggle_recording()
        started = self.clicker.start(self.clicker_cfg)
        if started:
            self.notify.emit("Auto clicker started", "ok")

    def toggle_keyhold(self) -> None:
        if self.keyholder.active:
            self.keyholder.disengage()
            return
        if self.keyholder.engage(self.keyholder_cfg):
            keys = ", ".join(keymap.label(k) for k in self.keyholder_cfg.keys)
            self.notify.emit(f"Holding {keys}", "ok")

    def toggle_recording(self) -> None:
        if self.recorder.recording:
            macro = self.recorder.stop()
            if macro is None:
                self.notify.emit("Nothing was recorded", "warn")
        else:
            if self.clicker.running:
                self.clicker.stop("Stopped for recording")
            started = self.recorder.start()
            if started:
                self.notify.emit("Recording macro — press the record hotkey to stop", "warn")

    def play_selected(self) -> None:
        if self.player.playing:
            self.player.stop()
            return
        if self.clicker.running:
            self.clicker.stop("Stopped for playback")
        macro = self.selected_macro
        if macro is None:
            macros = self.store.list()
            macro = macros[0] if macros else None
        if macro is None:
            self.notify.emit("No macro to play yet", "warn")
            return
        speed = float(self.config.get("macro.speed", 1.0) or 1.0)
        loops = int(self.config.get("macro.loops", 1) or 1)
        instant = bool(self.config.get("macro.instant", False))
        if self.player.play(macro, speed, loops, instant):
            self.notify.emit(f"Playing “{macro.name}”", "ok")

    def panic(self) -> None:
        self.clicker.stop("Panic stop")
        self.keyholder.disengage()
        self.player.stop()
        if self.recorder.recording:
            self.recorder.stop()
        self.notify.emit("Panic stop — everything released", "bad")

    # ------------------------------------------------------------------ #
    #  Signals
    # ------------------------------------------------------------------ #
    def _on_clicker_finished(self, reason: str) -> None:
        if reason:
            self.notify.emit(reason, "info")

    def _on_recorded(self, macro) -> None:
        if macro is None:
            return
        macro.name = self.store.unique_name(macro.name)
        self.store.save(macro)
        self.selected_macro = macro
        self.notify.emit(f"Saved “{macro.name}” · {len(macro.events)} events", "ok")
        self.macro_recorded.emit(macro)
        self.library_changed.emit()

    def set_selected_macro(self, macro: Macro | None) -> None:
        self.selected_macro = macro
        self.config.set("macro.selected", macro.path if macro and macro.path else "")

    def shutdown(self) -> None:
        try:
            self.panic()
        except Exception:
            pass
        try:
            self.hotkeys.detach()
            self.monitor.stop()
        except Exception:
            pass
        self.config.save()
