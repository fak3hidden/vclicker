"""High-performance auto clicker engine."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal

from .backend import Backend, get_backend
from .backend_base import spin_sleep


@dataclass
class ClickerConfig:
    mode: str = "cps"            # "cps" | "interval" | "instant"
    cps: float = 20.0
    ms: float = 50.0             # used when mode == "interval"
    button: str = "left"
    double: bool = False
    burst: int = 1               # clicks crammed into one SendInput/event call
    limit_mode: str = "none"     # "none" | "clicks" | "seconds"
    limit_clicks: int = 0        # 0 = unlimited
    limit_seconds: float = 0.0   # 0 = unlimited
    position: str = "cursor"     # "cursor" | "fixed"
    x: int = 0
    y: int = 0
    jitter: float = 0.0          # 0.0 - 0.5


class AutoClicker(QObject):
    """Runs the click loop on a dedicated thread with an optional zero-delay mode."""

    state_changed = Signal(bool)
    stats = Signal(float, int, float)     # live cps, total clicks, peak cps
    finished = Signal(str)

    def __init__(self, backend: Backend | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.backend = backend or get_backend()
        self.cfg = ClickerConfig()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._stop_reason = "Stopped"
        self._dirty = False
        self._total = 0
        self._peak = 0.0

    # -- public API -------------------------------------------------------- #
    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop.is_set()

    @property
    def total(self) -> int:
        return self._total

    @property
    def peak(self) -> float:
        return self._peak

    def start(self, cfg: ClickerConfig | None = None) -> bool:
        if self.running:
            return False
        if cfg is not None:
            self.cfg = replace(cfg)
        if not self.backend.caps.clicking:
            self.finished.emit("No input backend available on this system.")
            return False
        self._stop.clear()
        self._stop_reason = "Stopped"
        self._dirty = False
        self._total = 0
        self._peak = 0.0
        thread = threading.Thread(target=self._run, name="VClickerAuto", daemon=True)
        self._thread = thread
        thread.start()
        self.state_changed.emit(True)
        return True

    def apply_config(self, cfg: ClickerConfig) -> None:
        """Live-apply settings; a running loop rebuilds within a few hundred clicks."""
        self.cfg = replace(cfg)
        self._dirty = True

    def stop(self, reason: str = "Stopped") -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop_reason = reason
        self._stop.set()
        if thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def toggle(self, cfg: ClickerConfig | None = None) -> bool:
        if self.running:
            self.stop("Stopped by hotkey")
            return False
        return self.start(cfg)

    # -- engine ------------------------------------------------------------ #
    def _rebuild(self, cfg: ClickerConfig):
        backend = self.backend
        x = cfg.x if cfg.position == "fixed" else None
        y = cfg.y if cfg.position == "fixed" else None
        action = backend.build_click(cfg.button, cfg.double, x, y, max(1, int(cfg.burst)))
        if cfg.mode == "instant":
            interval = 0.0
        elif cfg.mode == "interval":
            interval = max(0.0, cfg.ms / 1000.0)
        else:
            interval = 1.0 / max(0.001, cfg.cps)
        return action, interval

    def _run(self) -> None:
        stop = self._stop
        total = 0
        started = time.perf_counter()
        last_stats_time = started
        last_stats_count = 0
        next_stats = started + 0.2
        peak = 0.0
        reason = "Stopped"
        cfg = self.cfg

        try:
            action, interval = self._rebuild(cfg)
        except Exception as exc:  # pragma: no cover - defensive
            self._thread = None
            self.state_changed.emit(False)
            self.finished.emit(f"Could not start: {exc}")
            return

        per_fire = max(1, action.burst)
        deadline = 0.0

        while not stop.is_set():
            if self._dirty:
                cfg = self.cfg
                self._dirty = False
                try:
                    action, interval = self._rebuild(cfg)
                    per_fire = max(1, action.burst)
                except Exception:
                    pass
                deadline = 0.0

            try:
                action.fire()
            except Exception:
                reason = "Input backend error"
                break

            total += per_fire

            if cfg.limit_clicks and total >= cfg.limit_clicks:
                reason = "Click limit reached"
                break
            if cfg.limit_seconds and (time.perf_counter() - started) >= cfg.limit_seconds:
                reason = "Time limit reached"
                break

            if interval > 0.0:
                step = interval
                if cfg.jitter > 0.0:
                    step *= 1.0 + random.uniform(-cfg.jitter, cfg.jitter)
                now = time.perf_counter()
                # Resync if we fell far behind (e.g. the system stalled) so the
                # engine never tries to "catch up" with a burst of clicks.
                if deadline <= 0.0 or deadline < now - interval * 4:
                    deadline = now
                deadline += step
                spin_sleep(deadline)

            now = time.perf_counter()
            if now >= next_stats:
                elapsed = max(1e-6, now - last_stats_time)
                cps = (total - last_stats_count) / elapsed
                peak = max(peak, cps)
                self._total = total
                self._peak = peak
                try:
                    self.stats.emit(cps, total, peak)
                except RuntimeError:
                    pass
                last_stats_time = now
                last_stats_count = total
                next_stats = now + 0.25

        requested = self._stop_reason
        if reason == "Stopped" and requested:
            reason = requested

        self._total = total
        self._peak = max(peak, self._peak)
        self._thread = None
        try:
            self.stats.emit(0.0, total, self._peak)
        except RuntimeError:
            pass
        self.state_changed.emit(False)
        self.finished.emit(reason)
