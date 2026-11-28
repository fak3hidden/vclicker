"""Screen capture for the macro.

Two implementations share one interface:

* :class:`ScreenCapture` — uses ``mss`` to grab the Sober window region. The
  dependency is imported lazily so the rest of the package (and its tests) works
  without a display.
* :class:`SyntheticCapture` — yields frames from a caller-supplied generator, so
  the detector / collector / engine can be tested end-to-end with no screen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import numpy as np

from ..types import Frame, Rect
from .window import find_window, WindowFinderUnavailable


def _to_bgr(shot) -> np.ndarray:
    """Convert an mss ScreenShot to an H x W x 3 BGR uint8 array."""

    import cv2

    h, w = shot.height, shot.width
    rgb = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(h, w, 3)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


@dataclass
class CaptureConfig:
    downscale: float = 1.0          # 1.0 = full res; 0.5 = half (faster CV)
    capture_fps: float = 20.0
    title_contains: Optional[list[str]] = None
    process_contains: Optional[list[str]] = None
    fixed_region: Optional[Rect] = None   # override automatic window detection


class ScreenCapture:
    """Grab the Sober window (or a fixed region) into :class:`Frame` objects."""

    def __init__(self, cfg: Optional[CaptureConfig] = None) -> None:
        self.cfg = cfg or CaptureConfig()
        self._window = None
        self._mss = None
        self._last_grab = 0.0

    # -- window management ------------------------------------------------
    def locate_window(self) -> Optional[object]:
        try:
            win = find_window(title_contains=self.cfg.title_contains,
                              process_contains=self.cfg.process_contains)
        except WindowFinderUnavailable as exc:
            raise RuntimeError(f"Cannot find Sober window: {exc}") from exc
        self._window = win
        return win

    def region(self) -> Rect:
        if self.cfg.fixed_region is not None:
            return self.cfg.fixed_region
        if self._window is None:
            self.locate_window()
        if self._window is None:
            raise RuntimeError("Sober window not found — is the game running?")
        return Rect(self._window.x, self._window.y, self._window.w, self._window.h)

    # -- frame grabbing ---------------------------------------------------
    def _ensure_mss(self):
        if self._mss is None:
            import mss

            self._mss = mss.mss()
        return self._mss

    def grab(self) -> Frame:
        region = self.region()
        if self.cfg.downscale and self.cfg.downscale != 1.0:
            f = self.cfg.downscale
            region = Rect(int(region.x * f), int(region.y * f),
                          max(1, int(region.w * f)), max(1, int(region.h * f)))
        mon = {"left": region.x, "top": region.y,
               "width": region.w, "height": region.h}
        sct = self._ensure_mss()
        shot = sct.grab(mon)
        bgr = _to_bgr(shot)
        if self.cfg.downscale and self.cfg.downscale != 1.0:
            import cv2

            bgr = cv2.resize(bgr, (region.w, region.h), interpolation=cv2.INTER_AREA)
        # Convert back to full-resolution frame coordinates.
        full = self.region()
        return Frame(bgr=bgr, region=full, source="mss")

    def close(self) -> None:
        if self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
            self._mss = None


class SyntheticCapture:
    """Feeds pre-built frames to the pipeline — for tests and dry runs.

    Pass either an iterable of :class:`Frame` objects or a zero-argument callable
    that returns a fresh frame each call (handy for procedural test scenes).
    """

    def __init__(self, frames: "Iterator[Frame] | list[Frame] | Callable[[], Frame]") -> None:
        if callable(frames) and not isinstance(frames, (list, tuple)):
            self._callable = frames
            self._gen = None
        else:
            self._callable = None
            self._gen = iter(list(frames))  # type: ignore[arg-type]

    def _next(self) -> Frame:
        if self._callable is not None:
            return self._callable()  # type: ignore[call-arg]
        return next(self._gen)  # type: ignore[arg-type]

    def grab(self) -> Frame:
        return self._next()

    def region(self) -> Rect:
        return Rect(0, 0, 640, 480)

    def close(self) -> None:
        pass
