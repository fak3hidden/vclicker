"""Calibration: harvest template images from your actual Bee Swarm session.

Templates are what the detector recognises. The easiest way to make them is to
let the macro screenshot your Sober window, then crop a few examples of each
thing you care about. This module does the screenshot + interactive cropping; the
resulting PNGs land in your templates folder and are picked up on the next run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

# Default set of labels worth cropping.  Extend freely — any filename stem in the
# templates folder becomes a usable label.
DEFAULT_LABELS = [
    "honey", "treat", "royal_jelly", "star", "gift", "bubble", "glue",
    "windy", "spider", "stinger", "hive",
]


def crop_to_template(image: np.ndarray, rect) -> np.ndarray:
    """Return the sub-image inside ``rect`` (x, y, w, h)."""

    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    x = max(0, min(x, image.shape[1] - 1))
    y = max(0, min(y, image.shape[0] - 1))
    x2 = max(x + 1, min(x + w, image.shape[1]))
    y2 = max(y + 1, min(y + h, image.shape[0]))
    return image[y:y2, x:x2].copy()


def grab_screenshot(out_path: str, cfg=None) -> Optional[str]:
    """Save a screenshot of the Sober window (or full screen) to ``out_path``."""

    import cv2

    try:
        from .capture.capture import CaptureConfig, ScreenCapture

        capture = ScreenCapture(CaptureConfig(
            title_contains=cfg.window_title_contains if cfg else None,
            process_contains=cfg.window_process_contains if cfg else None,
        ))
        frame = capture.grab()
        cv2.imwrite(out_path, frame.bgr)
        capture.close()
        return out_path
    except Exception:
        # Fall back to a full-screen grab via mss if window detection fails.
        try:
            import mss

            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[0])
                arr = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(
                    shot.height, shot.width, 3)
                cv2.imwrite(out_path, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
            return out_path
        except Exception:
            return None


@dataclass
class _DragState:
    drawing: bool = False
    sx: int = 0
    sy: int = 0
    ex: int = 0
    ey: int = 0


def interactive_crop(image_path: str, out_dir: str,
                     labels: list[str]) -> list[str]:
    """Open the screenshot and let the user drag a box for each label.

    Returns the list of labels that were successfully cropped. On a headless
    machine (no ``DISPLAY`` / no GUI backend) it returns ``[]`` and the caller
    should fall back to printing manual instructions.
    """

    import cv2

    if not os.environ.get("DISPLAY"):
        return []
    img = cv2.imread(image_path)
    if img is None:
        return []
    os.makedirs(out_dir, exist_ok=True)
    saved: list[str] = []
    for label in labels:
        state = _DragState()

        def on_mouse(event, x, y, _flags, _param):
            if event == cv2.EVENT_LBUTTONDOWN:
                state.drawing = True
                state.sx, state.sy = x, y
                state.ex, state.ey = x, y
            elif event == cv2.EVENT_MOUSEMOVE and state.drawing:
                state.ex, state.ey = x, y
            elif event == cv2.EVENT_LBUTTONUP:
                state.drawing = False

        win = f"Crop: {label}  (drag a box, any key to save, ESC to skip)"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(win, on_mouse)
        while True:
            view = img.copy()
            cv2.rectangle(view, (state.sx, state.sy), (state.ex, state.ey),
                         (0, 255, 0), 2)
            cv2.imshow(win, view)
            key = cv2.waitKey(20) & 0xFF
            if key == 27:  # ESC -> skip this label
                break
            if key != 255 and not state.drawing and \
                    abs(state.ex - state.sx) > 4 and abs(state.ey - state.sy) > 4:
                x = min(state.sx, state.ex); y = min(state.sy, state.ey)
                w = abs(state.ex - state.sx); h = abs(state.ey - state.sy)
                crop = crop_to_template(img, _rect(x, y, w, h))
                out = os.path.join(out_dir, f"{label}.png")
                cv2.imwrite(out, crop)
                saved.append(label)
                break
        cv2.destroyWindow(win)
    return saved


def _rect(x: int, y: int, w: int, h: int):
    from .types import Rect

    return Rect(x, y, w, h)


def run_calibrate(args) -> int:
    from .config import MacroConfig

    cfg = MacroConfig.load(getattr(args, "config", None))
    labels = getattr(args, "labels", None) or DEFAULT_LABELS
    out_dir = getattr(args, "templates_dir", None) or cfg.templates_dir
    os.makedirs(out_dir, exist_ok=True)

    shot_path = os.path.join(out_dir, "_window.png")
    print(f"[calibrate] Capturing Sober window -> {shot_path}")
    path = grab_screenshot(shot_path, cfg)
    if path is None:
        print("[calibrate] Could not capture the screen (no X display / Sober "
              "not running?).")
        print(f"[calibrate] Place screenshots manually in: {out_dir}")
        _print_manual(labels, out_dir)
        return 1

    print(f"[calibrate] Saved screenshot: {path}")
    saved = interactive_crop(path, out_dir, labels)
    if saved:
        print(f"[calibrate] Cropped templates: {', '.join(saved)}")
    else:
        print("[calibrate] Interactive cropping unavailable in this environment.")
        _print_manual(labels, out_dir)
    return 0


def _print_manual(labels: list[str], out_dir: str) -> None:
    print("\nManual template setup:")
    print(f"  1. Copy token/creature screenshots into: {out_dir}")
    print("  2. Name each file by its label, e.g.:")
    for lab in labels[:6]:
        print(f"       {lab}.png")
    print("  3. Run the macro — templates are loaded automatically.\n")
