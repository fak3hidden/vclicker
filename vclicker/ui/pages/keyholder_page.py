"""Key holder page with per-window targeting."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSpinBox, QVBoxLayout, QWidget

from ... import icons, keys as keymap, theme
from ...core.keyholder import KeyHolderConfig
from ..widgets import (Banner, Card, KeyCapture, Segmented, StatusPill, ToggleRow,
                       WindowPicker, button, divider, icon_button, label, repolish)
from .base import Page


class KeyRow(QWidget):
    removed = Signal(object)

    def __init__(self, hotkeys, key: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.capture = KeyCapture(hotkeys, allow_combo=False, placeholder="Choose a key")
        self.capture.setStyleSheet("text-align: left; padding-left: 13px;")
        self.capture.set_value(key)
        layout.addWidget(self.capture, 1)
        self.remove_button = icon_button("close", "Remove key", theme.DIM, 13)
        self.remove_button.setFixedSize(30, 30)
        self.remove_button.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self.remove_button)

    def key(self) -> str:
        return self.capture.value()


class KeyHolderPage(Page):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(
            "Key Holder",
            "Hold a key down — on the active window or on several windows at once.",
            parent,
        )
        self.ctx = ctx
        self.cfg: KeyHolderConfig = ctx.keyholder_cfg
        self.grid.setColumnStretch(0, 2)
        self.grid.setColumnStretch(1, 3)

        self._build_hold_card()
        self._build_target_card()
        self._build_platform_card()
        self._assemble()
        self._wire()

    # ------------------------------------------------------------------ #
    #  Build
    # ------------------------------------------------------------------ #
    def _build_hold_card(self) -> None:
        card = Card("Hold", "Keys stay pressed until you release them.", "keyboard")

        self.keys_box = QVBoxLayout()
        self.keys_box.setContentsMargins(0, 0, 0, 0)
        self.keys_box.setSpacing(8)
        card.add_layout(self.keys_box)

        self.add_key_button = button("Add another key", "ghost", "plus", theme.TEXT)
        self.add_key_button.setMinimumHeight(32)
        self.add_key_button.clicked.connect(lambda: self._add_key_row(""))
        card.add(self.add_key_button)

        card.add(divider())
        card.add(label("DURATION", "sectionTitle"))
        self.timing = Segmented([
            ("hold", "Until released"),
            ("timed", "Timed"),
        ], self.cfg.timing)
        card.add(self.timing)

        duration_row = QHBoxLayout()
        duration_row.setContentsMargins(0, 0, 0, 0)
        duration_row.setSpacing(8)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)
        self.duration_spin.setValue(max(1, int(self.cfg.duration)))
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setMinimumHeight(34)
        duration_row.addWidget(self.duration_spin, 1)
        self.duration_hint = label("auto-release", "dim")
        duration_row.addWidget(self.duration_hint)
        card.add_layout(duration_row)

        card.add(divider())
        self.repeat_row = ToggleRow(
            "Repeat key presses",
            "Re-sends key-down on a timer for apps that need repeats",
            self.cfg.repeat)
        card.add(self.repeat_row)

        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(10, 5000)
        self.repeat_spin.setVisible(self.cfg.repeat)
        self.repeat_spin.setSingleStep(10)
        self.repeat_spin.setValue(max(10, int(self.cfg.repeat_ms)))
        self.repeat_spin.setSuffix(" ms")
        self.repeat_spin.setMinimumHeight(34)
        card.add(self.repeat_spin)

        self.engage_button = button("Hold key", "hero", "keyboard")
        self.engage_button.setMinimumHeight(52)
        card.add(self.engage_button)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        self.status = StatusPill("Released", "off")
        footer.addWidget(self.status)
        footer.addStretch(1)
        self.hotkey_hint = label("", "dim")
        footer.addWidget(self.hotkey_hint)
        card.add_layout(footer)

        card.add(divider())
        self.summary = Banner("", "info")
        card.add(self.summary)

        self.hold_card = card

    def _build_target_card(self) -> None:
        card = Card("Targets", "Send the held key to one window or many.", "layers")
        self.target_seg = Segmented([
            ("global", "Active window"),
            ("windows", "Selected windows"),
        ], self.cfg.target)
        card.add(self.target_seg)

        self.picker = WindowPicker(self.ctx.backend)
        self.picker.setMinimumHeight(296)
        card.add(self.picker, 1)

        self.target_note = Banner("", "info")
        card.add(self.target_note)
        self.target_card = card

    def _build_platform_card(self) -> None:
        backend = self.ctx.backend
        card = Card("Platform behaviour", "How background key delivery works here.", "shield")
        if backend.caps.targeted_hold:
            text = ("Selected windows receive key messages directly — they keep running in the "
                    "background and never steal your focus. Games that read raw input may "
                    "ignore these messages; use “Active window” mode for those.")
            tone = "ok"
        else:
            text = ("This platform delivers keys by focusing each selected window in turn. "
                    "Expect a brief focus switch when engaging and releasing.")
            tone = "warn"
        card.add(Banner(text, tone))
        for note in backend.caps.notes[:3]:
            card.add(label("• " + note, "dim", wrap=True))
        self.platform_card = card

    def _assemble(self) -> None:
        self.add_pair(self.hold_card, self.target_card, row=0)
        self.add_row(self.platform_card, row=1)

    # ------------------------------------------------------------------ #
    #  Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        ctx = self.ctx
        self._key_rows: list[KeyRow] = []
        for key in (self.cfg.keys or ["space"])[:4]:
            self._add_key_row(key)
        self._refresh_add_button()

        ctx.keyholder.state_changed.connect(self._on_state)
        self.engage_button.clicked.connect(self._toggle)
        self.timing.changed.connect(self._on_timing)
        self.duration_spin.valueChanged.connect(self._on_duration)
        self.repeat_row.toggled.connect(self._on_repeat)
        self.repeat_spin.valueChanged.connect(self._on_repeat_interval)
        self.target_seg.changed.connect(self._on_target_changed)
        self.picker.selection_changed.connect(self._on_selection)

        panic = button("Release all", "ghost", "power", theme.TEXT)
        panic.clicked.connect(self._panic)
        self.add_header_widget(panic)

        # sync remaining widgets
        self.timing.set_value(self.cfg.timing)
        self.duration_spin.setVisible(self.cfg.timing == "timed")
        self.duration_hint.setVisible(self.cfg.timing == "timed")
        self.repeat_row.setChecked(self.cfg.repeat)
        self.repeat_spin.setVisible(self.cfg.repeat)
        self.target_seg.set_value(self.cfg.target)
        self.picker.refresh()
        if self.cfg.windows:
            self.picker.set_selection(self.cfg.windows)
        self._refresh_note()
        self._refresh_hotkey_hint()
        self._refresh_summary()
        self.engage_button.setEnabled(bool(self.cfg.keys))

        self._held_timer = QTimer(self)
        self._held_timer.setInterval(250)
        self._held_timer.timeout.connect(self._refresh_summary)
        self._held_since = 0.0

    # ------------------------------------------------------------------ #
    #  Key rows
    # ------------------------------------------------------------------ #
    def _add_key_row(self, key: str) -> None:
        row = KeyRow(self.ctx.hotkeys, key)
        row.removed.connect(self._remove_key_row)
        row.capture.captured.connect(lambda _value, _row=row: self._on_key_changed())
        self.keys_box.addWidget(row)
        self._key_rows.append(row)
        self._refresh_add_button()
        self._on_key_changed()

    def _remove_key_row(self, row: KeyRow) -> None:
        if len(self._key_rows) <= 1:
            row.capture.set_value("")
            self._on_key_changed()
            return
        self._key_rows.remove(row)
        self.keys_box.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh_add_button()
        self._on_key_changed()

    def _refresh_add_button(self) -> None:
        self.add_key_button.setVisible(len(self._key_rows) < 4)

    def _on_key_changed(self) -> None:
        keys = [r.key() for r in self._key_rows if r.key()]
        self.cfg.keys = keys
        self.ctx.persist_keyholder()
        if self.ctx.keyholder.active:
            self.ctx.keyholder.disengage()
        self.engage_button.setEnabled(bool(keys))
        self._refresh_summary()

    # ------------------------------------------------------------------ #
    #  Handlers
    # ------------------------------------------------------------------ #
    def _on_timing(self, value: str) -> None:
        self.cfg.timing = value
        self.duration_spin.setVisible(value == "timed")
        self.duration_hint.setVisible(value == "timed")
        self.ctx.persist_keyholder()
        self._refresh_summary()

    def _on_duration(self, value: int) -> None:
        self.cfg.duration = float(value)
        self.ctx.persist_keyholder()
        self._refresh_summary()

    def _on_repeat(self, value: bool) -> None:
        self.cfg.repeat = bool(value)
        self.repeat_spin.setVisible(bool(value))
        self.ctx.persist_keyholder()

    def _on_repeat_interval(self, value: int) -> None:
        self.cfg.repeat_ms = float(value)
        self.ctx.persist_keyholder()

    def _on_target_changed(self, value: str) -> None:
        self.cfg.target = value
        if self.ctx.keyholder.active:
            self.ctx.keyholder.disengage()
        self.ctx.persist_keyholder()
        self._refresh_note()
        self._refresh_summary()

    def _on_selection(self) -> None:
        self.cfg.windows = self.picker.selected()
        self.ctx.persist_keyholder(windows=self.cfg.windows)
        self._refresh_note()
        self._refresh_summary()

    def _refresh_note(self) -> None:
        if self.cfg.target == "global":
            self.target_note.set_tone("info")
            self.target_note.set_text(
                "Keys go to whichever window has focus — exactly like physically holding the key. "
                "Switch to “Selected windows” to hold on windows in the background.")
        else:
            count = len(self.picker.selected())
            if count:
                self.target_note.set_tone("ok")
                self.target_note.set_text(
                    f"{count} window{'s' if count != 1 else ''} selected. The key is held on all "
                    "of them at the same time.")
            else:
                self.target_note.set_tone("warn")
                self.target_note.set_text("Pick at least one window below to use this mode.")

    def _refresh_summary(self) -> None:
        if not hasattr(self, "summary"):
            return
        keys = ", ".join(keymap.label(k) for k in self.cfg.keys) or "no key"
        if self.ctx.keyholder.active:
            elapsed = time.perf_counter() - self._held_since
            target = ("active window" if self.cfg.target == "global"
                      else f"{len(self.cfg.windows)} windows")
            self.summary.set_tone("ok")
            self.summary.set_text(
                f"Holding {keys} for {elapsed:0.1f}s on {target} · press "
                f"{keymap.combo_text(self.ctx.hotkeys.bindings.get('toggle_keyhold', 'f9'))} "
                "to release")
            return
        mode = "until released" if self.cfg.timing == "hold" else f"for {int(self.cfg.duration)}s"
        target = ("the active window" if self.cfg.target == "global"
                  else f"{len(self.cfg.windows)} selected window(s)")
        self.summary.set_tone("info")
        self.summary.set_text(f"Will hold {keys} {mode} on {target}.")

    def _toggle(self) -> None:
        if self.ctx.keyholder.active:
            self.ctx.keyholder.disengage()
            return
        self.cfg.windows = self.picker.selected()
        if self.ctx.keyholder.engage(self.cfg):
            self._held_since = time.perf_counter()
            self._held_timer.start()
            keys = ", ".join(keymap.label(k) for k in self.cfg.keys)
            self.ctx.notify.emit(f"Holding {keys}", "ok")

    def _panic(self) -> None:
        self.ctx.keyholder.disengage()
        self.ctx.notify.emit("Keys released", "info")

    def _on_state(self, active: bool) -> None:
        self.status.set_state("live" if active else "off", "Holding" if active else "Released")
        if active:
            if not self._held_since:
                self._held_since = time.perf_counter()
            self._held_timer.start()
        else:
            self._held_timer.stop()
            self._held_since = 0.0
        self._refresh_summary()
        if active:
            self.engage_button.setText("Release keys")
            self.engage_button.setProperty("variant", "danger")
            self.engage_button.setIcon(icons.icon("power", theme.DANGER, 17))
        else:
            self.engage_button.setText("Hold key")
            self.engage_button.setProperty("variant", "hero")
            self.engage_button.setIcon(icons.icon("keyboard", theme.ON_ACCENT, 17))
        repolish(self.engage_button)
        self.engage_button.setMinimumHeight(52)

    def _refresh_hotkey_hint(self) -> None:
        combo = self.ctx.hotkeys.bindings.get("toggle_keyhold", "f9")
        self.hotkey_hint.setText(f"Hotkey · {keymap.combo_text(combo)}")
