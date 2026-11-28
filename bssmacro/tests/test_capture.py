import unittest

from bssmacro.capture.capture import CaptureConfig, ScreenCapture, SyntheticCapture
from bssmacro.types import Frame, Rect, empty_frame


class TestSyntheticCapture(unittest.TestCase):
    def test_from_list(self):
        frames = [empty_frame(64, 48), empty_frame(64, 48)]
        cap = SyntheticCapture(frames)
        f1 = cap.grab()
        f2 = cap.grab()
        self.assertEqual((f1.width, f1.height), (64, 48))
        self.assertEqual(cap.region().w, 640)

    def test_from_callable(self):
        calls = {"n": 0}

        def gen() -> Frame:
            calls["n"] += 1
            return empty_frame(32, 32)

        cap = SyntheticCapture(gen)
        cap.grab()
        cap.grab()
        self.assertEqual(calls["n"], 2)


class TestCaptureConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = CaptureConfig()
        self.assertEqual(cfg.downscale, 1.0)
        self.assertIsNone(cfg.fixed_region)


class TestScreenCaptureNoDisplay(unittest.TestCase):
    def test_construct_without_window(self):
        # Constructing must not touch X; locating the window is lazy.
        cap = ScreenCapture(CaptureConfig(fixed_region=Rect(0, 0, 100, 100)))
        self.assertIsNotNone(cap)

    def test_region_fixed(self):
        cap = ScreenCapture(CaptureConfig(fixed_region=Rect(5, 5, 50, 60)))
        self.assertEqual(cap.region().as_tuple(), (5, 5, 50, 60))


if __name__ == "__main__":
    unittest.main()
