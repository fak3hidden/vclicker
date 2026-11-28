"""Vision: detection, priority ranking and HUD reading."""

from __future__ import annotations

from .collector import Collector, CollectorConfig
from .detector import DetectorConfig, TokenDetector, nms
from .hud import HudConfig, HudReader
from .templates import Template, TemplateStore

__all__ = [
    "Collector", "CollectorConfig", "DetectorConfig", "TokenDetector", "nms",
    "HudConfig", "HudReader", "Template", "TemplateStore",
]
