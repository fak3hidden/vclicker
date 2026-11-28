"""Native-Wayland capture: find the Sober window and screenshot it.

Wayland doesn't let clients poke other clients' windows, so both jobs are done
through what the compositor *does* expose:

Window geometry
---------------
* **Hyprland** — ``hyprctl clients -j``
* **sway / other wlroots** — ``swaymsg -t get_tree -r``
* GNOME/KDE have no equivalent CLI, so there we fall back to a full-output
  capture; put Sober in **fullscreen** and the window rect *is* the screen.

Screen capture
--------------
A small chain of compositor screenshot tools is tried until one works:
``grim`` (wlroots) → ``wayshot`` (wlroots) → ``spectacle`` (KDE) →
``gnome-screenshot`` (GNOME) → ``scrot`` / ``maim`` / ``import`` (X11
fallbacks). All of them honour the compositor's own screenshot permission
model, so nothing is bypassed — it's the same as pressing PrintScreen.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ..types import Frame, Rect


@dataclass(slots=True)
class WaylandWindow:
    title: str
    process: str
    pid: int
    x: int
    y: int
    w: int
    h: int

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.w, self.h)


def _proc_name(pid: int) -> str:
    if not pid:
        return ""
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _matches(win: WaylandWindow, titles: List[str], procs: List[str]) -> bool:
    title_low = (win.title or "").lower()
    proc_low = ((win.process or "") + " " + title_low).lower()
    if any(t.lower() in title_low for t in titles):
        return True
    return any(p.lower() in proc_low for p in procs)


# --- compositor-specific window lists ---------------------------------------
def parse_sway_tree(tree: dict, titles: List[str], procs: List[str]) -> List[WaylandWindow]:
    """Extract matching windows from a ``swaymsg -t get_tree -r`` payload."""

    out: List[WaylandWindow] = []

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return
        title = node.get("title") or node.get("name") or ""
        pid = node.get("pid") or 0
        rect = node.get("rect") or {}
        win_rect = node.get("window_rect") or {}
        if node.get("type") in ("con", "floating_con") and rect:
            x = int(rect.get("x", 0)) + int(win_rect.get("x", 0))
            y = int(rect.get("y", 0)) + int(win_rect.get("y", 0))
            w = int(win_rect.get("width", rect.get("width", 0)))
            h = int(win_rect.get("height", rect.get("height", 0)))
            if w > 0 and h > 0:
                win = WaylandWindow(title, _proc_name(int(pid)), int(pid),
                                    x, y, w, h)
                if _matches(win, titles, procs):
                    out.append(win)
        for child in node.get("nodes") or []:
            walk(child)
        for child in node.get("floating_nodes") or []:
            walk(child)

    walk(tree)
    return out


def parse_hypr_clients(clients: list, titles: List[str], procs: List[str]) -> List[WaylandWindow]:
    """Extract matching windows from a ``hyprctl clients -j`` payload."""

    out: List[WaylandWindow] = []
    for c in clients or []:
        at = c.get("at") or [0, 0]
        size = c.get("size") or [0, 0]
        if len(at) < 2 or len(size) < 2 or size[0] <= 0 or size[1] <= 0:
            continue
        title = c.get("title") or c.get("initialTitle") or ""
        proc = c.get("class") or c.get("initialClass") or ""
        pid = int(c.get("pid") or 0)
        win = WaylandWindow(title, proc or _proc_name(pid), pid,
                            int(at[0]), int(at[1]), int(size[0]), int(size[1]))
        if _matches(win, titles, procs):
            out.append(win)
    return out


class WaylandWindowFinder:
    """Finds the Sober/Roblox window using compositor IPC, when available."""

    def available(self) -> bool:
        if shutil.which("swaymsg") or os.environ.get("SWAYSOCK"):
            return True
        if shutil.which("hyprctl") or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return True
        return False

    def list_windows(self, title_contains: Optional[List[str]] = None,
                     process_contains: Optional[List[str]] = None) -> List[WaylandWindow]:
        titles = title_contains or ["Sober", "Roblox", "sober"]
        procs = process_contains or ["sober", "roblox", "RobloxPlayer"]
        windows: List[WaylandWindow] = []
        if shutil.which("swaymsg") or os.environ.get("SWAYSOCK"):
            try:
                raw = subprocess.run(
                    ["swaymsg", "-t", "get_tree", "-r"],
                    capture_output=True, timeout=5, check=True).stdout
                windows = parse_sway_tree(json.loads(raw), titles, procs)
            except Exception:
                pass
        if not windows and (shutil.which("hyprctl")
                            or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")):
            try:
                raw = subprocess.run(
                    ["hyprctl", "clients", "-j"],
                    capture_output=True, timeout=5, check=True).stdout
                windows = parse_hypr_clients(json.loads(raw), titles, procs)
            except Exception:
                pass
        return windows

    def find(self, title_contains: Optional[List[str]] = None,
             process_contains: Optional[List[str]] = None) -> Optional[WaylandWindow]:
        wins = self.list_windows(title_contains, process_contains)
        return wins[0] if wins else None


# --- screenshot-tool chain ---------------------------------------------------
@dataclass
class _ShotTool:
    name: str
    argv: List[str]          # {out} = temp file placeholder
    stdout: bool = False     # True: PNG comes on stdout instead of a file


def _shot_tools(preferred: Optional[str] = None) -> List[_ShotTool]:
    tools = [
        _ShotTool("grim", ["grim", "--", "{out}"]),
        _ShotTool("wayshot", ["wayshot"], stdout=True),
        _ShotTool("spectacle", ["spectacle", "-b", "-n", "-f", "-o", "{out}"]),
        _ShotTool("gnome-screenshot", ["gnome-screenshot", "-f", "{out}"]),
        _ShotTool("scrot", ["scrot", "-o", "{out}"]),
        _ShotTool("maim", ["maim", "{out}"]),
        _ShotTool("import", ["import", "-window", "root", "{out}"]),
    ]
    if preferred:
        preferred = preferred.lower()
        tools.sort(key=lambda t: 0 if t.name == preferred else 1)
    return [t for t in tools if shutil.which(t.argv[0]) is not None]


class ShotCapture:
    """Grab frames by shelling out to the compositor's screenshot tool.

    Slower than ``mss`` (one process spawn per frame, typically 100–400 ms) but
    it works on native Wayland without any portal plumbing. Use
    ``capture.method = "cli"`` (or let ``auto`` pick it) on Wayland.
    """

    def __init__(self, downscale: float = 1.0,
                 title_contains: Optional[List[str]] = None,
                 process_contains: Optional[List[str]] = None,
                 fixed_region: Optional[Rect] = None,
                 shot_tool: Optional[str] = None,
                 timeout: float = 10.0,
                 finder: Optional[WaylandWindowFinder] = None) -> None:
        self.downscale = downscale or 1.0
        self.title_contains = title_contains
        self.process_contains = process_contains
        if isinstance(fixed_region, (tuple, list)):
            fixed_region = Rect(*fixed_region[:4])
        self.fixed_region = fixed_region
        self.shot_tool = shot_tool
        self.timeout = timeout
        self._finder = finder
        self._tool: Optional[_ShotTool] = None
        self._failed: set[str] = set()
        self._full: Optional[Frame] = None

    # -- tool selection ----------------------------------------------------
    def _ensure_tool(self) -> _ShotTool:
        if self._tool is None:
            tools = [t for t in _shot_tools(self.shot_tool)
                     if t.name not in self._failed]
            if not tools:
                if self._failed:
                    raise RuntimeError(
                        f"All screenshot tools failed (tried: "
                        f"{', '.join(sorted(self._failed))}). Is the "
                        "compositor allowing screenshots?")
                raise RuntimeError(
                    "No Wayland screenshot tool found. Install one of: "
                    "grim (wlroots/sway/Hyprland), spectacle (KDE), "
                    "gnome-screenshot (GNOME), or scrot/maim (X11).")
            self._tool = tools[0]
        return self._tool

    def _exec_tool(self, tool: _ShotTool) -> Optional[bytes]:
        if tool.stdout:
            proc = subprocess.run(tool.argv, capture_output=True,
                                  timeout=self.timeout)
            if proc.returncode != 0 or not proc.stdout:
                return None
            return proc.stdout
        fd, path = tempfile.mkstemp(suffix=".png", prefix="bssmacro-")
        os.close(fd)
        try:
            argv = [path if a == "{out}" else a for a in tool.argv]
            proc = subprocess.run(argv, capture_output=True,
                                  timeout=self.timeout)
            if proc.returncode != 0 or not os.path.exists(path) \
                    or os.path.getsize(path) == 0:
                return None
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    # -- geometry ------------------------------------------------------------
    def _window_rect(self) -> Optional[Rect]:
        finder = self._finder or WaylandWindowFinder()
        try:
            win = finder.find(self.title_contains, self.process_contains)
        except Exception:
            return None
        return win.rect if win else None

    def region(self) -> Rect:
        if self.fixed_region is not None:
            return self.fixed_region
        rect = self._window_rect()
        if rect is None:
            # No compositor IPC — capture the whole output. Fullscreen Sober
            # makes this exactly the game area.
            full = self._full_frame()
            return Rect(0, 0, full.width, full.height)
        return rect

    def _full_frame(self) -> Frame:
        import cv2

        tried: list[str] = []
        while True:
            tool = self._ensure_tool()   # raises once every candidate failed
            tried.append(tool.name)
            data = self._exec_tool(tool)
            if data:
                break
            self._failed.add(tool.name)  # try the next tool immediately
            self._tool = None
        arr = cv2.imdecode(np.frombuffer(data, dtype="uint8"), cv2.IMREAD_COLOR)
        if arr is None:
            self._failed.add(tool.name)
            self._tool = None
            raise RuntimeError(
                f"Screenshot from '{tool.name}' could not be decoded as an "
                "image.")
        h, w = arr.shape[:2]
        frame = Frame(bgr=arr, region=Rect(0, 0, w, h), source=tool.name)
        self._full = frame
        return frame

    # -- Frame API (mirrors ScreenCapture) ------------------------------------
    def grab(self) -> Frame:
        import cv2

        full = self._full_frame()
        rect = self.fixed_region if self.fixed_region is not None \
            else self._window_rect()
        if rect is None:
            rect = Rect(0, 0, full.width, full.height)
        x0 = max(0, rect.x)
        y0 = max(0, rect.y)
        x1 = min(full.width, rect.x + rect.w)
        y1 = min(full.height, rect.y + rect.h)
        crop = full.bgr[y0:y1, x0:x1]
        if crop.size == 0:
            raise RuntimeError(
                f"Crop region {rect.as_tuple()} is outside the captured "
                f"screen ({full.width}x{full.height}).")
        f = self.downscale
        if f != 1.0:
            crop = cv2.resize(
                crop, (max(1, int(crop.shape[1] * f)), max(1, int(crop.shape[0] * f))),
                interpolation=cv2.INTER_AREA)
        return Frame(bgr=crop, region=rect, source=full.source)

    def close(self) -> None:
        self._full = None
