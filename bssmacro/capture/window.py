"""Locate and focus the Sober (Linux Roblox) window via X11.

Sober renders Roblox in an X11 window (even under Wayland it normally runs under
XWayland), so the macro can find it the same way any X11 automation tool would:
walk ``_NET_CLIENT_LIST`` and read ``_NET_WM_NAME`` / ``_NET_WM_PID``.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import List, Optional

XA_WINDOW = 33
XA_CARDINAL = 6
ANY_PROPERTY_TYPE = 0
PROP_MODE_REPLACE = 0

class WindowFinderUnavailable(RuntimeError):
    """Raised when X11 is not available for window lookups."""


@dataclass(slots=True)
class WindowHandle:
    ident: int
    title: str
    process: str
    pid: int
    x: int
    y: int
    w: int
    h: int

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)


class X11WindowFinder:
    """Tiny ctypes wrapper around the bits of Xlib we need."""

    def __init__(self) -> None:
        xlib = None
        for name in ("libX11.so.6", "libX11.so"):
            try:
                xlib = ctypes.CDLL(name)
                break
            except OSError:
                continue
        if xlib is None:
            raise WindowFinderUnavailable("libX11 not found.")
        self._xlib = xlib
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = (ctypes.c_char_p,)
        xlib.XCloseDisplay.argtypes = (ctypes.c_void_p,)
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xlib.XDefaultRootWindow.argtypes = (ctypes.c_void_p,)
        xlib.XInternAtom.restype = c_ulong
        xlib.XInternAtom.argtypes = (ctypes.c_void_p, ctypes.c_char_p, c_int)
        xlib.XGetWindowProperty.restype = c_int
        xlib.XGetWindowProperty.argtypes = (
            ctypes.c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
            ctypes.POINTER(c_ulong), ctypes.POINTER(c_int), ctypes.POINTER(c_ulong),
            ctypes.POINTER(c_ulong), ctypes.POINTER(ctypes.POINTER(c_ubyte)))
        xlib.XQueryTree.restype = c_int
        xlib.XQueryTree.argtypes = (
            ctypes.c_void_p, c_ulong, ctypes.POINTER(c_ulong), ctypes.POINTER(c_ulong),
            ctypes.POINTER(ctypes.POINTER(c_ulong)), ctypes.POINTER(c_uint))
        xlib.XGetGeometry.restype = c_int
        xlib.XGetGeometry.argtypes = (
            ctypes.c_void_p, c_ulong, ctypes.POINTER(c_ulong), ctypes.POINTER(c_int),
            ctypes.POINTER(c_int), ctypes.POINTER(c_uint), ctypes.POINTER(c_uint),
            ctypes.POINTER(c_uint), ctypes.POINTER(c_uint))
        xlib.XTranslateCoordinates.restype = c_int
        xlib.XTranslateCoordinates.argtypes = (
            ctypes.c_void_p, c_ulong, c_ulong, c_int, c_int,
            ctypes.POINTER(c_int), ctypes.POINTER(c_int), ctypes.POINTER(c_ulong))
        xlib.XSetInputFocus.argtypes = (ctypes.c_void_p, c_ulong, c_int, c_ulong)
        xlib.XRaiseWindow.argtypes = (ctypes.c_void_p, c_ulong)
        xlib.XSync.argtypes = (ctypes.c_void_p, c_int)
        xlib.XFree.argtypes = (ctypes.c_void_p,)
        try:
            xlib.XInitThreads.restype = c_int
            xlib.XInitThreads.argtypes = ()
            xlib.XInitThreads()
        except AttributeError:  # pragma: no cover
            pass
        self._dpy = xlib.XOpenDisplay(None)
        if not self._dpy:
            raise WindowFinderUnavailable("No X display (need X11 session).")
        self._root = int(xlib.XDefaultRootWindow(self._dpy))

    # -- internals --------------------------------------------------------
    def _atom(self, name: str) -> int:
        return int(self._xlib.XInternAtom(self._dpy, name.encode(), False))

    def _prop_bytes(self, window: int, atom: int,
                    prop_type: int = ANY_PROPERTY_TYPE) -> bytes:
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        data = ctypes.POINTER(c_ubyte)()
        status = self._xlib.XGetWindowProperty(
            self._dpy, window, atom, 0, 8192, False, prop_type,
            ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(data))
        if status != 0 or not data:
            return b""
        try:
            if actual_format.value == 8:
                return ctypes.string_at(data, nitems.value)
            if actual_format.value == 16:
                return ctypes.string_at(data, nitems.value * 2)
            return b""
        finally:
            self._xlib.XFree(ctypes.cast(data, ctypes.c_void_p))

    def _title(self, window: int) -> str:
        raw = self._prop_bytes(window, self._atom("_NET_WM_NAME"),
                               self._atom("UTF8_STRING"))
        if raw:
            return raw.split(b"\x00", 1)[0].decode("utf-8", "ignore").strip()
        raw = self._prop_bytes(window, self._atom("WM_NAME"))
        return raw.split(b"\x00", 1)[0].decode("latin-1", "ignore").strip()

    def _pid(self, window: int) -> int:
        values = self._longs(window, self._atom("_NET_WM_PID"), XA_CARDINAL)
        return values[0] if values else 0

    def _longs(self, window: int, atom: int, prop_type: int) -> List[int]:
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        data = ctypes.POINTER(c_ubyte)()
        status = self._xlib.XGetWindowProperty(
            self._dpy, window, atom, 0, 8192, False, prop_type,
            ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(data))
        if status != 0 or not data:
            return []
        try:
            if actual_format.value == 32:
                vals = ctypes.cast(data, ctypes.POINTER(c_ulong))
                return [int(vals[i]) for i in range(nitems.value)]
            return []
        finally:
            self._xlib.XFree(ctypes.cast(data, ctypes.c_void_p))

    def _geometry(self, window: int):
        root = c_ulong()
        x, y = c_int(), c_int()
        w, h, bw, depth = c_uint(), c_uint(), c_uint(), c_uint()
        if self._xlib.XGetGeometry(self._dpy, window, ctypes.byref(root),
                                   ctypes.byref(x), ctypes.byref(y),
                                   ctypes.byref(w), ctypes.byref(h),
                                   ctypes.byref(bw), ctypes.byref(depth)):
            # Geometry is relative to the parent; translate to root coords.
            tx, ty = c_int(), c_int()
            child = c_ulong()
            if self._xlib.XTranslateCoordinates(
                    self._dpy, window, root.value, x.value, y.value,
                    ctypes.byref(tx), ctypes.byref(ty), ctypes.byref(child)):
                return (tx.value, ty.value, int(w.value), int(h.value))
            return (x.value, y.value, int(w.value), int(h.value))
        return None

    def list_windows(self) -> List[WindowHandle]:
        idents = self._longs(self._root, self._atom("_NET_CLIENT_LIST"), XA_WINDOW)
        if not idents:
            root_ret, parent_ret = c_ulong(), c_ulong()
            children = ctypes.POINTER(c_ulong)()
            nchildren = c_uint()
            if self._xlib.XQueryTree(self._dpy, self._root, ctypes.byref(root_ret),
                                     ctypes.byref(parent_ret), ctypes.byref(children),
                                     ctypes.byref(nchildren)):
                try:
                    for i in range(nchildren.value):
                        idents.append(int(children[i]))
                finally:
                    if children:
                        self._xlib.XFree(ctypes.cast(children, ctypes.c_void_p))
        out: List[WindowHandle] = []
        seen: set[int] = set()
        for ident in idents:
            if not ident or ident in seen:
                continue
            seen.add(ident)
            title = self._title(ident)
            if not title:
                continue
            pid = self._pid(ident)
            geom = self._geometry(ident)
            if not geom:
                continue
            process = ""
            if pid:
                try:
                    with open(f"/proc/{pid}/comm", "r", encoding="utf-8",
                              errors="ignore") as fh:
                        process = fh.read().strip()
                except OSError:
                    process = ""
            out.append(WindowHandle(ident, title, process, pid, *geom))
        return out

    def focus(self, ident: int) -> None:
        try:
            self._xlib.XRaiseWindow(self._dpy, ident)
        except Exception:
            pass
        self._xlib.XSetInputFocus(self._dpy, ident, 2, 0)
        self._xlib.XSync(self._dpy, 0)

    def close(self) -> None:
        try:
            if self._dpy:
                self._xlib.XCloseDisplay(self._dpy)
        except Exception:
            pass
        self._dpy = None


_finder: Optional[X11WindowFinder] = None


def _get_finder() -> X11WindowFinder:
    global _finder
    if _finder is None:
        _finder = X11WindowFinder()
    return _finder


def find_window(title_contains: Optional[List[str]] = None,
                process_contains: Optional[List[str]] = None) -> Optional[WindowHandle]:
    """Return the first window whose title/process matches.

    Defaults target Sober: title containing "Sober" or "Roblox", or a process
    named "sober"/"RobloxPlayer".
    """

    if title_contains is None:
        title_contains = ["Sober", "Roblox", "sober"]
    if process_contains is None:
        process_contains = ["sober", "roblox", "RobloxPlayer"]
    finder = _get_finder()
    for win in finder.list_windows():
        title_low = (win.title or "").lower()
        proc_low = (win.process or "").lower()
        if any(t.lower() in title_low for t in title_contains):
            return win
        if any(p.lower() in proc_low for p in process_contains):
            return win
    return None


def focus_window(ident: int) -> None:
    _get_finder().focus(ident)


def list_sober_windows() -> List[WindowHandle]:
    return _get_finder().list_windows()
