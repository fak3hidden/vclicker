"""The macro engine — ties capture, vision, movement and reporting together.

The public surface is deliberately small so it is easy to drive headless:

* :meth:`Engine.start` / :meth:`stop` / :meth:`pause` / :meth:`resume` run the
  full loop on a background thread (real use, with ``ScreenCapture`` + ``X11Input``).
* :meth:`Engine.loop_once` runs a single pipeline tick on a given frame. The
  self-tests call this directly with synthetic frames and a :class:`FakeInput`,
  exercising detection -> collector -> movement -> actions with zero display.

Pipeline per tick::

    grab frame -> detect -> read HUD -> objective.choose(target)
    -> move toward target -> gather clicks -> convert-if-full
    -> webhook heartbeat / event ping -> status callback
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any, Callable, Optional

from .capture.capture import ScreenCapture, SyntheticCapture
from .catalog import category_of
from .input.base import FakeInput, InputController
from .types import Detection, Frame, Stats, Target
from .vision.collector import Collector
from .vision.detector import TokenDetector
from .vision.hud import HudReader
from .vision.templates import TemplateStore
from .webhook.discord import DiscordWebhook
from .farming.objectives import build_objective


class Engine:
    def __init__(self, config, input: InputController,
                 capture: Optional[ScreenCapture] = None,
                 webhook: Optional[DiscordWebhook] = None,
                 status_cb: Optional[Callable[[dict], None]] = None,
                 detector: Optional[TokenDetector] = None,
                 collector: Optional[Collector] = None) -> None:
        self.config = config
        self.input = input
        self.capture = capture
        self.webhook = webhook
        self.status_cb = status_cb

        store = TemplateStore(getattr(config, "templates_dir", ""))
        self.detector = detector or TokenDetector(store, config.detector)
        self.collector = collector or Collector(config.collector)
        self.hud = HudReader(config.hud)
        self.objective = build_objective(config)

        self.stats = Stats()
        self._last_detections: list[Detection] = []
        self._mode = config.objective
        self._state = "collecting"          # collecting | returning | idle
        self._held_move: set[str] = set()   # forward/back/left/right
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_gather = 0.0
        self._last_status = 0.0
        self._last_frame: Optional[Frame] = None
        self._wander_angle = random.uniform(0, 2 * math.pi)
        self._wander_next = 0.0
        self._convert_cooldown = 0.0
        self._errors = 0
        self._fps = 0.0
        self._fps_at = time.perf_counter()

    # -- public lifecycle -------------------------------------------------
    @property
    def running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive() and not self._stop.is_set()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def start(self) -> bool:
        if self.capture is None:
            raise RuntimeError("Engine.start requires a capture instance.")
        if self.running:
            return False
        self._stop.clear()
        self._pause.clear()
        self.stats = Stats()
        self._focus_if_needed()
        self._thread = threading.Thread(target=self._run, name="BSSMacro", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._release_movement()
        if self.input is not None:
            try:
                self.input.close()
            except Exception:
                pass
        if self.capture is not None:
            try:
                self.capture.close()
            except Exception:
                pass

    def pause(self) -> None:
        self._pause.set()
        self._release_movement()

    def resume(self) -> None:
        self._pause.clear()

    # -- engine API used by objectives ------------------------------------
    def press(self, key: str, delay: float = 0.02) -> None:
        try:
            self.input.tap(key, delay)
        except Exception:
            self._on_error("press", key)

    def now(self) -> float:
        return time.perf_counter()

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def anchor(self, frame: Frame) -> tuple[int, int]:
        return frame.center()

    # -- main loop --------------------------------------------------------
    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                if self._pause.is_set():
                    time.sleep(0.1)
                    continue
                if self.config.safety.max_runtime_min > 0:
                    if self.stats.elapsed() / 60.0 >= self.config.safety.max_runtime_min:
                        self.stats.last_event = "Max runtime reached"
                        break
                frame = self.capture.grab()
                self.loop_once(frame)
        finally:
            self._release_movement()
            if self.webhook is not None:
                try:
                    self.webhook.notify_event("stop", self.stats, self._last_frame)
                except Exception:
                    pass

    def loop_once(self, frame: Frame) -> dict:
        """Run one tick on ``frame``. Returns a small status dict."""

        try:
            return self._tick(frame)
        except Exception as exc:  # keep the macro alive; report and continue
            self._on_error("tick", str(exc))
            return {"error": str(exc)}

    def _tick(self, frame: Frame) -> dict:
        self._last_frame = frame
        self.stats.fps = self._update_fps()

        # uinput needs the frame's pixel size to scale absolute coordinates.
        ss = getattr(self.input, "set_screen_size", None)
        if ss is not None:
            try:
                ss(frame.region.w, frame.region.h)
            except Exception:
                pass

        detections = self.detector.detect(frame)
        self._last_detections = detections
        hud = self.hud.read(frame)
        self.stats.mode = self._mode
        self._should_return(frame, hud)
        anchor = self.anchor(frame)

        # Objective picks the target (or None when the screen is empty).
        target = self.objective.choose(detections, anchor, self.collector)
        self.objective.periodic(self, frame, self.stats, self.now())

        if self._state == "returning":
            self._handle_returning(frame, hud)
        elif target is None:
            self._idle_wander(frame)
        else:
            self._move_to_target(target, frame)
            self._maybe_collect(target)
            self.objective.arrive(self, target)

        self._gather(frame)

        # Webhook heartbeat + status.
        if self.webhook is not None:
            self.webhook.maybe_heartbeat(self.stats, frame)
        self._emit_status(frame, target, hud)

        return {
            "state": self._state,
            "mode": self._mode,
            "target": target.detection.label if target else None,
            "detections": self.collector.summary(detections),
            "honey": round(hud.honey_fraction, 3),
            "fps": round(self._fps, 1),
        }

    # -- movement ---------------------------------------------------------
    def _move_keys_for(self, dx: int, dy: int) -> set[str]:
        keys = set()
        dz = self.config.deadzone_px
        mk = self.config.move_keys
        if dy < -dz:
            keys.add("forward")
        elif dy > dz:
            keys.add("back")
        if dx < -dz:
            keys.add("left")
        elif dx > dz:
            keys.add("right")
        return keys

    def _apply_move(self, desired: set[str]) -> None:
        if desired == self._held_move:
            return
        added = desired - self._held_move
        removed = self._held_move - desired
        mk = self.config.move_keys
        for name in removed:
            self.input.key_up(mk[name])
        for name in added:
            self.input.key_down(mk[name])
        if added or removed:
            self.stats.moves += 1
        self._held_move = desired

    def _release_movement(self) -> None:
        mk = self.config.move_keys
        for name in list(self._held_move):
            try:
                self.input.key_up(mk[name])
            except Exception:
                pass
        self._held_move = set()

    def _move_to_target(self, target: Target, frame: Frame) -> None:
        self._state = "collecting"
        if self.config.move_method == "click":
            cx, cy = target.center
            self.input.click(self.config.gather_button, cx, cy, 1)
            return
        dx = target.detection.rect.cx - frame.width // 2
        dy = target.detection.rect.cy - frame.height // 2
        self._apply_move(self._move_keys_for(dx, dy))

    def _maybe_collect(self, target: Target) -> None:
        if target.distance <= self.config.arrive_radius_px:
            label = target.detection.label
            self.stats.record_collected(label)
            if label == "stinger":
                self.stats.stinger_drops += 1
                self.stats.last_event = "Picked up stinger"
                self.stats.last_event_at = self.now()
                if self.webhook is not None:
                    self.webhook.notify_event("stinger", self.stats, self._last_frame)
            if label == "windy":
                self.stats.windy_events += 1
                self.stats.last_event = "Collected windy bee"
                self.stats.last_event_at = self.now()
                if self.webhook is not None:
                    self.webhook.notify_event("windy", self.stats, self._last_frame)

    def _idle_wander(self, frame: Frame) -> None:
        self._state = "idle"
        self._release_movement()
        if not self.config.field_cfg.random_walk:
            return
        now = self.now()
        if now < self._wander_next:
            return
        # Orbit a point near the field centre so we keep sweeping tokens.
        self._wander_angle += random.uniform(0.4, 1.2) * (1 if random.random() > 0.5 else -1)
        fx0, fy0, fx1, fy1 = self.config.field_cfg.wander_region
        cx = int((fx0 + fx1) / 2 * frame.width)
        cy = int((fy0 + fy1) / 2 * frame.height)
        radius = 0.25 * min(frame.width, frame.height)
        tx = int(cx + math.cos(self._wander_angle) * radius) - frame.width // 2
        ty = int(cy + math.sin(self._wander_angle) * radius) - frame.height // 2
        self._apply_move(self._move_keys_for(tx, ty))
        self._wander_next = now + random.uniform(2.5, 5.0)

    # -- conversion -------------------------------------------------------
    def _should_convert(self, frame: Frame, hud) -> bool:
        if not self.config.convert.enabled:
            return False
        if self.now() < self._convert_cooldown:
            return False
        if hud.converting:
            return True
        if self.config.convert.pollens_before:
            total = sum(v for k, v in self.stats.collected.items()
                        if k in ("pollen", "honey", "token"))
            if total >= self.config.convert.pollens_before:
                return True
        return False

    def _handle_returning(self, frame: Frame, hud) -> None:
        hx0, hy0, hx1, hy1 = self.config.convert.hive_region
        hx = int((hx0 + hx1) / 2 * frame.width)
        hy = int((hy0 + hy1) / 2 * frame.height)
        dx = hx - frame.width // 2
        dy = hy - frame.height // 2
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= self.config.arrive_radius_px * 2:
            if self.config.convert.key:
                self.press(self.config.convert.key)
            self.stats.conversions += 1
            self.stats.last_event = "Converted at hive"
            self.stats.last_event_at = self.now()
            self._convert_cooldown = self.now() + 5.0
            self._state = "collecting"
            self._release_movement()
            if self.webhook is not None:
                self.webhook.notify_event("convert", self.stats, self._last_frame)
        else:
            self._apply_move(self._move_keys_for(dx, dy))

    # -- gather (auto-collect clicks) ------------------------------------
    def _gather(self, frame: Frame) -> None:
        cps = self.config.gather_cps
        if cps <= 0:
            return
        interval = 1.0 / max(1, cps)
        now = self.now()
        if now - self._last_gather < interval:
            return
        self._last_gather = now
        # Click slightly below centre — where the bee's gather action lands.
        x = frame.width // 2
        y = int(frame.height * 0.62)
        self.input.click(self.config.gather_button, x, y, 1)
        self.stats.clicks += 1

    # -- housekeeping -----------------------------------------------------
    def _should_return(self, frame: Frame, hud) -> bool:
        if self._should_convert(frame, hud) and self._state != "returning":
            self._state = "returning"
            self.stats.last_event = "Honey full — returning to hive"
            self.stats.last_event_at = self.now()
            return True
        return False

    def _update_fps(self) -> float:
        now = time.perf_counter()
        dt = now - self._fps_at
        if dt >= 1.0:
            self._fps = 1.0 / max(1e-6, dt) if dt else self._fps
            self._fps_at = now
            return self._fps
        return self._fps

    def _focus_if_needed(self) -> None:
        if not self.config.safety.require_focus:
            return
        focus = getattr(self.input, "focus_sober", None)
        if focus is None:
            return
        try:
            focus(self.config.window_title_contains,
                 self.config.window_process_contains)
        except Exception:
            pass

    def _emit_status(self, frame: Frame, target: Optional[Target], hud) -> None:
        if self.status_cb is None:
            return
        now = self.now()
        if now - self._last_status < self.config.status_interval_sec:
            return
        self._last_status = now
        try:
            self.status_cb({
                "state": self._state, "mode": self._mode,
                "target": target.detection.label if target else None,
                "honey": round(hud.honey_fraction, 3),
                "tokens": sum(self.stats.collected.values()),
                "fps": round(self._fps, 1),
                "collected": dict(self.stats.collected),
            })
        except Exception:
            pass

    def _on_error(self, where: str, detail: str) -> None:
        self._errors += 1
        self.stats.errors += 1
        self.stats.last_event = f"Error in {where}: {detail}"
        self.stats.last_event_at = self.now()
        if self.webhook is not None:
            self.webhook.notify_event("error", self.stats, self._last_frame)
        if self.config.safety.panic_on_error and \
                self._errors >= self.config.safety.stop_after_errors:
            self._stop.set()
            self._release_movement()

    # helper for tests / status
    def last_summary(self) -> dict:
        return {
            "state": self._state, "mode": self._mode,
            "detections": self.collector.summary(self._last_detections),
            "collected": dict(self.stats.collected),
        }
