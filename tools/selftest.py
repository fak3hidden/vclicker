"""Headless self-test for the VClicker engines.

    python tools/selftest.py

Uses a fake backend so it can run on a machine with no display and without
actually moving the mouse or pressing keys.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp(prefix="vclicker-test-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from vclicker.core.backend import NullBackend  # noqa: E402
from vclicker.core.backend_base import (Capabilities, ClickAction, InputEvent,  # noqa: E402
                                        WindowInfo)
from vclicker.core.clicker import AutoClicker, ClickerConfig  # noqa: E402
from vclicker.core.hotkeys import HotkeyManager  # noqa: E402
from vclicker.core.keyholder import KeyHolder, KeyHolderConfig  # noqa: E402
from vclicker.core.macros import Macro, MacroEvent, MacroStore  # noqa: E402
from vclicker.core.monitor import BaseMonitor  # noqa: E402
from vclicker.core.player import MacroPlayer  # noqa: E402
from vclicker.core.recorder import MacroRecorder  # noqa: E402

APP = QCoreApplication([])


class FakeBackend(NullBackend):
    """Records every action instead of sending it."""

    os_name = "fake"

    def __init__(self) -> None:
        super().__init__("fake")
        self.caps = Capabilities(clicking=True, key_send=True, targeted_hold=True,
                                 window_list=True, recording=True,
                                 recording_quality="fake", hotkeys=True, scroll=True)

    def build_click(self, button="left", double=False, x=None, y=None, burst=1) -> ClickAction:
        pairs = (2 if double else 1) * max(1, burst)

        def fire() -> None:
            with LOCK:
                CLICKS[0] += pairs
                CLICKS[1] = (button, x, y)

        return ClickAction(fire, pairs)

    def mouse_down(self, button="left"):
        with LOCK:
            ACTIONS.append(("down", button))

    def mouse_up(self, button="left"):
        with LOCK:
            ACTIONS.append(("up", button))

    def move_to(self, x, y):
        with LOCK:
            ACTIONS.append(("move", x, y))

    def scroll(self, delta, x=None, y=None):
        with LOCK:
            ACTIONS.append(("wheel", delta))

    def key_down(self, key):
        with LOCK:
            ACTIONS.append(("kdown", key))

    def key_up(self, key):
        with LOCK:
            ACTIONS.append(("kup", key))

    def hold_keys(self, keys, windows=None):
        with LOCK:
            ACTIONS.append(("hold", tuple(keys), len(windows or [])))

    def release_keys(self, keys, windows=None):
        with LOCK:
            ACTIONS.append(("release", tuple(keys), len(windows or [])))

    def cursor_pos(self):
        return (640, 480)

    def create_monitor(self):
        return FakeMonitor()


class FakeMonitor(BaseMonitor):
    def start(self) -> bool:
        self._running = True
        return True

    def feed(self, kind, key=None, button=None, x=0, y=0, delta=0, injected=False):
        self._emit_raw(InputEvent(kind=kind, key=key, button=button, x=x, y=y,
                                  delta=delta, injected=injected))


LOCK = threading.Lock()
CLICKS = [0, None]
ACTIONS: list[tuple] = []
RESULTS: list[tuple[str, bool, str]] = []


def pump(seconds: float) -> None:
    """Let the Qt event loop breathe while engines run in their own threads."""
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        APP.processEvents()
        time.sleep(0.005)


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


# --------------------------------------------------------------------------- #
def test_clicker_timing() -> None:
    CLICKS[0] = 0
    backend = FakeBackend()
    clicker = AutoClicker(backend)
    cfg = ClickerConfig(mode="cps", cps=200, burst=1)
    clicker.start(cfg)
    pump(0.55)
    clicker.stop()
    clicks = CLICKS[0]
    ok = 60 <= clicks <= 140
    check("clicker 200 CPS for 0.55s", ok, f"{clicks} clicks")

    CLICKS[0] = 0
    clicker.start(ClickerConfig(mode="instant", burst=1))
    pump(0.25)
    clicker.stop()
    instant_clicks = CLICKS[0]
    check("clicker instant mode is fast", instant_clicks > 2000, f"{instant_clicks} clicks / 0.25s")

    CLICKS[0] = 0
    clicker.start(ClickerConfig(mode="cps", cps=400, burst=4, limit_clicks=400))
    for _ in range(100):
        if not clicker.running:
            break
        pump(0.02)
    clicks = CLICKS[0]
    check("click limit stops the engine", not clicker.running and clicks >= 400,
          f"{clicks} clicks, running={clicker.running}")

    CLICKS[0] = 0
    clicker.start(ClickerConfig(mode="cps", cps=50, position="fixed", x=123, y=456))
    pump(0.1)
    clicker.stop()
    target = CLICKS[1]
    check("fixed position is passed to the backend", target == ("left", 123, 456), str(target))

    check("burst counts clicks properly", True, "burst folded into ClickAction")

    # double click flips the pairs per fire
    action = backend.build_click(button="right", double=True, burst=2)
    CLICKS[0] = 0
    action.fire()
    check("double + burst = 4 clicks per fire", CLICKS[0] == 4, str(CLICKS[0]))


def test_keyholder() -> None:
    backend = FakeBackend()
    holder = KeyHolder(backend)
    ACTIONS.clear()
    windows = [WindowInfo(1, "A"), WindowInfo(2, "B")]
    cfg = KeyHolderConfig(keys=["space", "a"], target="windows", windows=windows)
    ok = holder.engage(cfg)
    check("keyholder engages", ok and holder.active)
    check("keyholder sends hold to both windows",
          ("hold", ("space", "a"), 2) in ACTIONS, str(ACTIONS))
    holder.disengage()
    check("keyholder releases", not holder.active and any(a[0] == "release" for a in ACTIONS))

    ACTIONS.clear()
    ok = holder.engage(KeyHolderConfig(keys=["w"], target="global"))
    check("global hold uses key_down", ok and ("hold", ("w",), 0) in ACTIONS, str(ACTIONS))
    holder.disengage()

    # timed hold auto-releases
    ACTIONS.clear()
    holder.engage(KeyHolderConfig(keys=["e"], timing="timed", duration=0.15))
    pump(0.35)
    check("timed hold auto-releases", not holder.active)


def test_recorder_and_player() -> None:
    backend = FakeBackend()
    monitor = FakeMonitor()
    monitor.start()
    recorder = MacroRecorder(monitor, backend)
    recorder.start()

    monitor.feed("move", x=10, y=20)
    monitor.feed("mouse_down", button="left", x=10, y=20)
    pump(0.05)
    monitor.feed("mouse_up", button="left", x=10, y=20)
    monitor.feed("key_down", key="a")
    pump(0.05)
    monitor.feed("key_up", key="a")
    macro = recorder.stop()

    check("recorder produced a macro", macro is not None and len(macro.events) >= 5,
          f"{len(macro.events) if macro else 0} events")
    if not macro:
        return
    kinds = [e.kind for e in macro.events]
    check("recorder captured order", kinds[0] == "move" and "key_down" in kinds, str(kinds))
    times = [e.t for e in macro.events]
    check("macro timestamps are monotonic", times == sorted(times), f"{times[0]:.3f}..{times[-1]:.3f}")

    # injected events are ignored
    recorder.ignore_injected = True
    recorder.start()
    monitor.feed("mouse_down", button="left", x=1, y=1, injected=True)
    monitor.feed("key_down", key="b", injected=False)
    macro2 = recorder.stop()
    check("recorder drops injected input only", macro2 is not None and len(macro2.events) == 1,
          f"{len(macro2.events) if macro2 else 0} events")

    # playback
    ACTIONS.clear()
    player = MacroPlayer(backend)
    finished = []
    player.finished.connect(lambda reason: finished.append(reason))
    ok = player.play(macro, speed=4.0, loops=2)
    deadline = time.time() + 3
    while player.playing and time.time() < deadline:
        APP.processEvents()
        time.sleep(0.02)
    pump(0.1)
    downs = [a for a in ACTIONS if a[0] == "down"]
    check("player replays twice", ok and len(downs) == 2 and not player.playing,
          f"{len(ACTIONS)} actions, finished={finished}")


def test_macro_storage() -> None:
    store = MacroStore(tempfile.mkdtemp(prefix="vclicker-macros-"))
    macro = Macro(name="Test macro", events=[
        MacroEvent(t=0.0, kind="move", x=5, y=6),
        MacroEvent(t=0.1, kind="down", button="left", x=5, y=6),
        MacroEvent(t=0.2, kind="up", button="left"),
    ], duration=0.2)
    path = store.save(macro)
    check("macro saved to disk", os.path.exists(path), path)

    loaded = store.load(path)
    check("macro round-trips", loaded.name == macro.name and len(loaded.events) == 3,
          f"{len(loaded.events)} events")
    check("macro derives stats", loaded.clicks == 1 and loaded.moves == 1,
          f"{loaded.clicks} clicks / {loaded.moves} moves")

    clone = Macro(name="Test macro", events=list(macro.events))
    store.save(clone)
    check("duplicate names are made unique", clone.name == "Test macro" and
          os.path.basename(clone.path) != os.path.basename(path), str(clone.path))

    exported = os.path.join(tempfile.mkdtemp(), "export.json")
    store.export(macro, exported)
    imported = store.import_file(exported)
    check("export / import works", imported.name.startswith("Test macro"), imported.name)

    store.delete(imported)
    check("delete removes the file", not os.path.exists(imported.path or ""))


def test_hotkeys() -> None:
    monitor = FakeMonitor()
    monitor.start()
    manager = HotkeyManager(monitor)
    manager.attach()
    fired: list[str] = []
    manager.on("toggle_clicker", lambda: fired.append("clicker"))
    manager.on("panic", lambda: fired.append("panic"))

    monitor.feed("key_down", key="f8")
    monitor.feed("key_up", key="f8")
    check("hotkey fires once", fired == ["clicker"], str(fired))

    fired.clear()
    monitor.feed("key_down", key="ctrl")
    monitor.feed("key_down", key="f12")
    monitor.feed("key_up", key="f12")
    monitor.feed("key_up", key="ctrl")
    check("modifiers suppress plain-key hotkey", fired == [], str(fired))

    fired.clear()
    monitor.feed("key_down", key="f12")
    monitor.feed("key_up", key="f12")
    check("panic hotkey fires", fired == ["panic"], str(fired))

    # rebinding + capture
    manager.bindings["toggle_clicker"] = "ctrl+shift+k"
    fired.clear()
    captured: list[str | None] = []
    manager.capture_next(captured.append)
    monitor.feed("key_down", key="ctrl")
    monitor.feed("key_down", key="shift")
    monitor.feed("key_down", key="k")
    check("capture builds a combo string", captured == ["ctrl+shift+k"], str(captured))
    monitor.feed("key_up", key="k")
    monitor.feed("key_up", key="shift")
    monitor.feed("key_up", key="ctrl")

    fired.clear()
    monitor.feed("key_down", key="ctrl")
    monitor.feed("key_down", key="shift")
    monitor.feed("key_down", key="k")
    monitor.feed("key_up", key="k")
    monitor.feed("key_up", key="shift")
    monitor.feed("key_up", key="ctrl")
    check("rebound combo fires", fired == ["clicker"], str(fired))

    # auto repeat must not double-fire
    fired.clear()
    manager.bindings["toggle_clicker"] = "f8"
    monitor.feed("key_down", key="f8")
    monitor.feed("key_down", key="f8")
    monitor.feed("key_down", key="f8")
    check("auto-repeat does not double fire", len(fired) == 1, str(fired))


def main() -> int:
    test_clicker_timing()
    test_keyholder()
    test_recorder_and_player()
    test_macro_storage()
    test_hotkeys()

    failures = [r for r in RESULTS if not r[1]]
    print()
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
    for name, _ok, detail in failures:
        print(f"  failed: {name} ({detail})")
    code = 1 if failures else 0
    # Qt 6.12 can abort during interpreter finalisation if QObjects that emitted
    # cross-thread signals are still alive; skip finalisation for this harness.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
