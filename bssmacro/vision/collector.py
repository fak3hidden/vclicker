"""The AI collector.

Given every detection in the current frame, the collector decides **what to walk
toward next**. That is the "AI": it scores each candidate by your priority
weights, prefers nearer targets, and refuses to chase things you told it to
avoid. Output is a single ranked :class:`Target` (or ``None`` when the screen is
empty), which the engine feeds straight into the movement controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..catalog import PriorityRule
from ..types import Detection, Target


@dataclass
class CollectorConfig:
    priorities: list[PriorityRule] = field(default_factory=list)
    default_weight: float = 1.0
    default_enabled: bool = True
    avoid: list[str] = field(default_factory=list)   # labels never chased
    max_distance: int = 0            # 0 = no cap (pixels from anchor)
    min_score: float = 0.0          # global confidence floor


class Collector:
    """Rank detections into a single navigation target using your priorities."""

    def __init__(self, config: CollectorConfig) -> None:
        self.cfg = config
        self._index: dict[str, PriorityRule] = {}
        for rule in config.priorities:
            self._index.setdefault(rule.label, rule)
        self._default = self._index.get("default") or PriorityRule(
            "default", config.default_enabled, config.default_weight)

    def _rule_for(self, label: str) -> PriorityRule:
        return self._index.get(label, self._default)

    def should_avoid(self, detection: Detection) -> bool:
        if detection.label in self.cfg.avoid:
            return True
        if detection.score < self.cfg.min_score:
            return True
        rule = self._rule_for(detection.label)
        return not rule.enabled or detection.score < rule.min_score

    def _weight(self, detection: Detection) -> float:
        return float(self._rule_for(detection.label).weight)

    def rank(self, detections: list[Detection],
             anchor: tuple[int, int]) -> list[Target]:
        """Return all valid targets sorted best-first."""

        ax, ay = anchor
        targets: list[Target] = []
        for d in detections:
            if self.should_avoid(d):
                continue
            dx = d.rect.cx - ax
            dy = d.rect.cy - ay
            dist = (dx * dx + dy * dy) ** 0.5
            if self.cfg.max_distance and dist > self.cfg.max_distance:
                continue
            targets.append(Target(detection=d, priority_weight=self._weight(d),
                                  distance=dist,
                                  reason=f"{d.label} @ {dist:.0f}px"))
        # Highest priority weight first; then nearest; then most confident.
        targets.sort(key=lambda t: (-t.priority_weight, t.distance, -t.detection.score))
        return targets

    def best(self, detections: list[Detection],
             anchor: tuple[int, int]) -> Optional[Target]:
        ranked = self.rank(detections, anchor)
        return ranked[0] if ranked else None

    def best_of_label(self, detections: list[Detection], label: str,
                      anchor: tuple[int, int]) -> Optional[Target]:
        """Best target whose label matches exactly (used by creature objectives)."""

        same = [d for d in detections if d.label == label]
        return self.best(same, anchor)

    def summary(self, detections: list[Detection]) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in detections:
            out[d.label] = out.get(d.label, 0) + 1
        return out
