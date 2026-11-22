"""Small JSON-backed settings store."""

from __future__ import annotations

import copy
import json
import os
from typing import Any

from .core.hotkeys import DEFAULT_BINDINGS
from .paths import config_path

DEFAULTS: dict[str, Any] = {
    "ui": {
        "accent": "indigo",
        "always_on_top": False,
        "last_page": 0,
        "window": [1240, 840],
        "maximized": False,
    },
    "hotkeys_enabled": True,
    "hotkeys": dict(DEFAULT_BINDINGS),
    "clicker": {
        "mode": "cps",
        "cps": 25.0,
        "ms": 40.0,
        "button": "left",
        "double": False,
        "burst": 1,
        "limit_mode": "none",
        "limit_clicks": 100,
        "limit_seconds": 10.0,
        "position": "cursor",
        "x": 0,
        "y": 0,
        "jitter": 0.0,
    },
    "keyholder": {
        "keys": ["space"],
        "timing": "hold",
        "duration": 5.0,
        "repeat": False,
        "repeat_ms": 100.0,
        "target": "global",
        "windows": [],
    },
    "macro": {
        "speed": 1.0,
        "loops": 1,
        "instant": False,
        "record_injected": False,
        "selected": "",
    },
}


def _deep_merge(base: dict, extra: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config_path()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    # -- io ---------------------------------------------------------------- #
    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self.data = _deep_merge(DEFAULTS, stored)
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # -- access ------------------------------------------------------------ #
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any, save: bool = True) -> None:
        node = self.data
        parts = dotted.split(".")
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        if save:
            self.save()

    def section(self, name: str) -> dict:
        value = self.get(name, {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}
