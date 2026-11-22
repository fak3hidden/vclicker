"""Global hotkey configuration page."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ... import icons, keys as keymap, theme
from ...core.hotkeys import ACTION_LABELS, DEFAULT_BINDINGS
from ..widgets import (Banner, Card, KeyCapture, StatusPill, ToggleRow, button,
                       divider, icon_badge, label)
from .base import Page

ACTION_ICONS = {
    "toggle_clicker": "cursor",
    "toggle_keyhold": "keyboard",
    "record_macro": "record",
    "play_macro": "play",
    "panic": "alert",
}


class HotkeyRow(QWidget):
    def __init__(self, action: str, hotkeys, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action = action
        title, description = ACTION_LABELS.get(action, (action, ""))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        name, _hover, _press, soft, _l = theme.accent_tuple(_accent())
        layout.addWidget(icon_badge(ACTION_ICONS.get(action, "command"), name, soft, 32, 16))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(label(title, "muted"))
        text_col.addWidget(label(description, "dim", wrap=True))
        layout.addLayout(text_col, 1)

        self.capture = KeyCapture(hotkeys, allow_combo=True, placeholder="Not set")
        self.capture.setMinimumWidth(148)
        self.capture.setMaximumWidth(210)
        layout.addWidget(self.capture)

        self.reset_button = button("", "icon")
        self.reset_button.setIcon(icons.icon("refresh", theme.DIM, 15))
        self.reset_button.setToolTip("Reset to default")
        self.reset_button.setFixedSize(32, 32)
        self.reset_button.clicked.connect(self._reset)
        layout.addWidget(self.reset_button)

    def _reset(self) -> None:
        self.capture.set_value(DEFAULT_BINDINGS.get(self.action, ""))
        self.capture.captured.emit(self.capture.value())


def _accent() -> str:
    from ... import theme as theme_module
    return getattr(theme_module, "CURRENT_ACCENT", "indigo")


class HotkeysPage(Page):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(
            "Hotkeys",
            "Control everything without leaving the game — hotkeys work while VClicker is in the background.",
            parent,
        )
        self.ctx = ctx
        self.grid.setColumnStretch(0, 3)
        self.grid.setColumnStretch(1, 2)
        self.rows: dict[str, HotkeyRow] = {}

        self._build_main_card()
        self._build_safety_card()
        self._build_status_card()
        self._wire()

    # ------------------------------------------------------------------ #
    def _build_main_card(self) -> None:
        card = Card("Global hotkeys", "Click a binding, then press the key combo you want.", "command")
        self.enabled_row = ToggleRow("Enable global hotkeys", "Turn every binding on or off at once",
                                     bool(self.ctx.config.get("hotkeys_enabled", True)))
        card.add(self.enabled_row)
        card.add(divider())

        for action in DEFAULT_BINDINGS:
            row = HotkeyRow(action, self.ctx.hotkeys)
            row.capture.set_value(self.ctx.hotkeys.bindings.get(action, ""))
            row.capture.captured.connect(lambda combo, a=action: self._on_captured(a, combo))
            self.rows[action] = row
            card.add(row)
            if action != list(DEFAULT_BINDINGS)[-1]:
                card.add(divider())

        self.main_card = card
        self.add_grid_widget(card, 0, 0)

    def _build_safety_card(self) -> None:
        card = Card("Panic button", "One key stops every action and releases every key.", "shield")
        panic_combo = keymap.combo_text(self.ctx.hotkeys.bindings.get("panic", "f12"))
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip = label(panic_combo, "key")
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        chip_row.addWidget(chip)
        chip_row.addStretch(1)
        card.add_layout(chip_row)
        card.add(label(
            "Use it if a key ever feels stuck or an action will not stop. It always works, "
            "even when other hotkeys are disabled.", "dim", wrap=True))
        self.release_button = button("Release everything now", "danger", "power", theme.DANGER)
        self.release_button.setMinimumHeight(40)
        card.add(self.release_button)
        card.add(Banner(
            "Bindings are global: they fire even when another window has focus. Games that "
            "capture raw input may swallow them.", "info"))
        card.add(divider())
        card.add(label("CHOOSING KEYS", "sectionTitle"))
        for tip in (
            "Use keys your game does not already bind — F-keys and single letters clash most.",
            "Ctrl / Shift / Alt combinations are the safest choice.",
            "Changes apply instantly and are saved automatically.",
        ):
            card.add(label("• " + tip, "dim", wrap=True))
        self.safety_card = card
        self.add_grid_widget(card, 0, 1)

    def _build_status_card(self) -> None:
        backend = self.ctx.backend
        card = Card("Capture status", "Where hotkey events come from.", "eye")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.monitor_pill = StatusPill(
            "Active" if self.ctx.monitor.running else "Inactive",
            "live" if self.ctx.monitor.running else "bad")
        row.addWidget(self.monitor_pill)
        row.addStretch(1)
        row.addWidget(label(backend.name, "dim"))
        card.add_layout(row)
        if backend.caps.recording_quality:
            card.add(label(f"Capture method · {backend.caps.recording_quality}", "dim", wrap=True))
        card.add(Banner(
            "If a hotkey does nothing, another app may already own that combo. Pick a different "
            "key above — changes apply instantly.", "info"))
        self.status_card = card
        self.add_row(card, row=1)

    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        self.enabled_row.toggled.connect(self._on_enabled)
        self.release_button.clicked.connect(self.ctx.panic)

    def _on_enabled(self, value: bool) -> None:
        self.ctx.hotkeys.enabled = bool(value)
        self.ctx.config.set("hotkeys_enabled", bool(value))
        self.ctx.notify.emit("Hotkeys enabled" if value else "Hotkeys disabled", "info")

    def _on_captured(self, action: str, combo: str) -> None:
        if not combo:
            return
        for other, existing in list(self.ctx.hotkeys.bindings.items()):
            if other != action and existing == combo:
                self.ctx.hotkeys.bindings[other] = ""
                if other in self.rows:
                    self.rows[other].capture.set_value("")
                self.ctx.notify.emit(
                    f"{keymap.combo_text(combo)} was reassigned from "
                    f"{ACTION_LABELS[other][0].lower()}", "warn")
        self.ctx.hotkeys.bindings[action] = combo
        self.ctx.config.set("hotkeys", dict(self.ctx.hotkeys.bindings))
        self.ctx.bindings_changed.emit()
        self.ctx.notify.emit(f"{ACTION_LABELS[action][0]} → {keymap.combo_text(combo)}", "ok")
