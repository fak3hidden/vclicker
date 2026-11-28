import numpy as np
import unittest

from bssmacro.types import Rect
from bssmacro.vision.detector import DetectorConfig, TokenDetector, nms
from bssmacro.vision.templates import Template, TemplateStore
from .helpers import frame_with, honey_bgr, treat_bgr


class TestColorDetection(unittest.TestCase):
    def test_honey_and_treat_found(self):
        store = TemplateStore("/nonexistent-path")
        det = TokenDetector(store, DetectorConfig(color_min_area=30))
        frame = frame_with(400, 300, [
            (100, 100, 16, honey_bgr()),   # gold -> honey
            (300, 200, 16, treat_bgr()),   # red -> treat
        ])
        found = det.detect(frame)
        labels = {d.label for d in found}
        self.assertIn("honey", labels)
        self.assertIn("treat", labels)

    def test_empty_frame_no_detections(self):
        store = TemplateStore("/nonexistent-path")
        det = TokenDetector(store, DetectorConfig())
        frame = frame_with(400, 300, [])
        self.assertEqual(det.detect(frame), [])


class TestTemplateMatching(unittest.TestCase):
    def test_match_placed_template(self):
        rng = np.random.RandomState(0)
        pattern = rng.randint(0, 255, (24, 24, 3), dtype=np.uint8)
        store = TemplateStore("/nonexistent-path")
        store.add("marker", pattern)

        frame_img = np.zeros((200, 200, 3), dtype=np.uint8)
        frame_img[80:104, 120:144] = pattern   # paste at (120,80)
        from bssmacro.types import Frame
        frame = Frame(bgr=frame_img, region=Rect(0, 0, 200, 200))

        det = TokenDetector(store, DetectorConfig(threshold=0.6))
        found = det.detect(frame)
        self.assertTrue(any(d.label == "marker" for d in found))
        marker = [d for d in found if d.label == "marker"][0]
        # centre should be near (132, 92)
        self.assertLess(abs(marker.rect.cx - 132), 12)
        self.assertLess(abs(marker.rect.cy - 92), 12)

    def test_scaled_template(self):
        import cv2

        rng = np.random.RandomState(1)
        pattern = rng.randint(0, 255, (40, 40, 3), dtype=np.uint8)
        # The frame patch must be the *same* resize the detector will produce,
        # otherwise the normalised correlation between two different subsamples
        # of random noise is ~0.
        small = cv2.resize(pattern, (20, 20), interpolation=cv2.INTER_AREA)
        store = TemplateStore("/nonexistent-path")
        store.add("big", pattern)
        frame_img = np.zeros((300, 300, 3), dtype=np.uint8)
        frame_img[100:120, 100:120] = small
        from bssmacro.types import Frame

        frame = Frame(bgr=frame_img, region=Rect(0, 0, 300, 300))
        det = TokenDetector(store, DetectorConfig(threshold=0.6, scales=[0.5]))
        found = det.detect(frame)
        self.assertTrue(any(d.label == "big" for d in found))


class TestNMS(unittest.TestCase):
    def test_dedup_overlapping(self):
        from bssmacro.types import Detection

        a = Detection("honey", 0.9, Rect(10, 10, 20, 20))
        b = Detection("honey", 0.5, Rect(12, 12, 20, 20))  # overlaps a
        kept = nms([a, b], 0.3)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].score, 0.9)

    def test_keep_non_overlapping(self):
        from bssmacro.types import Detection

        a = Detection("honey", 0.9, Rect(10, 10, 20, 20))
        b = Detection("honey", 0.8, Rect(200, 200, 20, 20))
        self.assertEqual(len(nms([a, b], 0.3)), 2)


if __name__ == "__main__":
    unittest.main()
