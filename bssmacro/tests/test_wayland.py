import os
import stat
import tempfile
import unittest

import cv2
import numpy as np

from bssmacro.capture.wayland import (
    ShotCapture,
    WaylandWindow,
    WaylandWindowFinder,
    parse_hypr_clients,
    parse_sway_tree,
)


class _FakeFinder(WaylandWindowFinder):
    def __init__(self, rect) -> None:
        self.rect = rect

    def find(self, title_contains=None, process_contains=None):
        x, y, w, h = self.rect
        return WaylandWindow("Sober — Roblox", "sober", 4242, x, y, w, h)


class TestSwayTree(unittest.TestCase):
    TREE = {
        "type": "root", "name": "root", "rect": {"x": 0, "y": 0, "width": 3840, "height": 1080},
        "nodes": [
            {"type": "output", "name": "HDMI-A-1", "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
             "nodes": [
                 {"type": "workspace", "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                  "nodes": [
                      {"type": "con", "title": "terminal", "pid": 100,
                       "rect": {"x": 0, "y": 0, "width": 800, "height": 1080},
                       "window_rect": {"x": 0, "y": 0, "width": 800, "height": 1080}},
                      {"type": "con", "title": "Sober — Roblox", "pid": 4242, "app_id": "sober",
                       "rect": {"x": 800, "y": 0, "width": 1120, "height": 1080},
                       "window_rect": {"x": 4, "y": 6, "width": 1100, "height": 1060}},
                  ],
                  "floating_nodes": []},
             ],
             "floating_nodes": []},
            {"type": "output", "name": "eDP-1", "rect": {"x": 1920, "y": 0, "width": 1920, "height": 1080},
             "nodes": [], "floating_nodes": []},
        ],
        "floating_nodes": [],
    }

    def test_finds_sober_window(self):
        wins = parse_sway_tree(self.TREE, ["Sober", "Roblox"], ["sober"])
        self.assertEqual(len(wins), 1)
        win = wins[0]
        self.assertEqual(win.pid, 4242)
        # rect + window_rect offsets, in global coordinates
        self.assertEqual((win.x, win.y), (804, 6))
        self.assertEqual((win.w, win.h), (1100, 1060))

    def test_no_match_when_absent(self):
        wins = parse_sway_tree(self.TREE, ["Firefox"], ["firefox"])
        self.assertEqual(wins, [])


class TestHyprClients(unittest.TestCase):
    CLIENTS = [
        {"class": "foot", "title": "terminal", "pid": 100,
         "at": [0, 0], "size": [500, 600]},
        {"class": "sober", "initialClass": "org.sober.Roblox",
         "title": "Roblox", "pid": 4242, "at": [500, 40], "size": [1400, 1040]},
        {"class": "kitty", "title": "hidden", "pid": 200,
         "at": [0, 0], "size": [0, 0]},   # invalid size -> skipped
    ]

    def test_finds_sober_window(self):
        wins = parse_hypr_clients(self.CLIENTS, ["Sober", "Roblox"], ["sober", "roblox"])
        self.assertEqual(len(wins), 1)
        win = wins[0]
        self.assertEqual(win.pid, 4242)
        self.assertEqual((win.x, win.y, win.w, win.h), (500, 40, 1400, 1040))


class TestShotCapture(unittest.TestCase):
    """Drives ShotCapture against fake screenshot tools on PATH."""

    W, H = 640, 480

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Fixture screenshot: a bright red 640x480 image.
        img = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        img[:, :] = (0, 0, 255)
        self.fixture = os.path.join(self.tmp, "fixture.png")
        cv2.imwrite(self.fixture, img)

        self.bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin_dir)
        self.old_path = os.environ.get("PATH")
        os.environ["PATH"] = self.bin_dir + os.pathsep + (self.old_path or "")

    def tearDown(self):
        if self.old_path is not None:
            os.environ["PATH"] = self.old_path

    def _install(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _ok_body(self):
        return (f'for a in "$@"; do case "$a" in *.png) '
                f'cp "{self.fixture}" "$a";; esac; done\nexit 0\n')

    def test_grab_with_fake_tool(self):
        self._install("grim", self._ok_body())
        cap = ShotCapture(shot_tool="grim")
        frame = cap.grab()
        self.assertEqual((frame.width, frame.height), (self.W, self.H))
        self.assertEqual(frame.source, "grim")
        self.assertEqual(frame.region.as_tuple(), (0, 0, self.W, self.H))

    def test_falls_through_on_tool_failure(self):
        self._install("grim", "exit 1\n")
        self._install("spectacle", self._ok_body())
        cap = ShotCapture()
        frame = cap.grab()
        self.assertEqual(frame.source, "spectacle")

    def test_fixed_region_crop(self):
        self._install("scrot", self._ok_body())
        cap = ShotCapture(shot_tool="scrot", fixed_region=(10, 20, 100, 50))
        frame = cap.grab()
        self.assertEqual((frame.width, frame.height), (100, 50))
        self.assertEqual(frame.region.as_tuple(), (10, 20, 100, 50))

    def test_window_rect_from_finder(self):
        self._install("maim", self._ok_body())
        cap = ShotCapture(shot_tool="maim", finder=_FakeFinder((20, 30, 200, 100)))
        frame = cap.grab()
        self.assertEqual((frame.width, frame.height), (200, 100))
        self.assertEqual(frame.region.as_tuple(), (20, 30, 200, 100))

    def test_no_tools_available_raises(self):
        # PATH is stripped of every known screenshot tool.
        os.environ["PATH"] = self.bin_dir + os.pathsep + "/nonexistent-bin"
        cap = ShotCapture()
        with self.assertRaises(RuntimeError):
            cap.grab()

    def test_stdout_tool(self):
        self._install("wayshot", f'cat "{self.fixture}"\nexit 0\n')
        cap = ShotCapture(shot_tool="wayshot")
        frame = cap.grab()
        self.assertEqual(frame.source, "wayshot")
        self.assertEqual((frame.width, frame.height), (self.W, self.H))


class TestFinderAvailability(unittest.TestCase):
    def test_available_is_bool(self):
        self.assertIsInstance(WaylandWindowFinder().available(), bool)

    def test_no_compositor_no_windows(self):
        # In the sandbox neither swaymsg nor hyprctl exist; find() must be a
        # clean None, not a crash.
        wins = WaylandWindowFinder().list_windows(["Sober"], ["sober"])
        self.assertIsInstance(wins, list)
        self.assertEqual(wins, [])


if __name__ == "__main__":
    unittest.main()
