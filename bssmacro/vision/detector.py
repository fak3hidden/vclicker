"""The token detector.

Two complementary strategies:

1. **Template matching** — exact recognition of things you cropped with the
   ``calibrate`` tool (honey, treats, windy bee, spiders…). Best precision.
2. **Colour-blob fallback** — when no template matches, bright saturated
   tokens are still found by hue and reported as ``token`` (or a hue bucket).
   This is what lets the collector work *before* you have harvested templates.

Both feeds are merged and de-duplicated with non-maximum suppression.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..catalog import category_of
from ..types import Detection, Frame, Rect
from .templates import TemplateStore

# HSV hue buckets -> label.  Ranges are (h_lo, h_hi, s_lo, s_hi, v_lo, v_hi).
# Values are deliberately loose; the collector ranks by priority, not colour.
COLOR_BUCKETS: dict[str, tuple[int, int, int, int, int, int]] = {
    "honey": (18, 45, 90, 255, 120, 255),       # gold / amber
    "treat": (0, 12, 120, 255, 120, 255),       # red gumdrops
    "royal_jelly": (180, 200, 60, 255, 120, 255),  # light blue / cyan
    "star": (85, 110, 60, 255, 160, 255),       # cyan-green (star treats)
    "bubble": (95, 130, 40, 200, 170, 255),     # pale blue bubbles
    "glue": (0, 180, 0, 40, 200, 255),          # near-white glue
    "white": (0, 180, 0, 50, 210, 255),         # white-ish tokens
}


@dataclass
class DetectorConfig:
    threshold: float = 0.72          # template match minimum score
    scales: list[float] = field(default_factory=lambda: [0.8, 1.0, 1.25])
    color_tokens: bool = True
    color_min_area: int = 40
    color_max_area: int = 9000
    nms_iou: float = 0.3
    max_per_label: int = 40


def _iou(a: Rect, b: Rect) -> float:
    xa = max(a.x, b.x); ya = max(a.y, b.y)
    xb = min(a.right, b.right); yb = min(a.bottom, b.bottom)
    iw = max(0, xb - xa); ih = max(0, yb - ya)
    inter = iw * ih
    if inter == 0:
        return 0.0
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union else 0.0


def nms(detections: list[Detection], iou: float) -> list[Detection]:
    """Keep the highest-scoring detection in each overlapping cluster."""

    by_label: dict[str, list[Detection]] = {}
    for d in detections:
        by_label.setdefault(d.label, []).append(d)
    kept: list[Detection] = []
    for group in by_label.values():
        group.sort(key=lambda d: d.score, reverse=True)
        for d in group:
            if all(_iou(d.rect, k.rect) < iou for k in kept if k.label == d.label):
                kept.append(d)
    return kept


class TokenDetector:
    """Turns a frame into a deduplicated list of :class:`Detection`."""

    def __init__(self, store: TemplateStore,
                 config: Optional[DetectorConfig] = None) -> None:
        self.store = store
        self.cfg = config or DetectorConfig()

    def detect(self, frame: Frame) -> list[Detection]:
        import cv2

        detections: list[Detection] = []
        gray = frame.to_gray()
        if not self.store.empty():
            hits = self.store.match(gray, self.cfg.threshold, self.cfg.scales)
            for label, category, score, x, y, w, h in hits:
                detections.append(Detection(
                    label=label, score=float(score),
                    rect=Rect(x, y, w, h), category=category))
        if self.cfg.color_tokens:
            detections.extend(self._color_tokens(cv2.cvtColor(frame.bgr, cv2.COLOR_BGR2HSV)))
        return nms(detections, self.cfg.nms_iou)

    def _color_tokens(self, hsv: np.ndarray) -> list[Detection]:
        import cv2

        found: list[Detection] = []
        h, w = hsv.shape[:2]
        for label, (h0, h1, s0, s1, v0, v1) in COLOR_BUCKETS.items():
            lower = np.array([h0, s0, v0], np.uint8)
            upper = np.array([h1, s1, v1], np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < self.cfg.color_min_area or area > self.cfg.color_max_area:
                    continue
                x, y, bw, bh = cv2.boundingRect(c)
                if bw < 3 or bh < 3:
                    continue
                cx, cy = x + bw // 2, y + bh // 2
                if not (0 <= cx < w and 0 <= cy < h):
                    continue
                # Cheap circularity proxy so we don't grab bars / UI.
                perim = cv2.arcLength(c, True) or 1.0
                circ = 4 * math.pi * area / (perim * perim)
                score = min(1.0, 0.55 + 0.45 * circ)
                found.append(Detection(
                    label=label, score=float(score),
                    rect=Rect(x, y, bw, bh), category=category_of(label),
                    meta={"method": "color"}))
        return found

    def detect_label(self, frame: Frame, label: str) -> list[Detection]:
        """Only return detections whose label matches (used for creatures)."""

        return [d for d in self.detect(frame) if d.label == label]
