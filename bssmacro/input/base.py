"""Input controller abstraction.

The macro never talks to X11 / Win32 directly — it speaks to an
:class:`InputController`. That keeps the engine fully testable: in tests we hand
it a :class:`FakeInput` and assert on the recorded action stream.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class InputController(Protocol):
    """Anything that can move the mouse / press keys in the game window."""

    def move(self, x: int, y: int) -> None: ...

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None, count: int = 1) -> None: ...

    def down(self, button: str = "left") -> None: ...

    def up(self, button: str = "left") -> None: ...

    def key_down(self, key: str) -> None: ...

    def key_up(self, key: str) -> None: ...

    def tap(self, key: str, delay: float = 0.02) -> None: ...

    def scroll(self, delta: int) -> None: ...

    def is_key_down(self, key: str) -> bool: ...

    def close(self) -> None: ...


class FakeInput:
    """Records every action instead of performing it.

    Used by the engine's headless self-tests. ``key_states`` mirrors the held
    keys so :meth:`is_key_down` behaves like the real thing.
    """

    def __init__(self) -> None:
        self.actions: list[tuple[str, dict]] = []
        self.key_states: set[str] = set()
        self.button_states: set[str] = set()

    # -- mouse ------------------------------------------------------------
    def move(self, x: int, y: int) -> None:
        self.actions.append(("move", {"x": x, "y": y}))

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None, count: int = 1) -> None:
        for _ in range(max(1, count)):
            self.actions.append(("click", {"button": button, "x": x, "y": y}))

    def down(self, button: str = "left") -> None:
        self.button_states.add(button)
        self.actions.append(("down", {"button": button}))

    def up(self, button: str = "left") -> None:
        self.button_states.discard(button)
        self.actions.append(("up", {"button": button}))

    # -- keyboard ---------------------------------------------------------
    def key_down(self, key: str) -> None:
        self.key_states.add(key)
        self.actions.append(("key_down", {"key": key}))

    def key_up(self, key: str) -> None:
        self.key_states.discard(key)
        self.actions.append(("key_up", {"key": key}))

    def tap(self, key: str, delay: float = 0.02) -> None:
        self.key_down(key)
        self.key_up(key)

    def scroll(self, delta: int) -> None:
        self.actions.append(("scroll", {"delta": delta}))

    def is_key_down(self, key: str) -> bool:
        return key in self.key_states

    def close(self) -> None:
        self.actions.append(("close", {}))

    # -- helpers for assertions ------------------------------------------
    def last(self) -> Optional[tuple[str, dict]]:
        return self.actions[-1] if self.actions else None

    def count(self, kind: str) -> int:
        return sum(1 for a in self.actions if a[0] == kind)
