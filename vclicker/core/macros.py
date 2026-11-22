"""Macro model + on-disk storage."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from ..paths import macros_dir

FORMAT = "vclicker.macro"
VERSION = 1


@dataclass
class MacroEvent:
    t: float = 0.0
    kind: str = "move"       # move | down | up | wheel | key_down | key_up
    key: str | None = None
    button: str | None = None
    x: int = 0
    y: int = 0
    delta: int = 0

    def to_dict(self) -> dict:
        data: dict = {"t": round(self.t, 5), "e": self.kind}
        if self.kind in ("move", "down", "up", "wheel"):
            data["x"] = self.x
            data["y"] = self.y
        if self.button:
            data["b"] = self.button
        if self.key:
            data["k"] = self.key
        if self.delta:
            data["d"] = self.delta
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "MacroEvent":
        return cls(
            t=float(data.get("t", 0.0)),
            kind=str(data.get("e", "move")),
            key=data.get("k"),
            button=data.get("b"),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            delta=int(data.get("d", 0)),
        )


@dataclass
class Macro:
    name: str = "Untitled macro"
    events: list[MacroEvent] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    duration: float = 0.0
    path: str | None = None

    # -- derived data ------------------------------------------------------ #
    @property
    def clicks(self) -> int:
        return sum(1 for e in self.events if e.kind == "down")

    @property
    def key_events(self) -> int:
        return sum(1 for e in self.events if e.kind in ("key_down", "key_up"))

    @property
    def moves(self) -> int:
        return sum(1 for e in self.events if e.kind == "move")

    def duration_text(self) -> str:
        total = self.duration or (self.events[-1].t if self.events else 0.0)
        if total >= 60:
            minutes = int(total // 60)
            seconds = total - minutes * 60
            return f"{minutes}m {seconds:04.1f}s"
        return f"{total:.1f}s"

    # -- serialisation ----------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "format": FORMAT,
            "version": VERSION,
            "name": self.name,
            "created": self.created,
            "duration": round(self.duration or (self.events[-1].t if self.events else 0.0), 4),
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Macro":
        events = [MacroEvent.from_dict(item) for item in data.get("events", [])]
        return cls(
            name=str(data.get("name") or "Untitled macro"),
            events=events,
            created=str(data.get("created") or datetime.now().isoformat(timespec="seconds")),
            duration=float(data.get("duration") or (events[-1].t if events else 0.0)),
        )


class MacroStore:
    def __init__(self, directory: str | None = None) -> None:
        self.directory = directory or macros_dir()
        os.makedirs(self.directory, exist_ok=True)

    # -- reading ----------------------------------------------------------- #
    def list(self) -> list[Macro]:
        macros: list[Macro] = []
        try:
            names = os.listdir(self.directory)
        except OSError:
            return macros
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                macro = Macro.from_dict(data)
                macro.path = path
                macros.append(macro)
            except (OSError, ValueError, TypeError):
                continue
        macros.sort(key=lambda m: m.created, reverse=True)
        return macros

    def load(self, path: str) -> Macro:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        macro = Macro.from_dict(data)
        macro.path = path
        return macro

    # -- writing ----------------------------------------------------------- #
    def unique_name(self, base: str) -> str:
        base = base.strip() or "Macro"
        existing = {m.name for m in self.list()}
        if base not in existing:
            return base
        index = 2
        while f"{base} ({index})" in existing:
            index += 1
        return f"{base} ({index})"

    def save(self, macro: Macro) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", macro.name).strip("-") or "macro"
        path = macro.path
        if not path:
            candidate = os.path.join(self.directory, f"{slug}.json")
            counter = 2
            while os.path.exists(candidate):
                candidate = os.path.join(self.directory, f"{slug}-{counter}.json")
                counter += 1
            path = candidate
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(macro.to_dict(), fh, indent=1)
        os.replace(tmp, path)
        macro.path = path
        return path

    def delete(self, macro: Macro) -> None:
        if macro.path and os.path.exists(macro.path):
            try:
                os.remove(macro.path)
            except OSError:
                pass

    def rename(self, macro: Macro, new_name: str) -> None:
        macro.name = new_name.strip() or macro.name
        if macro.path:
            # keep the file name stable, just update the stored label
            self.save(macro)

    def export(self, macro: Macro, target: str) -> None:
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(macro.to_dict(), fh, indent=1)

    def import_file(self, source: str) -> Macro:
        macro = self.load(source)
        macro.name = self.unique_name(macro.name)
        macro.path = None
        self.save(macro)
        return macro

    def stats(self) -> tuple[int, float]:
        macros = self.list()
        total = sum(len(m.events) for m in macros)
        seconds = sum(m.duration for m in macros)
        return (total, seconds)


def new_default_name() -> str:
    return time.strftime("Macro %Y-%m-%d %H.%M.%S")
