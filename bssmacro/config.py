"""Top-level macro configuration.

Everything the engine needs lives here. Defaults are chosen to be safe and to
work out-of-the-box on a typical Sober setup; you tune them via the config JSON
or the ``bssmacro config`` / ``calibrate`` CLI tools.

Config file location (overridable with ``--config path.json``)::

    ~/.config/vclicker/bssmacro/config.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .capture.capture import CaptureConfig
from .catalog import PriorityRule, default_priorities
from .vision.collector import CollectorConfig
from .vision.detector import DetectorConfig
from .vision.hud import HudConfig
from .webhook.discord import WebhookConfig

APP_NAME = "vclicker"
CONFIG_DIR = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
    os.path.expanduser("~"), ".config")
BASE_DIR = os.path.join(CONFIG_DIR, APP_NAME, "bssmacro")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
BUNDLED_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "bssmacro", "templates")


# --------------------------------------------------------------------------- #
#  Leaf configs for the subsystems
# --------------------------------------------------------------------------- #
@dataclass
class ConvertConfig:
    enabled: bool = True
    key: str = ""                 # optional key pressed when parked at the hive
    hive_region: tuple[float, float, float, float] = (0.40, 0.80, 0.60, 0.98)
    threshold: float = 0.85       # honey_fraction that triggers a trip home
    pollens_before: int = 0       # alt trigger: collect this many then convert


@dataclass
class FieldConfig:
    name: str = "auto"            # auto | sunflower | mushroom | spider | ...
    wander_region: tuple[float, float, float, float] = (0.15, 0.15, 0.85, 0.85)
    random_walk: bool = True      # drift when no token is on screen


@dataclass
class WindyConfig:
    enabled: bool = False
    spawn_key: str = ""           # key that uses a Cloud Vial (empty = don't)
    spawn_interval_sec: float = 120.0
    collect_key: str = ""         # key pressed when standing on the windy bee
    approach_radius_px: int = 40


@dataclass
class StingerConfig:
    enabled: bool = False
    field: str = "spider"
    kill_key: str = "1"           # ability used to kill spiders
    kill_radius_px: int = 60
    kill_cps: int = 8             # how fast to mash the kill key in range


@dataclass
class SafetyConfig:
    max_runtime_min: float = 0.0  # 0 = run forever
    require_focus: bool = True    # only send input while Sober is focused
    panic_on_error: bool = True
    stop_after_errors: int = 25


# --------------------------------------------------------------------------- #
#  Master config
# --------------------------------------------------------------------------- #
@dataclass
class MacroConfig:
    version: int = 1
    templates_dir: str = BUNDLED_TEMPLATES
    window_title_contains: list[str] = field(
        default_factory=lambda: ["Sober", "Roblox", "sober"])
    window_process_contains: list[str] = field(
        default_factory=lambda: ["sober", "roblox", "RobloxPlayer"])

    input_kind: str = "auto"      # auto | x11 | fake
    move_method: str = "keys"     # keys | click
    move_keys: dict[str, str] = field(
        default_factory=lambda: {"forward": "w", "back": "s",
                                "left": "a", "right": "d"})
    deadzone_px: int = 12
    arrive_radius_px: int = 28
    move_hz: float = 20.0         # re-evaluate movement this often
    gather_cps: int = 0           # auto-collect clicks while moving (0 = off)
    gather_button: str = "left"

    objective: str = "field"      # field | windy | stinger | mixed
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    hud: HudConfig = field(default_factory=HudConfig)
    convert: ConvertConfig = field(default_factory=ConvertConfig)
    field_cfg: FieldConfig = field(default_factory=FieldConfig)
    windy: WindyConfig = field(default_factory=WindyConfig)
    stinger: StingerConfig = field(default_factory=StingerConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)

    status_interval_sec: float = 2.0

    # -- construction -----------------------------------------------------
    @classmethod
    def default(cls) -> "MacroConfig":
        cfg = cls()
        cfg.collector = CollectorConfig(priorities=default_priorities())
        return cfg

    @classmethod
    def from_dict(cls, d: dict) -> "MacroConfig":
        cfg = cls.default()
        cfg.templates_dir = str(d.get("templates_dir", cfg.templates_dir))
        if "window_title_contains" in d:
            cfg.window_title_contains = list(d["window_title_contains"])
        if "window_process_contains" in d:
            cfg.window_process_contains = list(d["window_process_contains"])
        cfg.input_kind = str(d.get("input_kind", cfg.input_kind))
        cfg.move_method = str(d.get("move_method", cfg.move_method))
        mk = d.get("move_keys")
        if isinstance(mk, dict):
            cfg.move_keys.update({k: str(v) for k, v in mk.items()})
        cfg.deadzone_px = int(d.get("deadzone_px", cfg.deadzone_px))
        cfg.arrive_radius_px = int(d.get("arrive_radius_px", cfg.arrive_radius_px))
        cfg.move_hz = float(d.get("move_hz", cfg.move_hz))
        cfg.gather_cps = int(d.get("gather_cps", cfg.gather_cps))
        cfg.gather_button = str(d.get("gather_button", cfg.gather_button))
        cfg.objective = str(d.get("objective", cfg.objective))
        cfg.status_interval_sec = float(d.get("status_interval_sec",
                                              cfg.status_interval_sec))
        if "capture" in d and isinstance(d["capture"], dict):
            c = d["capture"]
            cfg.capture = CaptureConfig(
                downscale=float(c.get("downscale", cfg.capture.downscale)),
                capture_fps=float(c.get("capture_fps", cfg.capture.capture_fps)),
                title_contains=c.get("title_contains"),
                process_contains=c.get("process_contains"),
                method=str(c.get("method", cfg.capture.method)),
                shot_tool=str(c.get("shot_tool", cfg.capture.shot_tool)),
            )
        if "detector" in d and isinstance(d["detector"], dict):
            det = d["detector"]
            cfg.detector = DetectorConfig(
                threshold=float(det.get("threshold", cfg.detector.threshold)),
                scales=list(det.get("scales", cfg.detector.scales)),
                color_tokens=bool(det.get("color_tokens", cfg.detector.color_tokens)),
                color_min_area=int(det.get("color_min_area", cfg.detector.color_min_area)),
                nms_iou=float(det.get("nms_iou", cfg.detector.nms_iou)),
                max_per_label=int(det.get("max_per_label", cfg.detector.max_per_label)),
            )
        if "collector" in d and isinstance(d["collector"], dict):
            col = d["collector"]
            rules = col.get("priorities")
            if rules:
                cfg.collector = CollectorConfig(
                    priorities=[PriorityRule.from_dict(r) for r in rules],
                    default_weight=float(col.get("default_weight",
                                                 cfg.collector.default_weight)),
                    default_enabled=bool(col.get("default_enabled",
                                                  cfg.collector.default_enabled)),
                    avoid=list(col.get("avoid", cfg.collector.avoid)),
                    max_distance=int(col.get("max_distance", cfg.collector.max_distance)),
                    min_score=float(col.get("min_score", cfg.collector.min_score)),
                )
        if "hud" in d and isinstance(d["hud"], dict):
            h = d["hud"]
            cfg.hud = HudConfig(
                honey_region=tuple(h.get("honey_region", cfg.hud.honey_region)),
                honey_hsv=tuple(h.get("honey_hsv", cfg.hud.honey_hsv)),
                honey_tol=tuple(h.get("honey_tol", cfg.hud.honey_tol)),
                convert_threshold=float(h.get("convert_threshold",
                                             cfg.hud.convert_threshold)),
            )
        if "convert" in d and isinstance(d["convert"], dict):
            cv = d["convert"]
            cfg.convert = ConvertConfig(
                enabled=bool(cv.get("enabled", cfg.convert.enabled)),
                key=str(cv.get("key", cfg.convert.key)),
                hive_region=tuple(cv.get("hive_region", cfg.convert.hive_region)),
                threshold=float(cv.get("threshold", cfg.convert.threshold)),
                pollens_before=int(cv.get("pollens_before", cfg.convert.pollens_before)),
            )
        if "field" in d and isinstance(d["field"], dict):
            f = d["field"]
            cfg.field_cfg = FieldConfig(
                name=str(f.get("name", cfg.field_cfg.name)),
                wander_region=tuple(f.get("wander_region", cfg.field_cfg.wander_region)),
                random_walk=bool(f.get("random_walk", cfg.field_cfg.random_walk)),
            )
        if "windy" in d and isinstance(d["windy"], dict):
            w = d["windy"]
            cfg.windy = WindyConfig(
                enabled=bool(w.get("enabled", cfg.windy.enabled)),
                spawn_key=str(w.get("spawn_key", cfg.windy.spawn_key)),
                spawn_interval_sec=float(w.get("spawn_interval_sec",
                                              cfg.windy.spawn_interval_sec)),
                collect_key=str(w.get("collect_key", cfg.windy.collect_key)),
                approach_radius_px=int(w.get("approach_radius_px",
                                             cfg.windy.approach_radius_px)),
            )
        if "stinger" in d and isinstance(d["stinger"], dict):
            s = d["stinger"]
            cfg.stinger = StingerConfig(
                enabled=bool(s.get("enabled", cfg.stinger.enabled)),
                field=str(s.get("field", cfg.stinger.field)),
                kill_key=str(s.get("kill_key", cfg.stinger.kill_key)),
                kill_radius_px=int(s.get("kill_radius_px", cfg.stinger.kill_radius_px)),
                kill_cps=int(s.get("kill_cps", cfg.stinger.kill_cps)),
            )
        if "safety" in d and isinstance(d["safety"], dict):
            s = d["safety"]
            cfg.safety = SafetyConfig(
                max_runtime_min=float(s.get("max_runtime_min",
                                           cfg.safety.max_runtime_min)),
                require_focus=bool(s.get("require_focus", cfg.safety.require_focus)),
                panic_on_error=bool(s.get("panic_on_error", cfg.safety.panic_on_error)),
                stop_after_errors=int(s.get("stop_after_errors",
                                            cfg.safety.stop_after_errors)),
            )
        if "webhook" in d and isinstance(d["webhook"], dict):
            cfg.webhook = WebhookConfig.from_dict(d["webhook"])
        return cfg

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "templates_dir": self.templates_dir,
            "window_title_contains": self.window_title_contains,
            "window_process_contains": self.window_process_contains,
            "input_kind": self.input_kind,
            "move_method": self.move_method,
            "move_keys": dict(self.move_keys),
            "deadzone_px": self.deadzone_px,
            "arrive_radius_px": self.arrive_radius_px,
            "move_hz": self.move_hz,
            "gather_cps": self.gather_cps,
            "gather_button": self.gather_button,
            "objective": self.objective,
            "status_interval_sec": self.status_interval_sec,
            "capture": {
                "downscale": self.capture.downscale,
                "capture_fps": self.capture.capture_fps,
                "title_contains": self.capture.title_contains,
                "process_contains": self.capture.process_contains,
                "method": self.capture.method,
                "shot_tool": self.capture.shot_tool,
            },
            "detector": {
                "threshold": self.detector.threshold,
                "scales": list(self.detector.scales),
                "color_tokens": self.detector.color_tokens,
                "color_min_area": self.detector.color_min_area,
                "nms_iou": self.detector.nms_iou,
                "max_per_label": self.detector.max_per_label,
            },
            "collector": {
                "priorities": [r.to_dict() for r in self.collector.priorities],
                "default_weight": self.collector.default_weight,
                "default_enabled": self.collector.default_enabled,
                "avoid": list(self.collector.avoid),
                "max_distance": self.collector.max_distance,
                "min_score": self.collector.min_score,
            },
            "hud": {
                "honey_region": list(self.hud.honey_region),
                "honey_hsv": list(self.hud.honey_hsv),
                "honey_tol": list(self.hud.honey_tol),
                "convert_threshold": self.hud.convert_threshold,
            },
            "convert": {
                "enabled": self.convert.enabled,
                "key": self.convert.key,
                "hive_region": list(self.convert.hive_region),
                "threshold": self.convert.threshold,
                "pollens_before": self.convert.pollens_before,
            },
            "field": {
                "name": self.field_cfg.name,
                "wander_region": list(self.field_cfg.wander_region),
                "random_walk": self.field_cfg.random_walk,
            },
            "windy": {
                "enabled": self.windy.enabled,
                "spawn_key": self.windy.spawn_key,
                "spawn_interval_sec": self.windy.spawn_interval_sec,
                "collect_key": self.windy.collect_key,
                "approach_radius_px": self.windy.approach_radius_px,
            },
            "stinger": {
                "enabled": self.stinger.enabled,
                "field": self.stinger.field,
                "kill_key": self.stinger.kill_key,
                "kill_radius_px": self.stinger.kill_radius_px,
                "kill_cps": self.stinger.kill_cps,
            },
            "safety": {
                "max_runtime_min": self.safety.max_runtime_min,
                "require_focus": self.safety.require_focus,
                "panic_on_error": self.safety.panic_on_error,
                "stop_after_errors": self.safety.stop_after_errors,
            },
            "webhook": self.webhook.to_dict(),
        }

    # -- io ---------------------------------------------------------------
    def save(self, path: Optional[str] = None) -> str:
        path = path or DEFAULT_CONFIG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path: Optional[str] = None) -> "MacroConfig":
        path = path or DEFAULT_CONFIG_PATH
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return cls.default()
        if not isinstance(data, dict):
            return cls.default()
        return cls.from_dict(data)

    # -- validation -------------------------------------------------------
    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.objective not in ("field", "windy", "stinger", "mixed"):
            problems.append(f"Unknown objective: {self.objective!r}")
        if self.move_method not in ("keys", "click"):
            problems.append(f"Unknown move_method: {self.move_method!r}")
        if not self.collector.priorities:
            problems.append("No priority rules configured.")
        if self.webhook.enabled() and not self.webhook.url.startswith("http"):
            problems.append("Webhook URL does not look like a URL.")
        if self.safety.max_runtime_min < 0:
            problems.append("max_runtime_min must be >= 0.")
        for k in ("forward", "back", "left", "right"):
            if k not in self.move_keys:
                problems.append(f"move_keys missing {k!r}.")
        return problems
