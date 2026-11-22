"""Canonical key table shared by every platform backend.

A key is identified by a short, portable name ("a", "space", "f8", "numpad3").
Each entry knows how to reach that key on Windows (virtual-key code), X11
(keysym name) and macOS (virtual key code).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyInfo:
    name: str
    label: str
    mod: str | None = None      # "ctrl" / "shift" / "alt" / "win" for modifiers
    vk: int | None = None       # Windows virtual-key code
    x11: str | None = None      # X11 keysym name
    mac: int | None = None      # macOS virtual key code


def _k(name, label, mod=None, vk=None, x11=None, mac=None) -> KeyInfo:
    return KeyInfo(name, label, mod, vk, x11, mac)


_LETTERS = {
    # name: (vk, mac)
    "a": (0x41, 0), "s": (0x53, 1), "d": (0x44, 2), "f": (0x46, 3),
    "h": (0x48, 4), "g": (0x47, 5), "z": (0x5A, 6), "x": (0x58, 7),
    "c": (0x43, 8), "v": (0x56, 9), "b": (0x42, 11), "q": (0x51, 12),
    "w": (0x57, 13), "e": (0x45, 14), "r": (0x52, 15), "y": (0x59, 16),
    "t": (0x54, 17), "o": (0x4F, 31), "u": (0x55, 32), "i": (0x49, 34),
    "p": (0x50, 35), "l": (0x4C, 37), "j": (0x4A, 38), "k": (0x4B, 40),
    "n": (0x4E, 45), "m": (0x4D, 46),
}

_DIGITS = {
    "1": (0x31, 18), "2": (0x32, 19), "3": (0x33, 20), "4": (0x34, 21),
    "5": (0x35, 23), "6": (0x36, 22), "7": (0x37, 26), "8": (0x38, 28),
    "9": (0x39, 25), "0": (0x30, 29),
}

_PUNCT = {
    # name: (label, vk, x11 keysym, mac)
    "minus": ("-", 0xBD, "minus", 27),
    "equal": ("=", 0xBB, "equal", 24),
    "comma": (",", 0xBC, "comma", 43),
    "period": (".", 0xBE, "period", 47),
    "slash": ("/", 0xBF, "slash", 44),
    "semicolon": (";", 0xBA, "semicolon", 41),
    "apostrophe": ("'", 0xDE, "apostrophe", 39),
    "grave": ("`", 0xC0, "grave", 50),
    "bracketleft": ("[", 0xDB, "bracketleft", 33),
    "bracketright": ("]", 0xDD, "bracketright", 30),
    "backslash": ("\\", 0xDC, "backslash", 42),
}

_SPECIAL = [
    # name, label, mod, vk, x11, mac
    ("esc", "Esc", None, 0x1B, "Escape", 53),
    ("tab", "Tab", None, 0x09, "Tab", 48),
    ("capslock", "Caps Lock", None, 0x14, "Caps_Lock", 57),
    ("space", "Space", None, 0x20, "space", 49),
    ("enter", "Enter", None, 0x0D, "Return", 36),
    ("backspace", "Backspace", None, 0x08, "BackSpace", 51),
    ("insert", "Insert", None, 0x2D, "Insert", 114),
    ("delete", "Delete", None, 0x2E, "Delete", 117),
    ("home", "Home", None, 0x24, "Home", 115),
    ("end", "End", None, 0x23, "End", 119),
    ("pageup", "PgUp", None, 0x21, "Prior", 116),
    ("pagedown", "PgDn", None, 0x22, "Next", 121),
    ("up", "Up", None, 0x26, "Up", 126),
    ("down", "Down", None, 0x28, "Down", 125),
    ("left", "Left", None, 0x25, "Left", 123),
    ("right", "Right", None, 0x27, "Right", 124),
    ("printscreen", "PrtSc", None, 0x2C, "Print", None),
    ("scrolllock", "ScrLk", None, 0x91, "Scroll_Lock", None),
    ("pause", "Pause", None, 0x13, "Pause", None),
    ("menu", "Menu", None, 0x5D, "Menu", 110),
    ("ctrl", "Ctrl", "ctrl", 0x11, "Control_L", 59),
    ("shift", "Shift", "shift", 0x10, "Shift_L", 56),
    ("alt", "Alt", "alt", 0x12, "Alt_L", 58),
    ("win", "Win", "win", 0x5B, "Super_L", 55),
    ("numlock", "Num Lock", None, 0x90, "Num_Lock", 71),
    ("numpad0", "Num 0", None, 0x60, "KP_0", 82),
    ("numpad1", "Num 1", None, 0x61, "KP_1", 83),
    ("numpad2", "Num 2", None, 0x62, "KP_2", 84),
    ("numpad3", "Num 3", None, 0x63, "KP_3", 85),
    ("numpad4", "Num 4", None, 0x64, "KP_4", 86),
    ("numpad5", "Num 5", None, 0x65, "KP_5", 87),
    ("numpad6", "Num 6", None, 0x66, "KP_6", 88),
    ("numpad7", "Num 7", None, 0x67, "KP_7", 89),
    ("numpad8", "Num 8", None, 0x68, "KP_8", 91),
    ("numpad9", "Num 9", None, 0x69, "KP_9", 92),
    ("numpad_add", "Num +", None, 0x6B, "KP_Add", 69),
    ("numpad_sub", "Num -", None, 0x6D, "KP_Subtract", 78),
    ("numpad_mul", "Num *", None, 0x6A, "KP_Multiply", 67),
    ("numpad_div", "Num /", None, 0x6F, "KP_Divide", 75),
    ("numpad_dec", "Num .", None, 0x6E, "KP_Decimal", 65),
    ("numpad_enter", "Num Enter", None, 0x0D, "KP_Enter", 76),
    ("volume_up", "Vol+", None, 0xAF, "XF86AudioRaiseVolume", 72),
    ("volume_down", "Vol-", None, 0xAE, "XF86AudioLowerVolume", 73),
    ("volume_mute", "Mute", None, 0xAD, "XF86AudioMute", 74),
    ("media_play", "Play", None, 0xB3, "XF86AudioPlay", None),
    ("media_next", "Next", None, 0xB0, "XF86AudioNext", None),
    ("media_prev", "Prev", None, 0xB1, "XF86AudioPrev", None),
    ("media_stop", "Stop", None, 0xB2, "XF86AudioStop", None),
]

KEYS: dict[str, KeyInfo] = {}

for _name, (_vk, _mac) in _LETTERS.items():
    KEYS[_name] = _k(_name, _name.upper(), None, _vk, _name, _mac)
for _name, (_vk, _mac) in _DIGITS.items():
    KEYS[_name] = _k(_name, _name, None, _vk, _name, _mac)
for _name, (_label, _vk, _x11, _mac) in _PUNCT.items():
    KEYS[_name] = _k(_name, _label, None, _vk, _x11, _mac)
for _name, _label, _mod, _vk, _x11, _mac in _SPECIAL:
    KEYS[_name] = _k(_name, _label, _mod, _vk, _x11, _mac)

for _i in range(1, 25):
    KEYS[f"f{_i}"] = _k(f"f{_i}", f"F{_i}", None, 0x6F + _i, f"F{_i}", {
        1: 122, 2: 120, 3: 99, 4: 118, 5: 96, 6: 97, 7: 98, 8: 100, 9: 101,
        10: 109, 11: 103, 12: 111, 13: 105, 14: 107, 15: 113, 16: 106,
        17: 64, 18: 79, 19: 80, 20: 90,
    }.get(_i))
KEYS["numpad_enter"] = _k("numpad_enter", "Num Enter", None, 0x0D, "KP_Enter", 76)

MODIFIER_ORDER = ("ctrl", "shift", "alt", "win")
MODIFIER_LABELS = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win"}

# Windows virtual-key -> canonical name.  Left/right variants collapse onto the
# generic modifier so a combo recorded on either side still matches.
VK_TO_NAME: dict[int, str] = {}
for _name, _info in KEYS.items():
    if _info.vk is None:
        continue
    if _info.mod:
        VK_TO_NAME.setdefault(_info.vk, _name)
    else:
        VK_TO_NAME[_info.vk] = _name
# Explicit duplicates Windows reports separately.
VK_TO_NAME.update({
    0xA0: "shift", 0xA1: "shift",
    0xA2: "ctrl", 0xA3: "ctrl",
    0xA4: "alt", 0xA5: "alt",
    0x5C: "win",
})

# X11 keysym names that differ from our canonical names.
X11_TO_NAME = {info.x11.lower(): name for name, info in KEYS.items() if info.x11}
X11_TO_NAME.update({
    "shift_l": "shift", "shift_r": "shift",
    "control_l": "ctrl", "control_r": "ctrl",
    "alt_l": "alt", "alt_r": "alt",
    "meta_l": "alt", "meta_r": "alt",
    "super_l": "win", "super_r": "win",
    "kp_enter": "numpad_enter",
    "kp_decimal": "numpad_dec",
})

MAC_TO_NAME = {info.mac: name for name, info in KEYS.items() if info.mac is not None}
# macOS reports left/right modifiers with distinct codes; collapse to generic.
MAC_TO_NAME.update({60: "shift", 62: "ctrl", 61: "alt", 54: "win", 55: "win"})

MOUSE_BUTTONS = {
    "left": 1,
    "middle": 2,
    "right": 3,
    "back": 8,     # X11 / Windows XBUTTON1
    "forward": 9,  # X11 / Windows XBUTTON2
}


def info(name: str) -> KeyInfo:
    return KEYS.get(name) or KeyInfo(name, name.upper())


def label(name: str | None) -> str:
    if not name:
        return "—"
    return info(name).label


def is_modifier(name: str | None) -> bool:
    return bool(name) and KEYS.get(name, KeyInfo("", "")).mod is not None


def normalize(name: str | None) -> str | None:
    """Best-effort cleanup of key names coming from capture widgets / configs."""
    if not name:
        return None
    name = str(name).strip().lower()
    aliases = {
        "escape": "esc", "return": "enter", "del": "delete", "ins": "insert",
        "control": "ctrl", "cmd": "win", "command": "win", "super": "win",
        "option": "alt", "pgup": "pageup", "pgdn": "pagedown",
        "num0": "numpad0", "num1": "numpad1", "num2": "numpad2",
        "num3": "numpad3", "num4": "numpad4", "num5": "numpad5",
        "num6": "numpad6", "num7": "numpad7", "num8": "numpad8",
        "num9": "numpad9", "spacebar": "space",
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


def combo_text(name: str | None) -> str:
    parts = parse_parts(name)
    if not parts:
        return "Not set"
    ordered = [p for m in MODIFIER_ORDER for p in parts if KEYS[p].mod == m]
    ordered += [p for p in parts if KEYS[p].mod is None]
    return " + ".join(label(p) for p in ordered)


def combo_from_event(key: str | None, pressed: set[str]) -> str | None:
    """Build a combo string from a pressed non-modifier key plus held modifiers."""
    if not key or is_modifier(key):
        return None
    mods = [m for m in MODIFIER_ORDER if m in pressed]
    return "+".join(mods + [key])
