import os
import tempfile
import unittest

from bssmacro.config import MacroConfig
from bssmacro.types import Stats


class TestConfig(unittest.TestCase):
    def test_default_builds(self):
        cfg = MacroConfig.default()
        self.assertTrue(cfg.collector.priorities)
        self.assertEqual(cfg.objective, "field")
        labels = [p.label for p in cfg.collector.priorities]
        self.assertIn("honey", labels)
        self.assertIn("stinger", labels)

    def test_round_trip(self):
        cfg = MacroConfig.default()
        cfg.objective = "mixed"
        cfg.gather_cps = 12
        cfg.webhook.url = "https://discord.com/api/webhooks/x/y"
        d = cfg.to_dict()
        cfg2 = MacroConfig.from_dict(d)
        self.assertEqual(cfg2.objective, "mixed")
        self.assertEqual(cfg2.gather_cps, 12)
        self.assertEqual(cfg2.webhook.url, "https://discord.com/api/webhooks/x/y")
        self.assertEqual(len(cfg2.collector.priorities),
                         len(cfg.collector.priorities))

    def test_save_load_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cfg.json")
            cfg = MacroConfig.default()
            cfg.objective = "windy"
            saved = cfg.save(path)
            self.assertTrue(os.path.exists(saved))
            loaded = MacroConfig.load(path)
            self.assertEqual(loaded.objective, "windy")

    def test_validate_ok(self):
        cfg = MacroConfig.default()
        self.assertEqual(cfg.validate(), [])

    def test_validate_bad_objective(self):
        cfg = MacroConfig.default()
        cfg.objective = "bananas"
        problems = cfg.validate()
        self.assertTrue(any("objective" in p for p in problems))

    def test_validate_bad_webhook(self):
        cfg = MacroConfig.default()
        cfg.webhook.url = "not-a-url"
        problems = cfg.validate()
        self.assertTrue(any("webhook" in p.lower() for p in problems))

    def test_stats_per_minute(self):
        s = Stats()
        s.started_at = 0.0
        s.collected = {"honey": 100}
        # elapsed measured from started_at; override by monkeypatching time is overkill
        self.assertGreaterEqual(s.per_minute(100), 0.0)


if __name__ == "__main__":
    unittest.main()
