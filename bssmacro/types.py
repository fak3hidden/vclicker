"""Shared data types used across the macro pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass(slots=True)
class Rect:
    """A screen-space rectangle. All coordinates are integers (pixels)."""

    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    def clip_to(self, w: int, h: int) -> "Rect":
        x = max(0, min(self.x, w - 1))
        y = max(0, min(self.y, h - 1))
        right = min(self.right, w)
        bottom = min(self.bottom, h)
        return Rect(x, y, max(1, right - x), max(1, bottom - y))

    def scaled(self, factor: float) -> "Rect":
        return Rect(
            int(self.x * factor), int(self.y * factor),
            max(1, int(self.w * factor)), max(1, int(self.h * factor)),
        )


@dataclass(slots=True)
class Frame:
    """One captured video frame plus the screen region it came from.

    ``bgr`` is an ``H x W x 3`` ``uint8`` array in BGR order (OpenCV's native
    layout). Everything downstream expects BGR so no colour conversion is needed.
    """

    bgr: Any  # np.ndarray
    timestamp: float = field(default_factory=time.perf_counter)
    region: Optional[Rect] = None  # screen-space rect this frame covers
    source: str = "capture"

    @property
    def height(self) -> int:
        return int(self.bgr.shape[0])

    @property
    def width(self) -> int:
        return int(self.bgr.shape[1])

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def center(self) -> tuple[int, int]:
        return (self.width // 2, self.height // 2)

    def to_gray(self) -> Any:
        import cv2

        return cv2.cvtColor(self.bgr, cv2.COLOR_BGR2GRAY)

    def to_hsv(self) -> Any:
        import cv2

        return cv2.cvtColor(self.bgr, cv2.COLOR_BGR2HSV)


@dataclass(slots=True)
class Detection:
    """A single thing the detector found in a frame."""

    label: str  # e.g. "honey", "treat", "stinger", "windy", "spider", "player"
    score: float  # 0..1 confidence
    rect: Rect  # bounding box in *frame* coordinates
    category: str = "token"  # token | creature | hazard | player | hud
    meta: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        return (self.rect.cx, self.rect.cy)

    @property
    def area(self) -> int:
        return self.rect.w * self.rect.h


@dataclass(slots=True)
class Target:
    """A ranked navigation goal produced by the collector."""

    detection: Detection
    priority_weight: float
    distance: float  # pixels from the player anchor to the target centre
    reason: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return self.detection.center


@dataclass(slots=True)
class HudState:
    """Best-effort read of on-screen HUD values."""

    honey_fraction: float = 0.0  # 0..1 fill of the convert/honey bar
    pollen_fraction: float = 0.0  # 0..1 fill of the pollen bar
    converting: bool = False
    in_hive: bool = False
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class Stats:
    """Running counters reported to the webhook / status callback."""

    started_at: float = field(default_factory=time.perf_counter)
    collected: dict[str, int] = field(default_factory=dict)  # label -> count
    clicks: int = 0
    moves: int = 0
    conversions: int = 0
    windy_events: int = 0
    stinger_drops: int = 0
    errors: int = 0
    last_event: str = ""
    last_event_at: float = 0.0
    fps: float = 0.0
    mode: str = "field"

    def record_collected(self, label: str, n: int = 1) -> None:
        self.collected[label] = self.collected.get(label, 0) + n

    def elapsed(self) -> float:
        return time.perf_counter() - self.started_at

    def per_minute(self, value: float) -> float:
        mins = self.elapsed() / 60.0
        if mins <= 0:
            return 0.0
        return value / mins


def empty_frame(width: int = 640, height: int = 480, region: Optional[Rect] = None) -> Frame:
    """Build a black frame (used by tests and the calibration tool)."""

    bgr = np.zeros((height, width, 3), dtype=np.uint8)
    return Frame(bgr=bgr, region=region or Rect(0, 0, width, height))
