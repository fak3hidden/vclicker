import unittest

from bssmacro.input.linux_uinput import (
    ABS_MAX_COORD,
    ABS_X,
    ABS_Y,
    EV_ABS,
    EV_KEY,
    EV_REL,
    REL_WHEEL,
    UINPUT_KEY_CODES,
    UinputInput,
    uinput_available,
)


class RecordingInput(UinputInput):
    """A UinputInput that never touches a real device."""

    def __init__(self) -> None:
        super().__init__(device=None, screen_size=(800, 600))


class TestKeyCodes(unittest.TestCase):
    def test_macro_keys_present(self):
        for key in ("w", "a", "s", "d", "1", "2", "space", "esc", "f1"):
            self.assertIn(key, UINPUT_KEY_CODES, key)

    def test_known_values(self):
        self.assertEqual(UINPUT_KEY_CODES["w"], 17)
        self.assertEqual(UINPUT_KEY_CODES["1"], 2)
        self.assertEqual(UINPUT_KEY_CODES["space"], 57)
        self.assertEqual(UINPUT_KEY_CODES["left"], 105)


class TestEventEmission(unittest.TestCase):
    def setUp(self):
        self.ui = RecordingInput()

    def _types(self):
        return [(t, c, v) for (t, c, v) in self.ui._events]

    def test_move_emits_abs_and_syn(self):
        self.ui.move(400, 300)
        ev = self._types()
        self.assertIn((EV_ABS, ABS_X, ABS_MAX_COORD // 2), ev)
        self.assertIn((EV_ABS, ABS_Y, ABS_MAX_COORD // 2), ev)
        self.assertTrue(any(t == 0 for t, _, _ in ev))   # EV_SYN present

    def test_scale_uses_screen_size(self):
        self.ui.set_screen_size(1600, 800)
        self.ui.move(800, 400)
        ev = self._types()
        self.assertIn((EV_ABS, ABS_X, ABS_MAX_COORD // 2), ev)
        self.assertIn((EV_ABS, ABS_Y, ABS_MAX_COORD // 2), ev)

    def test_click_emits_button_press_release(self):
        self.ui.click("left", 100, 50)
        ev = self._types()
        self.assertIn((EV_KEY, 0x110, 1), ev)            # BTN_LEFT down
        self.assertIn((EV_KEY, 0x110, 0), ev)            # BTN_LEFT up
        self.assertIn((EV_KEY, 0x14A, 1), ev)            # BTN_TOUCH down

    def test_key_down_up(self):
        self.ui.key_down("w")
        self.assertIn((EV_KEY, 17, 1), self._types())
        self.assertTrue(self.ui.is_key_down("w"))
        self.ui.key_up("w")
        self.assertIn((EV_KEY, 17, 0), self._types())
        self.assertFalse(self.ui.is_key_down("w"))

    def test_tap(self):
        self.ui.tap("space")
        ev = self._types()
        self.assertIn((EV_KEY, 57, 1), ev)
        self.assertIn((EV_KEY, 57, 0), ev)

    def test_unknown_key_ignored(self):
        self.ui.key_down("not-a-key")
        self.assertEqual(self.ui._events, [])

    def test_scroll_wheel(self):
        self.ui.scroll(2)
        ev = self._types()
        self.assertIn((EV_REL, REL_WHEEL, 1), ev)
        self.ui.scroll(-1)
        self.assertIn((EV_REL, REL_WHEEL, -1), self._types())

    def test_close_releases_keys(self):
        self.ui.key_down("w")
        self.ui.click("left")
        self.ui.close()
        self.assertIn((EV_KEY, 17, 0), self._types())
        self.assertIn((EV_KEY, 0x110, 0), self._types())


class TestAvailability(unittest.TestCase):
    def test_uinput_available_returns_bool(self):
        self.assertIsInstance(uinput_available(device="/nonexistent-uinput"), bool)

    def test_missing_device_is_false(self):
        self.assertFalse(uinput_available(device="/nonexistent-uinput"))


if __name__ == "__main__":
    unittest.main()
