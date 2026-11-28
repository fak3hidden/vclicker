"""Catalogue of the things the macro can recognise in Bee Swarm Simulator.

This is the single source of truth for *labels*. Templates you drop into
``bssmacro/templates/`` are matched to these labels by filename (``honey.png``,
``treat__gumdrop.png`` …), and the colour fallback in the detector maps dominant
hues onto them too.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Categories used for routing inside the engine.
CREATURES = {"windy", "spider", "mantis", "rhino", "scorpion", "werewolf", "kingbeetle"}
HAZARDS = {"spider", "mantis", "rhino", "scorpion", "werewolf", "kingbeetle"}
PLAYER = {"player", "hive"}

# Token / creature labels the macro knows about. Order is irrelevant here; the
# priority ordering lives in DEFAULT_PRIORITIES.
KNOWN_LABELS: tuple[str, ...] = (
    # valuables / boosts
    "stinger", "royal_jelly", "treat", "star", "gift", "honey", "bubble",
    "glue", "oil", "enzymes", "tonic", "field_boost", "magnet", "pollen",
    "gingerbread", "candy", "reindeer", "stump", "cloud", "ant_pass",
    "coconut", "relic", "wavy", "white", "red", "night_bell",
    "blue_boost", "red_boost", "field_dice",
    # creatures / hazards
    "windy", "spider", "mantis", "rhino", "scorpion", "werewolf", "kingbeetle",
    # anchors
    "player", "hive",
    # catch-all
    "token",
)


def category_of(label: str) -> str:
    if label in CREATURES:
        return "creature"
    if label in HAZARDS:
        return "hazard"
    if label in PLAYER:
        return "player"
    return "token"


@dataclass(slots=True)
class PriorityRule:
    label: str
    enabled: bool = True
    weight: float = 1.0
    min_score: float = 0.0

    def to_dict(self) -> dict:
        return {"label": self.label, "enabled": self.enabled,
                "weight": self.weight, "min_score": self.min_score}

    @classmethod
    def from_dict(cls, d: dict) -> "PriorityRule":
        return cls(str(d.get("label", "default")),
                   bool(d.get("enabled", True)),
                   float(d.get("weight", 1.0)),
                   float(d.get("min_score", 0.0)))


# Default priority order (high value first).  This mirrors what veteran BSS
# macros tend to favour: stingers / royal jellies / treats before generic honey.
DEFAULT_PRIORITY_ORDER: list[tuple[str, float]] = [
    ("stinger", 100.0),
    ("royal_jelly", 90.0),
    ("treat", 85.0),
    ("star", 80.0),
    ("gift", 78.0),
    ("field_boost", 72.0),
    ("magnet", 70.0),
    ("honey", 60.0),
    ("bubble", 55.0),
    ("glue", 50.0),
    ("oil", 48.0),
    ("enzymes", 46.0),
    ("tonic", 46.0),
    ("gingerbread", 40.0),
    ("candy", 40.0),
    ("reindeer", 38.0),
    ("pollen", 30.0),
    ("cloud", 25.0),
    ("stump", 22.0),
    ("ant_pass", 20.0),
    ("coconut", 18.0),
    ("relic", 16.0),
    ("wavy", 14.0),
    ("white", 12.0),
    ("red", 12.0),
    ("night_bell", 10.0),
    ("blue_boost", 8.0),
    ("red_boost", 8.0),
    ("field_dice", 8.0),
    # generic catch-all for colour-detected tokens with no specific rule
    ("token", 5.0),
]


def default_priorities(disabled: list[str] | None = None) -> list[PriorityRule]:
    """Build the default priority list, optionally disabling some labels."""

    disabled = set(disabled or [])
    rules: list[PriorityRule] = []
    for label, weight in DEFAULT_PRIORITY_ORDER:
        rules.append(PriorityRule(label, enabled=label not in disabled, weight=weight))
    # A "default" bucket catches anything not explicitly listed.
    rules.append(PriorityRule("default", enabled=True, weight=1.0))
    return rules
