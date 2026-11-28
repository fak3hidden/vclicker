import unittest

from bssmacro.catalog import PriorityRule, default_priorities
from bssmacro.types import Detection, Rect
from bssmacro.vision.collector import Collector, CollectorConfig


def det(label, cx, cy, score=0.9):
    return Detection(label=label, score=score,
                    rect=Rect(cx - 5, cy - 5, 10, 10))


class TestCollector(unittest.TestCase):
    def test_priority_ordering(self):
        cfg = CollectorConfig(priorities=default_priorities())
        c = Collector(cfg)
        dets = [det("honey", 100, 100), det("stinger", 300, 300)]
        ranked = c.rank(dets, (200, 200))
        self.assertEqual(ranked[0].detection.label, "stinger")

    def test_nearer_wins_within_same_priority(self):
        cfg = CollectorConfig(priorities=default_priorities())
        c = Collector(cfg)
        dets = [det("honey", 50, 200), det("honey", 190, 200)]
        ranked = c.rank(dets, (200, 200))
        # the one at x=190 is closer to anchor x=200
        self.assertEqual(ranked[0].detection.rect.cx, 190)

    def test_avoid(self):
        cfg = CollectorConfig(priorities=default_priorities(), avoid=["spider"])
        c = Collector(cfg)
        dets = [det("spider", 100, 100), det("honey", 300, 300)]
        ranked = c.rank(dets, (200, 200))
        self.assertFalse(any(t.detection.label == "spider" for t in ranked))
        self.assertTrue(any(t.detection.label == "honey" for t in ranked))

    def test_disabled_rule_skipped(self):
        prios = default_priorities(disabled=["stinger"])
        cfg = CollectorConfig(priorities=prios)
        c = Collector(cfg)
        dets = [det("stinger", 100, 100), det("honey", 300, 300)]
        ranked = c.rank(dets, (200, 200))
        self.assertEqual(ranked[0].detection.label, "honey")

    def test_min_score_global_floor(self):
        cfg = CollectorConfig(priorities=default_priorities(), min_score=0.95)
        c = Collector(cfg)
        dets = [det("honey", 300, 300, score=0.5)]
        self.assertEqual(c.rank(dets, (200, 200)), [])

    def test_best_of_label(self):
        cfg = CollectorConfig(priorities=default_priorities())
        c = Collector(cfg)
        dets = [det("spider", 90, 90), det("spider", 110, 110)]
        t = c.best_of_label(dets, "spider", (200, 200))
        self.assertIsNotNone(t)
        self.assertEqual(t.detection.rect.cx, 110)

    def test_summary(self):
        cfg = CollectorConfig(priorities=default_priorities())
        c = Collector(cfg)
        summary = c.summary([det("honey", 1, 1), det("honey", 2, 2),
                            det("treat", 3, 3)])
        self.assertEqual(summary, {"honey": 2, "treat": 1})


if __name__ == "__main__":
    unittest.main()
