"""UI smoke test: drives the real window against a fake input backend.

    QT_QPA_PLATFORM=offscreen python tools/uitest.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp(prefix="vclicker-ui-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vclicker.core import backend as backend_mod  # noqa: E402
from vclicker.core.backend import NullBackend  # noqa: E402
from vclicker.core.backend_base import (Capabilities, ClickAction, InputEvent,  # noqa: E402
                                        WindowInfo)
from vclicker.core.monitor import BaseMonitor  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


class FakeMonitor(BaseMonitor):
    def start(self) -> bool:
        self._running = True
        return True

    def feed(self, kind, key=None, button=None, x=0, y=0, delta=0):
        self._emit_raw(InputEvent(kind=kind, key=key, button=button, x=x, y=y, delta=delta))


class FakeBackend(NullBackend):
    os_name = "windows"

    def __init__(self) -> None:
        super().__init__("fake")
        self.capabilities = Capabilities(
            clicking=True, key_send=True, targeted_hold=True, window_list=True,
            recording=True, recording_quality="fake hooks", hotkeys=True, scroll=True)
        self.caps = self.capabilities
        self.clicks = 0
        self.actions: list[tuple] = []
        self.monitor = FakeMonitor()

    def build_click(self, button="left", double=False, x=None, y=None, burst=1) -> ClickAction:
        pairs = (2 if double else 1) * max(1, burst)

        def fire() -> None:
            self.clicks += pairs

        return ClickAction(fire, pairs)

    def mouse_down(self, button="left"):
        self.actions.append(("down", button))

    def mouse_up(self, button="left"):
        self.actions.append(("up", button))

    def move_to(self, x, y):
        self.actions.append(("move", x, y))

    def scroll(self, delta, x=None, y=None):
        self.actions.append(("wheel", delta))

    def key_down(self, key):
        self.actions.append(("kdown", key))

    def key_up(self, key):
        self.actions.append(("kup", key))

    def hold_keys(self, keys, windows=None):
        self.actions.append(("hold", tuple(keys), len(windows or [])))

    def release_keys(self, keys, windows=None):
        self.actions.append(("release", tuple(keys), len(windows or [])))

    def list_windows(self):
        return [WindowInfo(11, "Game window", "game.exe", 4242),
                WindowInfo(12, "Second window", "client.exe", 4343)]

    def create_monitor(self):
        return self.monitor


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def pump(app, seconds: float = 0.05) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    fake = FakeBackend()
    backend_mod._CACHE = fake

    from vclicker.app import create_app
    from vclicker.ui.pages.clicker_page import ClickerPage
    from vclicker.ui.pages.hotkeys_page import HotkeysPage
    from vclicker.ui.pages.keyholder_page import KeyHolderPage
    from vclicker.ui.pages.macros_page import MacrosPage

    app, window, ctx = create_app([])
    window.show()
    pump(app, 0.2)

    check("window built with five pages", window.stack.count() == 5, str(window.stack.count()))
    check("fake backend in use", ctx.backend is fake, ctx.backend.name)

    # ---------------- clicker ----------------
    window.set_page(0)
    pump(app)
    page = window.stack.currentWidget()
    assert isinstance(page, ClickerPage)
    page._toggle()
    pump(app, 0.6)
    running = ctx.clicker.running
    clicks = fake.clicks
    total_label = page.tile_total.value.text()
    page._toggle()
    pump(app, 0.2)
    check("clicker runs from the UI", running and clicks > 0, f"{clicks} clicks")
    check("clicker stats reach the tiles", total_label not in ("0", ""), total_label)
    check("clicker stops from the UI", not ctx.clicker.running)
    check("stop button state follows engine",
          page.start_button.property("variant") == "hero", str(page.start_button.property("variant")))

    # ---------------- key holder ----------------
    window.set_page(1)
    pump(app)
    holder_page = window.stack.currentWidget()
    assert isinstance(holder_page, KeyHolderPage)
    holder_page.target_seg.set_value("windows", emit=True)
    holder_page.picker.refresh()
    pump(app)
    check("window list populated", len(holder_page.picker._windows) == 2,
          str(len(holder_page.picker._windows)))
    holder_page.picker.select_all()
    pump(app)
    fake.actions.clear()
    holder_page._toggle()
    pump(app, 0.1)
    held = any(a[0] == "hold" and a[2] == 2 for a in fake.actions)
    check("key holder targets selected windows", ctx.keyholder.active and held, str(fake.actions[:3]))
    ctx.panic()
    pump(app)
    check("panic releases keys", not ctx.keyholder.active)

    # ---------------- recorder ----------------
    window.set_page(2)
    pump(app)
    macros_page = window.stack.currentWidget()
    assert isinstance(macros_page, MacrosPage)
    before = len(ctx.store.list())
    macros_page._toggle_record()
    pump(app, 0.1)
    check("recorder starts from the UI", ctx.recorder.recording)
    fake.monitor.feed("move", x=100, y=120)
    fake.monitor.feed("mouse_down", button="left", x=100, y=120)
    pump(app, 0.05)
    fake.monitor.feed("mouse_up", button="left", x=100, y=120)
    fake.monitor.feed("key_down", key="1")
    pump(app, 0.05)
    fake.monitor.feed("key_up", key="1")
    pump(app, 0.1)
    macros_page._toggle_record()
    pump(app, 0.3)
    after = ctx.store.list()
    check("recording saved a macro", len(after) == before + 1, f"{before} -> {len(after)}")
    check("library list refreshed", macros_page.list.count() == len(after),
          str(macros_page.list.count()))

    # ---------------- playback ----------------
    fake.actions.clear()
    macros_page._play_selected()
    pump(app, 0.5)
    check("playback reaches the backend", any(a[0] == "down" for a in fake.actions),
          str(fake.actions[:5]))

    # ---------------- hotkey capture ----------------
    window.set_page(3)
    pump(app)
    hotkeys_page = window.stack.currentWidget()
    assert isinstance(hotkeys_page, HotkeysPage)
    row = hotkeys_page.rows["toggle_clicker"]
    row.capture._begin()
    pump(app)
    fake.monitor.feed("key_down", key="ctrl")
    fake.monitor.feed("key_down", key="k")
    pump(app, 0.1)
    check("hotkey capture rebinds", ctx.hotkeys.bindings["toggle_clicker"] == "ctrl+k",
          ctx.hotkeys.bindings["toggle_clicker"])
    check("binding persisted to config",
          ctx.config.get("hotkeys.toggle_clicker") == "ctrl+k",
          str(ctx.config.get("hotkeys.toggle_clicker")))
    fake.monitor.feed("key_up", key="k")
    fake.monitor.feed("key_up", key="ctrl")
    pump(app)

    # new binding actually fires
    fake.clicks = 0
    fake.monitor.feed("key_down", key="ctrl")
    fake.monitor.feed("key_down", key="k")
    pump(app, 0.3)
    check("rebound hotkey starts the clicker", ctx.clicker.running)
    fake.monitor.feed("key_up", key="k")
    fake.monitor.feed("key_up", key="ctrl")
    ctx.panic()
    pump(app, 0.2)

    # ---------------- theme ----------------
    pages_before = id(window.stack.widget(0))
    window.apply_accent("cyber" if False else "cyan")
    pump(app, 0.3)
    check("accent change rebuilds pages", id(window.stack.widget(0)) != pages_before)
    check("accent stored in config", ctx.config.get("ui.accent") == "cyan",
          str(ctx.config.get("ui.accent")))

    # ---------------- navigation ----------------
    for index in range(5):
        window.set_page(index)
        pump(app, 0.05)
    check("all pages can be shown", window.stack.currentIndex() == 4)
    check("last page persisted", ctx.config.get("ui.last_page") == 4,
          str(ctx.config.get("ui.last_page")))

    failures = [r for r in RESULTS if not r[1]]
    print()
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} UI checks passed")
    for name, _ok, detail in failures:
        print(f"  failed: {name} ({detail})")

    window.close()
    app.processEvents()
    code = 1 if failures else 0
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
