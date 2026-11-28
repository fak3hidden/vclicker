"""Canonical key table for the macro's input backends.

A key is identified by a short, portable name ("a", "space", "f8", "numpad3").
Each entry carries the X11 keysym name used by :mod:`bssmacro.input.linux_x11`;
the uinput / ydotool backends use their own EV_KEY code table in
:mod:`bssmacro.input.linux_uinput`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyInfo:
    name: str
    label: str
    x11: str | None = None      # X11 keysym name


def _k(name: str, label: str, x11: str | None = None) -> KeyInfo:
    return KeyInfo(name, label, x11)


_LETTERS = "abcdefghijklmnopqrstuvwxyz"

_DIGITS = "0123456789"

_PUNCT = {
    # name: (label, x11 keysym)
    "minus": ("-", "minus"),
    "equal": ("=", "equal"),
    "comma": (",", "comma"),
    "period": (".", "period"),
    "slash": ("/", "slash"),
    "semicolon": (";", "semicolon"),
    "apostrophe": ("'", "apostrophe"),
    "grave": ("`", "grave"),
    "bracketleft": ("[", "bracketleft"),
    "bracketright": ("]", "bracketright"),
    "backslash": ("\\", "backslash"),
}

_SPECIAL = [
    # name, label, x11 keysym
    ("esc", "Esc", "Escape"),
    ("tab", "Tab", "Tab"),
    ("capslock", "Caps Lock", "Caps_Lock"),
    ("space", "Space", "space"),
    ("enter", "Enter", "Return"),
    ("backspace", "Backspace", "BackSpace"),
    ("insert", "Insert", "Insert"),
    ("delete", "Delete", "Delete"),
    ("home", "Home", "Home"),
    ("end", "End", "End"),
    ("pageup", "PgUp", "Prior"),
    ("pagedown", "PgDn", "Next"),
    ("up", "Up", "Up"),
    ("down", "Down", "Down"),
    ("left", "Left", "Left"),
    ("right", "Right", "Right"),
    ("printscreen", "PrtSc", "Print"),
    ("scrolllock", "ScrLk", "Scroll_Lock"),
    ("pause", "Pause", "Pause"),
    ("menu", "Menu", "Menu"),
    ("ctrl", "Ctrl", "Control_L"),
    ("shift", "Shift", "Shift_L"),
    ("alt", "Alt", "Alt_L"),
    ("win", "Win", "Super_L"),
    ("numlock", "Num Lock", "Num_Lock"),
    ("numpad0", "Num 0", "KP_0"),
    ("numpad1", "Num 1", "KP_1"),
    ("numpad2", "Num 2", "KP_2"),
    ("numpad3", "Num 3", "KP_3"),
    ("numpad4", "Num 4", "KP_4"),
    ("numpad5", "Num 5", "KP_5"),
    ("numpad6", "Num 6", "KP_6"),
    ("numpad7", "Num 7", "KP_7"),
    ("numpad8", "Num 8", "KP_8"),
    ("numpad9", "Num 9", "KP_9"),
    ("numpad_add", "Num +", "KP_Add"),
    ("numpad_sub", "Num -", "KP_Subtract"),
    ("numpad_mul", "Num *", "KP_Multiply"),
    ("numpad_div", "Num /", "KP_Divide"),
    ("numpad_dec", "Num .", "KP_Decimal"),
    ("numpad_enter", "Num Enter", "KP_Enter"),
    ("volume_up", "Vol+", "XF86AudioRaiseVolume"),
    ("volume_down", "Vol-", "XF86AudioLowerVolume"),
    ("volume_mute", "Mute", "XF86AudioMute"),
    ("media_play", "Play", "XF86AudioPlay"),
    ("media_next", "Next", "XF86AudioNext"),
    ("media_prev", "Prev", "XF86AudioPrev"),
    ("media_stop", "Stop", "XF86AudioStop"),
]

KEYS: dict[str, KeyInfo] = {}

for _name in _LETTERS:
    KEYS[_name] = _k(_name, _name.upper(), _name)
for _name in _DIGITS:
    KEYS[_name] = _k(_name, _name, _name)
for _name, (_label, _x11) in _PUNCT.items():
    KEYS[_name] = _k(_name, _label, _x11)
for _name, _label, _x11 in _SPECIAL:
    KEYS[_name] = _k(_name, _label, _x11)

for _i in range(1, 25):
    KEYS[f"f{_i}"] = _k(f"f{_i}", f"F{_i}", f"F{_i}")

MODIFIER_ORDER = ("ctrl", "shift", "alt", "win")
MODIFIER_LABELS = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win"}

# X11 button numbers (as used by XTestFakeButtonEvent).
MOUSE_BUTTONS = {
    "left": 1,
    "middle": 2,
    "right": 3,
    "back": 8,     # XBUTTON1
    "forward": 9,  # XBUTTON2
}


def info(name: str) -> KeyInfo:
    return KEYS.get(name) or KeyInfo(name, name.upper())


def label(name: str | None) -> str:
    if not name:
        return "—"
    return info(name).label


def is_modifier(name: str | None) -> bool:
    return bool(name) and name in MODIFIER_ORDER


def normalize(name: str | None) -> str | None:
    """Best-effort cleanup of key names coming from configs."""

    if not name:
        return None
    name = str(name).strip().lower()
    aliases = {
        "escape": "esc", "return": "enter", "del": "delete", "ins": "insert",
        "control": "ctrl", "cmd": "win", "command": "win", "super": "win",
        "option": "alt", "pgup": "pageup", "pgdn": "pagedown",
        "spacebar": "space",
    }
    return aliases.get(name, name)


def parse_parts(name: str | None) -> list[str]:
    """Split a combo string ("ctrl+shift+k") into canonical key names."""

    if not name:
        return []
    out: list[str] = []
    for raw in str(name).replace(" ", "").split("+"):
        key = normalize(raw)
        if key and key in KEYS and key not in out:
            out.append(key)
    return out
