import unittest

from bssmacro.input.ydotool import (
    YdotoolInput,
    YdotoolUnavailable,
)


class TestYdotool(unittest.TestCase):
    def _make(self, rc=0):
        calls = []

        def runner(argv):
            calls.append(argv)
            return rc

        return YdotoolInput(runner=runner), calls

    def test_move_absolute(self):
        yt, calls = self._make()
        yt.move(640, 480)
        self.assertEqual(
            calls[0], ["mousemove", "--absolute", "-x", "640", "-y", "480"])

    def test_move_relative(self):
        yt, calls = self._make()
        yt.move_rel(-100, 100)
        self.assertEqual(calls[0], ["mousemove", "-x", "-100", "-y", "100"])

    def test_click_left(self):
        yt, calls = self._make()
        yt.click("left", 100, 200, 3)
        self.assertEqual(calls[0][:3], ["mousemove", "--absolute", "-x"])
        self.assertEqual(calls[1][4], "10")          # next-delay ms
        self.assertEqual(calls[1][5], "0xc0")

    def test_click_right(self):
        yt, calls = self._make()
        yt.click("right")
        self.assertEqual(calls[0][5], "0xc1")

    def test_key_down_up_uses_ev_codes(self):
        yt, calls = self._make()
        yt.key_down("w")
        self.assertEqual(calls[0], ["key", "17:1"])
        yt.key_up("w")
        self.assertEqual(calls[1], ["key", "17:0"])

    def test_tap_single_call(self):
        yt, calls = self._make()
        yt.tap("space")
        self.assertEqual(calls[0], ["key", "57:1", "57:0"])

    def test_failure_raises(self):
        yt, _ = self._make(rc=3)
        with self.assertRaises(RuntimeError):
            yt.key_down("w")

    def test_unknown_key_noop(self):
        yt, calls = self._make()
        yt.key_down("not-a-key")
        self.assertEqual(calls, [])

    def test_missing_binary_raises(self):
        with self.assertRaises(YdotoolUnavailable):
            YdotoolInput(binary="definitely-not-installed-ydotool")

    def test_is_key_down_tracking(self):
        yt, _ = self._make()
        yt.key_down("a")
        self.assertTrue(yt.is_key_down("a"))
        yt.key_up("a")
        self.assertFalse(yt.is_key_down("a"))


if __name__ == "__main__":
    unittest.main()
