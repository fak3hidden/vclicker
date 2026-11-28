"""Synthetic frame builders shared across the tests."""

from __future__ import annotations

import cv2
import numpy as np

from bssmacro.types import Frame, Rect


def blank(w: int = 400, h: int = 300, bgr=(0, 0, 0)) -> np.ndarray:
    return np.full((h, w, 3), bgr, dtype=np.uint8)


def circle(img: np.ndarray, cx: int, cy: int, r: int, bgr) -> None:
    cv2.circle(img, (cx, cy), r, bgr, -1)


def frame_with(w: int, h: int, blobs):
    """blobs: list of (cx, cy, radius, bgr)."""

    img = blank(w, h)
    for cx, cy, r, bgr in blobs:
        circle(img, cx, cy, r, bgr)
    return Frame(bgr=img, region=Rect(0, 0, w, h))


def honey_bgr() -> tuple[int, int, int]:
    return (30, 200, 255)        # gold


def treat_bgr() -> tuple[int, int, int]:
    return (0, 0, 255)           # red


def stinger_bgr() -> tuple[int, int, int]:
    return (0, 255, 255)         # cyan-ish (falls in a colour bucket / generic)
