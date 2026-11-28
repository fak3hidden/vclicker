import os
import unittest

from bssmacro.input.base import FakeInput
from bssmacro.input.select import describe_auto, get_input


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

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            get_input("telepathy")

    def test_uinput_without_device(self):
        from bssmacro.input.linux_uinput import UinputInput, uinput_available

        if uinput_available():
            self.skipTest("/dev/uinput is available on this machine")
        with self.assertRaises(Exception):
            get_input("uinput")

    def test_ydotool_without_binary(self):
        if os.environ.get("PATH") and __import__("shutil").which("ydotool"):
            self.skipTest("ydotool is installed on this machine")
        with self.assertRaises(Exception):
            get_input("ydotool")

    def test_describe_auto(self):
        self.assertIsInstance(describe_auto(), str)
        self.assertTrue(describe_auto())
