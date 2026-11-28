import unittest

from bssmacro.types import Frame, Rect, Stats, empty_frame


class TestTypes(unittest.TestCase):
    def test_rect_math(self):
        r = Rect(10, 20, 100, 50)
        self.assertEqual(r.cx, 60)
        self.assertEqual(r.cy, 45)
        self.assertTrue(r.contains(60, 45))
        self.assertFalse(r.contains(0, 0))

    def test_rect_clip(self):
        r = Rect(50, 50, 100, 100).clip_to(120, 120)
        self.assertEqual(r.right, 120)
        self.assertEqual(r.bottom, 120)

    def test_rect_scaled(self):
        r = Rect(10, 10, 100, 100).scaled(0.5)
        self.assertEqual((r.x, r.y, r.w, r.h), (5, 5, 50, 50))

    def test_frame_center(self):
        f = empty_frame(640, 480)
        self.assertEqual(f.center(), (320, 240))
        self.assertEqual(f.width, 640)
        self.assertEqual(f.height, 480)

    def test_stats_record(self):
        s = Stats()
        s.record_collected("honey", 3)
        s.record_collected("honey", 1)
        self.assertEqual(s.collected["honey"], 4)


if __name__ == "__main__":
    unittest.main()
