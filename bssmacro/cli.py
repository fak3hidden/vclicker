"""Command-line interface for the BSS Linux macro.

Subcommands::

    bssmacro config            write a default config.json
    bssmacro run              start farming (Ctrl+C to stop)
    bssmacro calibrate        capture Sober + crop templates
    bssmacro webhook-test     send a test embed to your Discord webhook
    bssmacro selftest         run the headless unit tests
    bssmacro version          print version

Use ``--fake`` with ``run`` to drive the whole pipeline against the live Sober
window *without* injecting real input (great for verifying detection/templates).

X11 / XWayland vs native Wayland
--------------------------------

* **X11 / XWayland**: works out of the box (XTest input + mss capture).
* **Native Wayland (GNOME/KDE/sway/Hyprland)**: set ``input_kind = "uinput"``
  (needs /dev/uinput write access — see README) or ``"ydotool"`` (needs
  ydotoold), and ``capture.method = "cli"`` so frames come from the
  compositor's screenshot tool (grim / spectacle / gnome-screenshot).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

from . import __version__
from .config import DEFAULT_CONFIG_PATH, MacroConfig
from .input.select import describe_auto, get_input
from .webhook.discord import DiscordWebhook


def _make_capture(cfg: MacroConfig):
    from .capture.capture import CaptureConfig, ScreenCapture
    from .capture.wayland import ShotCapture

    cap_cfg = CaptureConfig(
        downscale=cfg.capture.downscale,
        capture_fps=cfg.capture.capture_fps,
        title_contains=cfg.window_title_contains,
        process_contains=cfg.window_process_contains,
        method=cfg.capture.method,
        shot_tool=cfg.capture.shot_tool,
    )
    method = (cap_cfg.method or "auto").lower()
    if method in ("cli", "wayland", "shot"):
        return ShotCapture(
            downscale=cap_cfg.downscale,
            title_contains=cap_cfg.title_contains,
            process_contains=cap_cfg.process_contains,
            shot_tool=cap_cfg.shot_tool or None)
    if method in ("mss", "x11"):
        return ScreenCapture(cap_cfg)
    # auto: mss whenever an X/XWayland display can find the game, else the
    # compositor screenshot path (native Wayland).
    cap = ScreenCapture(cap_cfg)
    try:
        if cap.locate_window() is not None:
            return cap
    except Exception:
        pass
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return ShotCapture(
            downscale=cap_cfg.downscale,
            title_contains=cap_cfg.title_contains,
            process_contains=cap_cfg.process_contains,
            shot_tool=cap_cfg.shot_tool or None)
    # No X window and no Wayland marker — keep the mss capture so the error
    # message at grab time explains exactly what's missing.
    return cap


def cmd_config(args) -> int:
    path = args.path or DEFAULT_CONFIG_PATH
    cfg = MacroConfig.default()
    if os.path.exists(path):
        # Merge onto whatever is already there so we don't clobber edits.
        cfg = MacroConfig.load(path)
    saved = cfg.save(path)
    print(f"Wrote config -> {saved}")
    problems = cfg.validate()
    if problems:
        print("Note: configuration has issues:")
        for p in problems:
            print(f"  - {p}")
    return 0


def cmd_run(args) -> int:
    cfg = MacroConfig.load(args.config)
    if args.objective:
        cfg.objective = args.objective
    if args.templates:
        cfg.templates_dir = args.templates
    problems = cfg.validate()
    if problems:
        print("Configuration problems:")
        for p in problems:
            print(f"  - {p}")
        if not args.force:
            print("Pass --force to run anyway.")
            return 1

    input_kind = "fake" if args.fake else cfg.input_kind
    ctrl = get_input(input_kind)
    capture = None if args.fake else _make_capture(cfg)
    webhook = DiscordWebhook(cfg.webhook) if cfg.webhook.enabled() else None
    if webhook is not None:
        webhook.notify_event("start", _fresh_stats(), None)

    from .engine import Engine

    engine = Engine(cfg, ctrl, capture, webhook, status_cb=_print_status)
    print(f"Starting BSS macro (objective={cfg.objective}, input={input_kind})…")
    if input_kind == "auto":
        print(f"input backend: {describe_auto()}")
    print("Ctrl+C to stop.")
    if capture is None:
        # Dry run: step synthetic frames so we still exercise the pipeline.
        print("[dry-run] No live capture — feeding synthetic frames.")
        _dry_run(engine, ctrl)
        return 0
    engine.start()
    try:
        while engine.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        engine.stop()
    return 0


def _dry_run(engine, ctrl) -> None:
    from .types import empty_frame

    try:
        for _ in range(30):
            engine.loop_once(empty_frame(640, 480))
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()


def cmd_calibrate(args) -> int:
    from .calibrate import run_calibrate

    return run_calibrate(args)


def cmd_webhook_test(args) -> int:
    cfg = MacroConfig.load(args.config)
    if not cfg.webhook.enabled():
        print("No webhook URL configured (see config -> webhook.url).")
        return 1
    wh = DiscordWebhook(cfg.webhook)
    ok = wh.send(_fresh_stats(), None, title="BSS Macro webhook test",
                description="If you can read this, your webhook works 🎉")
    print("Webhook sent." if ok else "Webhook failed (check the URL / network).")
    return 0 if ok else 1


def cmd_selftest(args) -> int:
    import unittest

    from .tests import run_tests

    result = run_tests()
    return 0 if result.wasSuccessful() else 1


def cmd_version(_args) -> int:
    print(f"bssmacro {__version__}")
    return 0


# -- helpers ----------------------------------------------------------------
def _print_status(s: dict) -> None:
    print(f"[{s.get('state'):>10}] mode={s.get('mode'):<7} "
          f"target={s.get('target')} honey={s.get('honey')} "
          f"tokens={s.get('tokens')} fps={s.get('fps')}")


def _fresh_stats():
    from .types import Stats

    return Stats()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bssmacro", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("config", help="write a default config.json")
    pc.add_argument("--path", default=None)
    pc.set_defaults(func=cmd_config)

    pr = sub.add_parser("run", help="start farming")
    pr.add_argument("--config", default=None)
    pr.add_argument("--objective", default=None,
                   choices=["field", "windy", "stinger", "mixed"])
    pr.add_argument("--templates", default=None)
    pr.add_argument("--fake", action="store_true",
                   help="drive the pipeline without injecting real input")
    pr.add_argument("--force", action="store_true")
    pr.set_defaults(func=cmd_run)

    pcal = sub.add_parser("calibrate", help="capture Sober + crop templates")
    pcal.add_argument("--config", default=None)
    pcal.add_argument("--templates-dir", default=None)
    pcal.add_argument("--labels", nargs="*", default=None)
    pcal.set_defaults(func=cmd_calibrate)

    pw = sub.add_parser("webhook-test", help="send a test embed")
    pw.add_argument("--config", default=None)
    pw.set_defaults(func=cmd_webhook_test)

    ps = sub.add_parser("selftest", help="run headless unit tests")
    ps.set_defaults(func=cmd_selftest)

    pv = sub.add_parser("version", help="print version")
    pv.set_defaults(func=cmd_version)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
