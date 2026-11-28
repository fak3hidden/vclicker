"""Discord webhook progress reporting.

Mirrors what Natro / Revolution macros send: a clean embed with uptime, pollen /
honey, tokens-per-minute, the active mode and a live screenshot. ``requests`` is
imported lazily so the rest of the package works without network access (and so
the tests never touch the network).
"""

from __future__ import annotations

import base64
import io
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..types import Stats


@dataclass
class WebhookConfig:
    url: str = ""                       # leave empty to disable
    username: str = "BSS Linux Macro"
    avatar_url: str = ""
    interval_sec: float = 60.0          # periodic heartbeat
    send_screenshot: bool = True
    color: int = 0x1ABC9C               # embed accent (teal)
    on_events: list[str] = field(
        default_factory=lambda: ["start", "stop", "windy", "stinger",
                                 "convert", "error"])
    max_event_sec: float = 0.0          # 0 = never throttle event pings

    def enabled(self) -> bool:
        return bool(self.url)

    def to_dict(self) -> dict:
        return {
            "url": self.url, "username": self.username,
            "avatar_url": self.avatar_url, "interval_sec": self.interval_sec,
            "send_screenshot": self.send_screenshot, "color": self.color,
            "on_events": list(self.on_events), "max_event_sec": self.max_event_sec,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WebhookConfig":
        return cls(
            url=str(d.get("url", "")),
            username=str(d.get("username", "BSS Linux Macro")),
            avatar_url=str(d.get("avatar_url", "")),
            interval_sec=float(d.get("interval_sec", 60.0)),
            send_screenshot=bool(d.get("send_screenshot", True)),
            color=int(d.get("color", 0x1ABC9C)),
            on_events=list(d.get("on_events", ["start", "stop", "windy",
                                               "stinger", "convert", "error"])),
            max_event_sec=float(d.get("max_event_sec", 0.0)),
        )


def _frame_to_png(frame) -> Optional[bytes]:
    import cv2

    try:
        import PIL  # noqa: F401
    except Exception:
        PIL = None
    bgr = frame.bgr
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        return None
    return buf.tobytes()


class DiscordWebhook:
    """Sends embeds + optional screenshots to a Discord channel webhook."""

    def __init__(self, cfg: WebhookConfig) -> None:
        self.cfg = cfg
        self._last_heartbeat = 0.0
        self._last_event_sent: dict[str, float] = {}

    # -- public API -------------------------------------------------------
    def maybe_heartbeat(self, stats: Stats, frame=None, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if not self.cfg.enabled():
            return False
        if now - self._last_heartbeat < self.cfg.interval_sec:
            return False
        self._last_heartbeat = now
        return self.send(stats, frame, title="Macro heartbeat", color=self.cfg.color)

    def notify_event(self, event: str, stats: Stats, frame=None,
                     now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if not self.cfg.enabled() or event not in self.cfg.on_events:
            return False
        last = self._last_event_sent.get(event, 0.0)
        if self.cfg.max_event_sec and (now - last) < self.cfg.max_event_sec:
            return False
        self._last_event_sent[event] = now
        return self.send(stats, frame, title=f"Event: {event}", color=0xF1C40F)

    def send(self, stats: Stats, frame=None, title: str = "BSS Macro",
             color: int | None = None, description: str = "") -> bool:
        if not self.cfg.enabled():
            return False
        payload = self._build_payload(stats, title, color or self.cfg.color,
                                      description)
        files = None
        if frame is not None and self.cfg.send_screenshot:
            png = _frame_to_png(frame)
            if png:
                files = {"file": ("bss.png", png, "image/png")}
        try:
            return self._post(payload, files)
        except Exception:
            stats.errors += 1
            return False

    # -- payload building -------------------------------------------------
    def _build_payload(self, stats: Stats, title: str, color: int,
                       description: str) -> dict:
        elapsed = stats.elapsed()
        mins = elapsed / 60.0
        top = sorted(stats.collected.items(), key=lambda kv: kv[1], reverse=True)[:8]
        lines = "\n".join(f"{k}: {v}" for k, v in top) or "—"
        total = sum(stats.collected.values())
        fields = [
            {"name": "Uptime", "value": _fmt_duration(elapsed), "inline": True},
            {"name": "Mode", "value": getattr(stats, "mode", "field") or "field",
             "inline": True},
            {"name": "Clicks", "value": str(stats.clicks), "inline": True},
            {"name": "Tokens/min", "value": f"{stats.per_minute(total):.1f}",
             "inline": True},
            {"name": "Conversions", "value": str(stats.conversions), "inline": True},
            {"name": "Windy / Stingers", "value": f"{stats.windy_events} / {stats.stinger_drops}",
             "inline": True},
            {"name": "Collected", "value": f"```{lines}```", "inline": False},
        ]
        if stats.last_event:
            fields.append({"name": "Last event", "value": stats.last_event,
                           "inline": False})
        embed = {
            "title": title,
            "color": color,
            "fields": fields,
            "timestamp": _iso_now(),
        }
        if description:
            embed["description"] = description
        payload: dict = {"embeds": [embed]}
        if self.cfg.username:
            payload["username"] = self.cfg.username
        if self.cfg.avatar_url:
            payload["avatar_url"] = self.cfg.avatar_url
        return payload

    # -- transport --------------------------------------------------------
    def _post(self, payload: dict, files) -> bool:
        import requests

        if files is None:
            resp = requests.post(self.cfg.url, json=payload, timeout=10)
        else:
            import requests as _r

            resp = _r.post(self.cfg.url, data={"payload_json": _json(payload)},
                           files=files, timeout=10)
        return 200 <= resp.status_code < 300


def _json(d: dict) -> str:
    import json

    return json.dumps(d)


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"
