"""Render every page to a PNG without a display (development helper).

    QT_QPA_PLATFORM=offscreen python tools/preview.py [outdir]
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vclicker.app import create_app  # noqa: E402
from vclicker.core import backend as backend_mod  # noqa: E402
from vclicker.core.backend import NullBackend  # noqa: E402
from vclicker.core.backend_base import Capabilities, WindowInfo  # noqa: E402
from vclicker.core.macros import Macro, MacroEvent  # noqa: E402


def fake_windows():
    return [
        WindowInfo(101, "World of Warcraft", "Wow.exe", 4321),
        WindowInfo(102, "BlueStacks App Player", "HD-Player.exe", 5512),
        WindowInfo(103, "RuneScape - Chrome", "chrome.exe", 7788),
        WindowInfo(104, "Discord", "Discord.exe", 3344),
        WindowInfo(105, "ELDEN RING", "eldenring.exe", 9911),
    ]


class PreviewBackend(NullBackend):
    """A healthy X11 backend so screenshots look like a normal desktop install."""

    def __init__(self) -> None:
        super().__init__("preview")
        self.name = "Linux · X11 / XTest"
        self.os_name = "linux"
        self.caps = Capabilities(
            clicking=True, key_send=True, targeted_hold=True, window_list=True,
            recording=True, recording_quality="X11 polling (2 ms resolution)",
            hotkeys=True, scroll=True,
            notes=["Multi-window key-hold focuses each selected window in turn."])

    def describe(self) -> str:
        return "Linux · X11 XTest + 2 ms polling"


def sample_events(duration: float, seed: int) -> list[MacroEvent]:
    random.seed(seed)
    events: list[MacroEvent] = []
    t = 0.0
    while t < duration:
        events.append(MacroEvent(t=t, kind="move",
                                 x=random.randint(200, 900), y=random.randint(200, 700)))
        t += random.uniform(0.02, 0.09)
        if random.random() < 0.55:
            events.append(MacroEvent(t=t, kind="down", button="left",
                                     x=random.randint(200, 900), y=random.randint(200, 700)))
            events.append(MacroEvent(t=t + 0.04, kind="up", button="left"))
        if random.random() < 0.3:
            events.append(MacroEvent(t=t, kind="key_down", key=random.choice(["1", "2", "3", "q"])))
            events.append(MacroEvent(t=t + 0.06, kind="key_up", key="1"))
        t += random.uniform(0.05, 0.3)
    return events


def main() -> int:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/vclicker-shots"
    os.makedirs(outdir, exist_ok=True)
    os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp(prefix="vclicker-cfg-"))

    use_fake_backend = os.environ.get("VCLICKER_PREVIEW_BACKEND", "fake") != "real"
    if use_fake_backend:
        backend_mod._CACHE = PreviewBackend()

    app, window, ctx = create_app([])

    if not use_fake_backend:
        # Document what a missing input library looks like on Linux.
        window.resize(1240, 860)
        window.show()
        app.processEvents()
        for index in (0, 4):
            window.set_page(index)
            app.processEvents()
            app.processEvents()
        window.grab().save(os.path.join(outdir, "9-input-missing.png"))
        print("saved", os.path.join(outdir, "9-input-missing.png"))
        return 0
    ctx.backend.list_windows = fake_windows

    # seed a macro library
    from vclicker.core.macros import MacroStore
    store = MacroStore()
    for name, seconds, seed in (("Boss rotation", 4.2, 3), ("Fish farm loop", 7.8, 7),
                                ("Daily claim", 2.1, 11)):
        if not any(m.name == name for m in store.list()):
            store.save(Macro(name=name, events=sample_events(seconds, seed), duration=seconds))
    ctx.macro_recorded.emit(None)
    ctx.library_changed.emit()

    window.resize(1240, 860)
    window.show()
    app.processEvents()

    # make the clicker page look alive
    from vclicker.ui.pages.clicker_page import ClickerPage
    from vclicker.ui.pages.macros_page import MacrosPage
    from vclicker.ui.pages.keyholder_page import KeyHolderPage

    clicker = next(p for p in window.pages if isinstance(p, ClickerPage))
    random.seed(5)
    for _ in range(72):
        clicker.graph.push(random.uniform(16, 44))
    clicker.tile_speed.set_value("1,284")
    clicker.tile_total.set_value("37,912")
    clicker.tile_peak.set_value("2,140")
    clicker.runtime_hint.setText("Zero delay — maximum throughput")

    keyholder = next(p for p in window.pages if isinstance(p, KeyHolderPage))
    keyholder.picker._windows = fake_windows()
    keyholder.picker.set_selection(fake_windows())
    keyholder.picker._update_count()

    macros = next(p for p in window.pages if isinstance(p, MacrosPage))
    macros.reload()
    macros.list.setCurrentRow(0)
    macros._on_selection(macros.list.currentItem(), None)

    # shot 1 shows the live state; the real "running" flag needs a live thread,
    # so fake the property for the screenshot only.
    from vclicker.core.clicker import AutoClicker
    AutoClicker.running = property(lambda self: True)
    clicker._on_state(True)
    random.seed(5)
    for _ in range(72):
        clicker.graph.push(random.uniform(16, 44))
    clicker.tile_speed.set_value("1,284")
    clicker.tile_total.set_value("37,912")
    clicker.tile_peak.set_value("2,140")
    clicker.runtime_hint.setText("Zero delay — maximum throughput")
    window._refresh_global_state()
    app.processEvents()

    from vclicker.ui.main_window import NAV

    for index, (_key, text, _icon, _cls) in enumerate(NAV):
        if index == 1:
            AutoClicker.running = property(lambda self: self._thread is not None)
            clicker._on_state(False)
            window._refresh_global_state()
        window.set_page(index)
        app.processEvents()
        page = window.stack.currentWidget()
        if hasattr(page, "scroll"):
            page.scroll.verticalScrollBar().setValue(0)
            print("  scroll", page.scroll.verticalScrollBar().value(),
                  "max", page.scroll.verticalScrollBar().maximum(),
                  "viewport", page.scroll.viewport().height(),
                  "content", page.container.sizeHint().height())
        app.processEvents()
        pixmap = window.grab()
        path = os.path.join(outdir, f"{index + 1}-{text.lower().replace(' ', '-')}.png")
        pixmap.save(path)
        print("saved", path)
        if index == 0:
            window.resize(1240, 1180)
            app.processEvents()
            window.grab().save(os.path.join(outdir, "0-hero.png"))
            print("saved", os.path.join(outdir, "0-hero.png"))
            window.resize(1240, 860)
            app.processEvents()

    # detail: key holder with keys held
    window.set_page(1)
    keyholder.target_seg.set_value("windows", emit=True)
    keyholder.picker._windows = fake_windows()      # switching target re-scans
    keyholder.picker.set_selection(fake_windows())
    keyholder.cfg.windows = list(fake_windows())
    ctx.keyholder._active = True
    ctx.keyholder._keys = ["space"]
    ctx.keyholder._windows = list(fake_windows())
    keyholder._held_since = time.monotonic() - 12.0
    keyholder._on_state(True)
    window._refresh_global_state()
    app.processEvents()
    app.processEvents()
    window.grab().save(os.path.join(outdir, "6-keyholder-holding.png"))
    print("saved", os.path.join(outdir, "6-keyholder-holding.png"))
    ctx.keyholder._active = False
    keyholder._on_state(False)
    window._refresh_global_state()
    window.set_page(0)
    app.processEvents()

    # diagnostics dialog
    from vclicker.ui.pages.settings_page import DiagnosticsDialog
    dialog = DiagnosticsDialog(ctx, window)
    dialog.resize(560, 520)
    dialog.show()
    app.processEvents()
    app.processEvents()
    dialog.grab().save(os.path.join(outdir, "7-diagnostics.png"))
    dialog.close()
    print("saved", os.path.join(outdir, "7-diagnostics.png"))

    # alternate accent
    window.resize(1240, 860)
    window.set_page(0)
    window.apply_accent("cyan")
    app.processEvents()
    app.processEvents()
    window.grab().save(os.path.join(outdir, "8-accent-cyan.png"))
    window.apply_accent("indigo")
    app.processEvents()
    print("saved", os.path.join(outdir, "8-accent-cyan.png"))

    # minimum window size sanity check
    window.resize(1040, 700)
    app.processEvents()
    for index in range(5):
        window.set_page(index)
        app.processEvents()
        app.processEvents()
        window.grab().save(os.path.join(outdir, f"small-{index + 1}.png"))
    print("saved compact layout shots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
