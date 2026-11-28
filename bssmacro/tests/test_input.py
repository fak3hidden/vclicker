import unittest

from bssmacro.input.base import FakeInput
from bssmacro.input.select import get_input


class TestFakeInput(unittest.TestCase):
    def test_records_actions(self):
        f = FakeInput()
        f.move(10, 20)
        f.click("left", 5, 5, 2)
        f.key_down("w")
        self.assertEqual(f.count("move"), 1)
        self.assertEqual(f.count("click"), 2)
        self.assertTrue(f.is_key_down("w"))
        f.key_up("w")
        self.assertFalse(f.is_key_down("w"))

    def test_tap(self):
        f = FakeInput()
        f.tap("space")
        self.assertIn(("key_down", {"key": "space"}), f.actions)
        self.assertIn(("key_up", {"key": "space"}), f.actions)


class TestInputSelect(unittest.TestCase):
    def test_fake(self):
        ctrl = get_input("fake")
        self.assertIsInstance(ctrl, FakeInput)

    def test_auto_returns_something(self):
        # On a headless box this falls back to FakeInput; either way it works.
        ctrl = get_input("auto")
        self.assertTrue(hasattr(ctrl, "click"))


if __name__ == "__main__":
    unittest.main()
