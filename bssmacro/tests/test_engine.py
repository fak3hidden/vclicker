import os
import tempfile
import unittest

from bssmacro.config import MacroConfig
from bssmacro.engine import Engine
from bssmacro.input.base import FakeInput
from bssmacro.types import Rect
from .helpers import frame_with, honey_bgr


def build_engine(tmp_templates: str, **cfg_overrides) -> Engine:
    cfg = MacroConfig.default()
    cfg.templates_dir = tmp_templates
    cfg.field_cfg.random_walk = False
    cfg.gather_cps = 0
    for k, v in cfg_overrides.items():
        setattr(cfg, k, v)
    return Engine(cfg, FakeInput(), capture=None)


class _SizeAwareFake(FakeInput):
    def __init__(self):
        super().__init__()
        self.sizes = []

    def set_screen_size(self, w, h):
        self.sizes.append((w, h))


class TestEngineWaylandHooks(unittest.TestCase):
    def test_screen_size_passed_to_input(self):
        tmp = tempfile.mkdtemp()
        cfg = MacroConfig.default()
        cfg.templates_dir = tmp
        cfg.field_cfg.random_walk = False
        cfg.gather_cps = 0
        input_ctrl = _SizeAwareFake()
        eng = Engine(cfg, input_ctrl, capture=None)
        eng.loop_once(frame_with(400, 300, []))
        self.assertIn((400, 300), input_ctrl.sizes)


class TestEngineField(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_empty_frame_is_idle_and_still(self):
        eng = build_engine(self.tmp)
        out = eng.loop_once(frame_with(400, 300, []))
        self.assertEqual(out["state"], "idle")
        keys = [a[1]["key"] for a in eng.input.actions if a[0] == "key_down"]
        self.assertEqual([k for k in keys if k in ("w", "a", "s", "d")], [])

    def test_moves_toward_token_top_left(self):
        eng = build_engine(self.tmp)
        eng.loop_once(frame_with(400, 300, [(60, 60, 16, honey_bgr())]))
        keys = [a[1]["key"] for a in eng.input.actions if a[0] == "key_down"]
        # top-left of centre => forward (w) + left (a)
        self.assertIn("w", keys)
        self.assertIn("a", keys)

    def test_collects_token_at_center(self):
        eng = build_engine(self.tmp)
        eng.loop_once(frame_with(400, 300, [(200, 150, 16, honey_bgr())]))
        self.assertEqual(eng.stats.collected.get("honey"), 1)

    def test_status_callback_fires(self):
        seen = {}
        cfg = MacroConfig.default()
        cfg.templates_dir = self.tmp
        cfg.field_cfg.random_walk = False
        cfg.status_interval_sec = 0.0
        eng = Engine(cfg, FakeInput(), capture=None, status_cb=lambda s: seen.update(s))
        eng.loop_once(frame_with(400, 300, []))
        self.assertIn("state", seen)

    def test_returns_and_converts_when_honey_full(self):
        cfg = MacroConfig.default()
        cfg.templates_dir = self.tmp
        cfg.field_cfg.random_walk = False
        cfg.gather_cps = 0
        cfg.hud.honey_region = (0.0, 0.0, 1.0, 1.0)   # whole frame
        cfg.hud.honey_hsv = (30, 200, 200)
        cfg.hud.honey_tol = (40, 60, 60)
        cfg.hud.convert_threshold = 0.5
        cfg.convert.hive_region = (0.4, 0.4, 0.6, 0.6)  # centred -> arrives at once
        eng = Engine(cfg, FakeInput(), capture=None)
        # Fill the whole frame with honey-gold so the bar reads full.
        frame = frame_with(400, 300, [])
        frame.bgr[:] = honey_bgr()
        eng.loop_once(frame)
        self.assertGreaterEqual(eng.stats.conversions, 1)

    def test_windy_objective_does_not_crash(self):
        eng = build_engine(self.tmp, objective="windy")
        out = eng.loop_once(frame_with(400, 300, [(200, 150, 16, honey_bgr())]))
        self.assertIn("state", out)


if __name__ == "__main__":
    unittest.main()
