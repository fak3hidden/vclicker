"""Environment check: what works, what is missing, and how to fix it.

    vclicker --check          (or: python run.py --check)
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys

from . import session

#: (soname, human label, required for input, package key in session.PACKAGES)
LIBS: list[tuple[str, str, bool]] = [
    ("libX11.so.6", "X11 client library", True),
    ("libXtst.so.6", "XTest input injection", True),
    ("libxcb-cursor.so.0", "Qt 6 xcb platform plugin", True),
    ("libxkbcommon-x11.so.0", "Qt 6 X11 keyboard support", True),
    ("libGL.so.1", "OpenGL (Qt rendering)", False),
    ("libEGL.so.1", "EGL (Qt rendering)", False),
    ("libfontconfig.so.1", "font configuration", False),
    ("libdbus-1.so.3", "D-Bus (Qt notifications)", False),
]


def _present(soname: str) -> bool:
    try:
        ctypes.CDLL(soname)
        return True
    except OSError:
        return False


def missing_libraries() -> list[str]:
    """Libraries that are needed but cannot be loaded (input-critical first)."""
    return [soname for soname, _label, required in LIBS
            if required and not _present(soname)]


def _display_reachable() -> tuple[bool, str]:
    if session.kind() != "x11" and session.kind() != "wayland":
        return False, "no DISPLAY"
    try:
        xlib = ctypes.CDLL("libX11.so.6")
    except OSError as exc:
        return False, str(exc)
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = (ctypes.c_char_p,)
    dpy = xlib.XOpenDisplay(None)
    if not dpy:
        return False, f"cannot open {os.environ.get('DISPLAY', '?')}"
    xlib.XCloseDisplay.argtypes = (ctypes.c_void_p,)
    xlib.XCloseDisplay(dpy)
    return True, os.environ.get("DISPLAY", "")


def _pyside_version() -> str:
    try:
        import PySide6
        return PySide6.__version__
    except Exception as exc:  # pragma: no cover
        return f"missing ({exc})"


def _qt_platform() -> str:
    try:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app is None:
            return "not started"
        return QGuiApplication.platformName()
    except Exception as exc:  # pragma: no cover
        return f"unavailable ({exc})"


def report(include_qt: bool = True) -> str:
    lines: list[str] = []
    add = lines.append
    add("VClicker environment check")
    add("=" * 46)
    add(f"Python          {platform.python_version()}  ({sys.executable})")
    add(f"PySide6         {_pyside_version()}")
    add(f"System          {session.distro_name()}")
    add(f"Session         {session.session_summary()}")
    if include_qt:
        add(f"Qt platform     {_qt_platform()}")
    add("")

    if sys.platform.startswith("linux"):
        reachable, detail = _display_reachable()
        add(f"X display       {'reachable' if reachable else 'NOT reachable'}"
            + (f"  ({detail})" if detail else ""))
        add("")
        add("Native libraries")
        for soname, label, required in LIBS:
            state = "ok" if _present(soname) else ("MISSING" if required else "missing (optional)")
            add(f"  {soname:<24} {state:<20} {label}")

    add("")
    try:
        from .core.backend import get_backend
        backend = get_backend()
        caps = backend.caps
        add(f"Input backend   {backend.describe()}")
        flags = [
            ("clicks", caps.clicking), ("keys", caps.key_send),
            ("multi-window hold", caps.targeted_hold), ("window list", caps.window_list),
            ("recording", caps.recording), ("hotkeys", caps.hotkeys),
        ]
        add("Capabilities    " + "  ".join(f"{name}={'yes' if ok else 'no'}" for name, ok in flags))
    except Exception as exc:  # pragma: no cover
        add(f"Input backend   error: {exc}")

    missing = missing_libraries()
    add("")
    if sys.platform.startswith("linux") and (missing or session.kind() == "wayland"):
        add("What to fix")
        if missing:
            add(f"  Missing packages → {session.install_command(missing)}")
        if session.kind() == "wayland":
            add("  Wayland session: XTest only reaches X-Wayland (X11) windows.")
            add("  Native Wayland apps need an X11 session for now — log out and pick")
            add("  \"X11\" / \"Xorg\" in the login screen's session menu.")
        if not session.display() and session.kind() != "wayland":
            add("  No DISPLAY: run VClicker from inside your desktop, not from a TTY/SSH.")
    else:
        add("Nothing to fix — input layer looks good.")
    return "\n".join(line for line in lines if line is not None)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else []
    include_qt = "--no-qt" not in argv
    print(report(include_qt=include_qt))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
