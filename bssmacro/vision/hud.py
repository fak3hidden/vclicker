"""Best-effort HUD reading.

There is no public BSS API, so the macro estimates HUD state from pixels:

* the honey / convert bar fill is measured as the fraction of "honey-coloured"
  pixels inside a configurable rectangle (given as fractions of the window);
* ``in_hive`` is a coarse flag the engine sets itself when it walks back to the
  hive marker.

OCR (tesseract) would give exact numbers but is optional and slow; the macro's
progress reporting mostly relies on its own counters (see
:class:`bssmacro.types.Stats`) plus this bar estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..types import Frame, HudState, Rect


@dataclass
class HudConfig:
    # Fractions of the frame: (x0, y0, x1, y1).  All zero -> disabled.
    honey_region: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # Honey / convert bar colour in HSV plus a tolerance box.
    honey_hsv: tuple[int, int, int] = (35, 180, 200)
    honey_tol: tuple[int, int, int] = (25, 80, 60)
    convert_threshold: float = 0.85     # fraction that triggers a return-to-hive


def _region_rect(fraction: tuple[float, float, float, float],
                 frame: Frame) -> Optional[Rect]:
    x0, y0, x1, y1 = fraction
    if x0 == y0 == x1 == y1 == 0.0:
        return None
    w, h = frame.width, frame.height
    return Rect(int(x0 * w), int(y0 * h),
                max(1, int((x1 - x0) * w)), max(1, int((y1 - y0) * h)))


class HudReader:
    def __init__(self, config: Optional[HudConfig] = None) -> None:
        self.cfg = config or HudConfig()

    def read(self, frame: Frame) -> HudState:
        honey = self._bar_fill(frame, self.cfg.honey_region, self.cfg.honey_hsv,
                              self.cfg.honey_tol)
        return HudState(honey_fraction=honey, converting=honey >= self.cfg.convert_threshold)

    def _bar_fill(self, frame: Frame, fraction, hsv_center, tol) -> float:
        import cv2

        rect = _region_rect(fraction, frame)
        if rect is None:
            return 0.0
        crop = frame.bgr[rect.y:rect.bottom, rect.x:rect.right]
        if crop.size == 0:
            return 0.0
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        lower = np.array([max(0, hsv_center[0] - tol[0]),
                          max(0, hsv_center[1] - tol[1]),
                          max(0, hsv_center[2] - tol[2])], np.uint8)
        upper = np.array([min(179, hsv_center[0] + tol[0]),
                          min(255, hsv_center[1] + tol[1]),
                          min(255, hsv_center[2] + tol[2])], np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        total = mask.size
        if total == 0:
            return 0.0
        return float(np.count_nonzero(mask)) / total

    def should_convert(self, frame: Frame) -> bool:
        return self.read(frame).converting
