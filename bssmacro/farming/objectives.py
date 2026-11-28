"""Farming objectives — what the macro is *trying* to do right now.

The engine asks the active objective for the best target each frame. Objectives
also perform "on arrival" actions (e.g. press the kill key when you reach a
spider) and periodic side-effects (e.g. spawn a windy bee on cooldown).

An ``Objective`` only needs the engine to expose: ``input`` (InputController),
``config``, ``stats``, ``press(key)``, ``now()`` and ``set_mode(text)``. That
keeps this module decoupled from the concrete engine class.
"""

from __future__ import annotations

from typing import Optional

from ..types import Detection, Target


class Objective:
    name = "field"

    def choose(self, detections: list[Detection], anchor, collector) -> Optional[Target]:
        return None

    def arrive(self, engine, target: Target) -> None:
        pass

    def periodic(self, engine, frame, stats, now: float) -> None:
        pass


class FieldObjective(Objective):
    """Default behaviour: walk to the most valuable token on screen."""

    name = "field"

    def choose(self, detections, anchor, collector):
        return collector.best(detections, anchor)


class WindyObjective(Objective):
    name = "windy"

    def __init__(self, config) -> None:
        self.cfg = config.windy
        self._last_spawn = 0.0

    def choose(self, detections, anchor, collector):
        if not self.cfg.enabled:
            return None
        return collector.best_of_label(detections, "windy", anchor)

    def arrive(self, engine, target: Target) -> None:
        if self.cfg.collect_key and target.distance <= self.cfg.approach_radius_px:
            engine.press(self.cfg.collect_key)

    def periodic(self, engine, frame, stats, now):
        # Spawn a windy bee on a cooldown if we have a key and none is present.
        if not self.cfg.enabled or not self.cfg.spawn_key:
            return
        if now - self._last_spawn < self.cfg.spawn_interval_sec:
            return
        # Only spawn if the screen does not already show a windy bee.
        has_windy = any(d.label == "windy" for d in engine._last_detections)
        if has_windy:
            self._last_spawn = now
            return
        engine.press(self.cfg.spawn_key)
        self._last_spawn = now
        stats.windy_events += 1
        stats.last_event = "Spawned windy bee (Cloud Vial)"
        stats.last_event_at = now


class StingerObjective(Objective):
    name = "stinger"

    def __init__(self, config) -> None:
        self.cfg = config.stinger

    def choose(self, detections, anchor, collector):
        if not self.cfg.enabled:
            return None
        return collector.best_of_label(detections, "spider", anchor)

    def arrive(self, engine, target: Target) -> None:
        if not self.cfg.kill_key:
            return
        if target.distance <= self.cfg.kill_radius_px:
            # Mash the kill ability while in range; the engine's per-frame
            # gather loop handles the actual stinger-token pickup.
            engine.press(self.cfg.kill_key, delay=max(0.02, 1.0 / max(1, self.cfg.kill_cps)))


class MixedObjective(Objective):
    """Field collection, but drop everything for a windy bee or a spider."""

    name = "mixed"

    def __init__(self, config) -> None:
        self.windy = WindyObjective(config)
        self.stinger = StingerObjective(config)
        self.field = FieldObjective()

    def choose(self, detections, anchor, collector):
        windy = self.windy.choose(detections, anchor, collector)
        if windy is not None:
            return windy
        spider = self.stinger.choose(detections, anchor, collector)
        if spider is not None:
            return spider
        return self.field.choose(detections, anchor, collector)

    def arrive(self, engine, target: Target) -> None:
        if target.detection.label == "windy":
            self.windy.arrive(engine, target)
        elif target.detection.label == "spider":
            self.stinger.arrive(engine, target)

    def periodic(self, engine, frame, stats, now) -> None:
        self.windy.periodic(engine, frame, stats, now)


def build_objective(config):
    """Return the objective implementation for ``config.objective``."""

    if config.objective == "windy":
        return WindyObjective(config)
    if config.objective == "stinger":
        return StingerObjective(config)
    if config.objective == "mixed":
        return MixedObjective(config)
    return FieldObjective()
