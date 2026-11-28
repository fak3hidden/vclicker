import os
import tempfile
import unittest

import numpy as np

from bssmacro.calibrate import crop_to_template, grab_screenshot
from bssmacro.types import Rect


class TestCalibrate(unittest.TestCase):
    def test_crop_to_template(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[10:30, 20:40] = (0, 255, 0)   # green square
        crop = crop_to_template(img, Rect(20, 10, 20, 20))
        self.assertEqual(crop.shape[:2], (20, 20))
        self.assertTrue(np.all(crop[:, :, 1] == 255))

    def test_grab_screenshot_headless(self):
        # With no X display this must fail gracefully (return None), not raise.
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "shot.png")
            result = grab_screenshot(out)
            self.assertTrue(result is None or isinstance(result, str))


if __name__ == "__main__":
    unittest.main()
