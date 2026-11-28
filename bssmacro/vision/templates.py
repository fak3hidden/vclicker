"""Template storage for the token detector.

Templates are small PNG crops of the on-screen thing you want to recognise
(honey token, windy bee, a spider, …). They live in one folder; the filename
``stem`` becomes the label, e.g. ``honey.png`` -> label ``honey``,
``treat__gumdrop.png`` -> label ``treat``. An optional ``manifest.json`` can
override the inferred category / weight.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..catalog import category_of


@dataclass(slots=True)
class Template:
    label: str
    bgr: np.ndarray            # H x W x 3 uint8
    gray: np.ndarray           # H x W uint8
    category: str
    meta: dict = field(default_factory=dict)

    @property
    def size(self) -> tuple[int, int]:
        return (self.gray.shape[1], self.gray.shape[0])


def _load_image(path: str) -> Optional[np.ndarray]:
    import cv2

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return img


class TemplateStore:
    """Loads, holds and matches template images."""

    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.templates: list[Template] = []
        self.manifest: dict = {}
        self.load()

    # -- loading ----------------------------------------------------------
    def load(self) -> None:
        self.templates = []
        if not os.path.isdir(self.folder):
            return
        manifest_path = os.path.join(self.folder, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    self.manifest = json.load(fh)
            except (OSError, ValueError):
                self.manifest = {}
        for name in sorted(os.listdir(self.folder)):
            if not name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            stem = os.path.splitext(name)[0]
            if stem in ("manifest", "readme", "_window"):
                continue
            label = self.manifest.get("labels", {}).get(name, stem)
            img = _load_image(os.path.join(self.folder, name))
            if img is None:
                continue
            import cv2

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self.templates.append(Template(
                label=label, bgr=img, gray=gray,
                category=category_of(label)))

    def add(self, label: str, bgr: np.ndarray) -> None:
        import cv2

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        self.templates.append(Template(label, bgr, gray, category_of(label)))

    def labels(self) -> list[str]:
        return [t.label for t in self.templates]

    def has(self, label: str) -> bool:
        return any(t.label == label for t in self.templates)

    def empty(self) -> bool:
        return not self.templates

    # -- matching ---------------------------------------------------------
    def match(self, frame_gray: np.ndarray, threshold: float,
              scales: list[float]) -> list[tuple[str, str, float, int, int, int, int]]:
        """Return raw hits: (label, category, score, x, y, w, h)."""

        import cv2

        out: list[tuple[str, str, float, int, int, int, int]] = []
        fh, fw = frame_gray.shape[:2]
        for tpl in self.templates:
            th, tw = tpl.gray.shape[:2]
            if th < 4 or tw < 4 or th > fh or tw > fw:
                continue
            for scale in scales:
                st = max(4, int(tw * scale))
                sh = max(4, int(th * scale))
                if st >= fw or sh >= fh:
                    continue
                if abs(scale - 1.0) > 1e-6:
                    t = cv2.resize(tpl.gray, (st, sh), interpolation=cv2.INTER_AREA)
                else:
                    t = tpl.gray
                try:
                    res = cv2.matchTemplate(frame_gray, t, cv2.TM_CCOEFF_NORMED)
                except cv2.error:
                    continue
                loc = np.where(res >= threshold)
                for y, x in zip(*loc):
                    out.append((tpl.label, tpl.category, float(res[y, x]),
                                int(x), int(y), st, sh))
        return out
