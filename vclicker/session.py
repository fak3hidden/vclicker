"""Linux desktop-session and distribution detection.

Small helpers so the rest of the app can explain *why* input is unavailable
instead of showing a raw ctypes traceback.
"""

from __future__ import annotations

import os
import sys


def _os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                key, _, value = line.strip().partition("=")
                if key and value:
                    data[key] = value.strip().strip('"')
    except OSError:
        pass
    return data


_OS = _os_release()
_OS_IDS = {_OS.get("ID", "").lower(), *(_OS.get("ID_LIKE", "").lower().split())} - {""}

#: "wayland" | "x11" | "tty" | "none" (Windows/macOS report "none")
SESSION_KIND = "none"
if sys.platform.startswith("linux"):
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        SESSION_KIND = "wayland"
    elif os.environ.get("DISPLAY"):
        SESSION_KIND = "x11"
    elif os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11":
        SESSION_KIND = "x11"
    else:
        SESSION_KIND = "tty"


def kind() -> str:
    return SESSION_KIND


def display() -> str:
    return os.environ.get("DISPLAY", "")


def wayland_display() -> str:
    return os.environ.get("WAYLAND_DISPLAY", "")


def distro_id() -> str:
    return _OS.get("ID", "").lower()


def distro_name() -> str:
    name = _OS.get("PRETTY_NAME") or _OS.get("NAME") or "Linux"
    return str(name)


def package_family() -> str:
    """Return 'debian' | 'arch' | 'fedora' | 'suse' | 'alpine' | 'linux'."""
    if _OS_IDS & {"debian", "ubuntu", "linuxmint", "pop", "elementary", "kali", "raspbian", "zorin"}:
        return "debian"
    if _OS_IDS & {"arch", "manjaro", "endeavouros", "garuda", "steamos", "cachyos"}:
        return "arch"
    if _OS_IDS & {"fedora", "rhel", "centos", "rocky", "almalinux", "nobara", "bazzite"}:
        return "fedora"
    if _OS_IDS & {"opensuse", "opensuse-tumbleweed", "opensuse-leap", "sles", "suse"}:
        return "suse"
    if _OS_IDS & {"alpine"}:
        return "alpine"
    return "linux"


#: Missing shared object -> package name, per family.
PACKAGES = {
    "libXtst.so.6": {
        "debian": "libxtst6", "arch": "libxtst", "fedora": "libXtst",
        "suse": "libXtst6", "alpine": "libxtst", "linux": "libXtst",
    },
    "libxcb-cursor.so.0": {
        "debian": "libxcb-cursor0", "arch": "xcb-util-cursor", "fedora": "xcb-util-cursor",
        "suse": "libxcb-cursor0", "alpine": "xcb-util-cursor", "linux": "xcb-util-cursor",
    },
    "libxkbcommon-x11.so.0": {
        "debian": "libxkbcommon-x11-0", "arch": "libxkbcommon-x11", "fedora": "libxkbcommon-x11",
        "suse": "libxkbcommon-x11-0", "alpine": "libxkbcommon", "linux": "libxkbcommon-x11",
    },
    "libGL.so.1": {
        "debian": "libgl1", "arch": "mesa", "fedora": "mesa-libGL",
        "suse": "Mesa-libGL1", "alpine": "mesa-gl", "linux": "mesa",
    },
    "libEGL.so.1": {
        "debian": "libegl1", "arch": "mesa", "fedora": "mesa-libEGL",
        "suse": "Mesa-libEGL1", "alpine": "mesa-egl", "linux": "mesa",
    },
    "libfontconfig.so.1": {
        "debian": "libfontconfig1", "arch": "fontconfig", "fedora": "fontconfig",
        "suse": "fontconfig", "alpine": "fontconfig", "linux": "fontconfig",
    },
    "libdbus-1.so.3": {
        "debian": "libdbus-1-3", "arch": "dbus", "fedora": "dbus-libs",
        "suse": "libdbus-1-3", "alpine": "dbus-libs", "linux": "dbus",
    },
}

_INSTALLERS = {
    "debian": ("sudo apt install -y", True),
    "arch": ("sudo pacman -S --needed", False),
    "fedora": ("sudo dnf install -y", False),
    "suse": ("sudo zypper install -y", False),
    "alpine": ("sudo apk add", False),
}


def install_command(missing: list[str] | None = None) -> str:
    """A copy-paste command that installs the packages needed to run."""
    family = package_family()
    base, _ = _INSTALLERS.get(family, ("# install with your package manager:", False))
    names: list[str] = []
    for lib in missing or list(PACKAGES):
        package = PACKAGES.get(lib, {}).get(family)
        if package and package not in names:
            names.append(package)
    if family == "debian":
        names = [name for name in names if name not in {"libgl1", "libegl1", "libfontconfig1"}]
    if not names:
        return f"{base} libxtst"
    return f"{base} {' '.join(names)}"


def session_summary() -> str:
    if SESSION_KIND == "wayland":
        suffix = f" (Wayland {wayland_display()})" if wayland_display() else ""
        return f"Wayland{suffix}"
    if SESSION_KIND == "x11":
        return f"X11 ({display()})"
    if SESSION_KIND == "tty":
        return "No graphical session"
    return "Not Linux"
