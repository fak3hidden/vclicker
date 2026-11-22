"""App data locations (config + macros)."""

from __future__ import annotations

import os
import sys

APP_NAME = "VClicker"


def app_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    elif sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(base, "vclicker")
    os.makedirs(path, exist_ok=True)
    return path


def macros_dir() -> str:
    path = os.path.join(app_dir(), "macros")
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def logs_dir() -> str:
    path = os.path.join(app_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def asset_path(*parts: str) -> str:
    """Locate a bundled asset (fonts/icons ship inside the package)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidate = os.path.join(base, "assets", *parts)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", *parts)
