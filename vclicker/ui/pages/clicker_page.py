"""Auto clicker page."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget

from ... import icons, keys as keymap, theme
from ...core.clicker import ClickerConfig
from ..widgets import (Banner, Card, CpsGraph, Segmented, SliderRow, StatTile,
                       StatusPill, ToggleRow, button, divider, label)
from .base import Page


class ClickerPage(Page):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(
            "Auto Clicker",
            "Native clicks with a zero-delay mode, live speed meter and full hotkey control.",
            parent,
        )
        self.ctx = ctx
        self.cfg: ClickerConfig = ctx.clicker_cfg
        self._limit_guard = False

        self._build_engine_card()
        self._build_timing_card()
        self._build_click_card()
        self._build_position_card()
        self._build_backend_card()
        self.add_pair(self.timing_card, self.click_card, row=1)
        self.add_pair(self.position_card, self.backend_card, row=2)
        self._wire()
        self._sync_widgets()

    # ------------------------------------------------------------------ #
    #  Engine card
    # ------------------------------------------------------------------ #
    def _build_engine_card(self) -> None:
        card = Card("Click engine", "Press start or use the hotkey — it begins instantly.", "zap")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self.start_button = button("Start clicking", "hero", "play")
        self.start_button.setMinimumHeight(60)
        self.start_button.setMinimumWidth(196)
        top.addWidget(self.start_button)

        self.tile_speed = StatTile("Live speed", "0", "CPS", "zap")
        self.tile_total = StatTile("Clicks", "0", "", "cursor")
        self.tile_peak = StatTile("Peak", "0", "CPS", "target")
        for tile in (self.tile_speed, self.tile_total, self.tile_peak):
            top.addWidget(tile, 1)
        card.add_layout(top)

        self.graph = CpsGraph()
        self.graph.setMinimumHeight(92)
        card.add(self.graph, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self.status = StatusPill("Idle", "off")
        footer.addWidget(self.status)
        self.hotkey_hint = label("", "dim")
        footer.addWidget(self.hotkey_hint)
        footer.addStretch(1)
        self.runtime_hint = label("", "dim")
        footer.addWidget(self.runtime_hint)
        card.add_layout(footer)

        self.add_row(card)

    # ------------------------------------------------------------------ #
    #  Timing card
    # ------------------------------------------------------------------ #
    def _build_timing_card(self) -> None:
        card = Card("Timing", "Choose how fast the engine fires.", "clock")
        self.mode = Segmented([
            ("cps", "Clicks / sec"),
            ("interval", "Interval"),
            ("instant", "Instant"),
        ], self.cfg.mode)
        card.add(self.mode)

        self.cps_row = SliderRow("Clicks per second", 1, 1000, self.cfg.cps, " CPS", 0, 1,
                                 log=True)
        card.add(self.cps_row)

        self.ms_row = SliderRow("Delay between clicks", 1, 1000, self.cfg.ms, " ms", 0, 1,
                                log=True)
        card.add(self.ms_row)

        self.jitter_row = SliderRow("Human-like jitter", 0, 50, self.cfg.jitter * 100, " %", 0, 1,
                                    tooltip="Randomises the delay by ± this amount")
        card.add(self.jitter_row)

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        preset_row.addWidget(label("PRESETS", "sectionTitle"))
        preset_row.addStretch(1)
        self.preset_buttons = {}
        for preset_name, cps, instant in (("Chill · 10", 10, False), ("Normal · 40", 40, False),
                                          ("Fast · 150", 150, False), ("Max", 0, True)):
            chip = QPushButton(preset_name)
            chip.setProperty("variant", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet("padding: 5px 10px; font-size: 11.5px;")
            chip.clicked.connect(lambda _c=False, v=cps, i=instant: self._apply_preset(v, i))
            self.preset_buttons[preset_name] = chip
            preset_row.addWidget(chip)
        card.add_layout(preset_row)

        self.instant_banner = Banner(
            "Instant mode sends clicks with no delay at all. Expect a fully used CPU core "
            "and a lot of clicks per second.", "warn")
        self.instant_banner.hide()
        card.add(self.instant_banner)

        self.timing_card = card

    # ------------------------------------------------------------------ #
    #  Click card
    # ------------------------------------------------------------------ #
    def _build_click_card(self) -> None:
        card = Card("Click", "What each action sends.", "mouse")
        self.button_seg = Segmented([
            ("left", "Left"),
            ("right", "Right"),
            ("middle", "Middle"),
        ], self.cfg.button)
        card.add(self.button_seg)

        self.double_row = ToggleRow("Double click", "Two clicks per action", self.cfg.double)
        card.add(self.double_row)

        self.burst_row = SliderRow(
            "Turbo burst", 1, 64, self.cfg.burst, "×", 0, 1,
            tooltip="Clicks packed into a single native input call")
        card.add(self.burst_row)
        card.add(label("Packs several clicks into one native call — highest sustained rate.",
                       "dim", wrap=True))
        card.add(divider())

        card.add(label("STOP AFTER", "sectionTitle"))
        self.limit_seg = Segmented([
            ("none", "Never"),
            ("clicks", "Clicks"),
            ("seconds", "Seconds"),
        ], "none")
        card.add(self.limit_seg)

        limit_row = QHBoxLayout()
        limit_row.setContentsMargins(0, 0, 0, 0)
        limit_row.setSpacing(8)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000000)
        self.limit_spin.setValue(100)
        self.limit_spin.setMinimumHeight(34)
        limit_row.addWidget(self.limit_spin, 1)
        self.limit_suffix = label("clicks", "dim")
        limit_row.addWidget(self.limit_suffix)
        card.add_layout(limit_row)

        self.click_card = card

    # ------------------------------------------------------------------ #
    #  Position card
    # ------------------------------------------------------------------ #
    def _build_position_card(self) -> None:
        card = Card("Position", "Click wherever the cursor is, or lock a point.", "target")
        self.pos_seg = Segmented([
            ("cursor", "Follow cursor"),
            ("fixed", "Fixed point"),
        ], self.cfg.position)
        card.add(self.pos_seg)

        coords = QHBoxLayout()
        coords.setContentsMargins(0, 0, 0, 0)
        coords.setSpacing(8)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-100000, 100000)
        self.x_spin.setPrefix("X  ")
        self.x_spin.setValue(self.cfg.x)
        self.x_spin.setMinimumHeight(34)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-100000, 100000)
        self.y_spin.setPrefix("Y  ")
        self.y_spin.setValue(self.cfg.y)
        self.y_spin.setMinimumHeight(34)
        self.pick_button = button("Pick in 3s", "ghost", "target", theme.TEXT)
        self.pick_button.setMinimumHeight(34)
        coords.addWidget(self.x_spin, 1)
        coords.addWidget(self.y_spin, 1)
        coords.addWidget(self.pick_button)
        card.add_layout(coords)

        self.pos_hint = label("", "dim", wrap=True)
        card.add(self.pos_hint)

        self.position_card = card

    # ------------------------------------------------------------------ #
    #  Backend card
    # ------------------------------------------------------------------ #
    def _build_backend_card(self) -> None:
        backend = self.ctx.backend
        card = Card("Input backend", "How clicks and keys reach your operating system.",
                    "shield")
        caps = backend.caps

        rows = QWidget()
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(8)

        def info_line(title: str, value: str) -> None:
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.addWidget(label(title, "dim"))
            line.addStretch(1)
            line.addWidget(label(value, "muted"))
            rows_layout.addLayout(line)

        info_line("Platform", backend.os_name.title())
        info_line("Click capture", caps.recording_quality or "—")
        info_line("Background key hold", "Supported" if caps.targeted_hold else "Focus based")
        card.add(rows)

        notes = " · ".join(caps.notes) if caps.notes else ""
        if not caps.clicking:
            notes = "No input backend — clicks cannot be sent. " + notes
        self.backend_banner = Banner(notes or "Native input layer ready.", "ok" if caps.clicking else "bad")
        card.add(self.backend_banner)
        self.backend_card = card

    # ------------------------------------------------------------------ #
    #  Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        ctx = self.ctx

        # engine
        self.start_button.clicked.connect(self._toggle)
        ctx.clicker.state_changed.connect(self._on_state)
        ctx.clicker.stats.connect(self._on_stats)

        # timing
        self.mode.changed.connect(self._on_mode)
        self.cps_row.value_changed.connect(lambda v: self._set("cps", v))
        self.ms_row.value_changed.connect(lambda v: self._set("ms", v))
        self.burst_row.value_changed.connect(lambda v: self._set("burst", int(v)))
        self.jitter_row.value_changed.connect(lambda v: self._set("jitter", v / 100.0))

        # click
        self.button_seg.changed.connect(lambda v: self._set("button", v))
        self.double_row.toggled.connect(lambda v: self._set("double", bool(v)))
        self.limit_seg.changed.connect(self._on_limit_mode)
        self.limit_spin.valueChanged.connect(self._on_limit_value)

        # position
        self.pos_seg.changed.connect(self._on_position_mode)
        self.x_spin.valueChanged.connect(lambda v: self._set("x", int(v)))
        self.y_spin.valueChanged.connect(lambda v: self._set("y", int(v)))
        self.pick_button.clicked.connect(self._start_pick)

        self._pick_timer = QTimer(self)
        self._pick_timer.setInterval(1000)
        self._pick_timer.timeout.connect(self._tick_pick)
        self._pick_countdown = 0

        self._refresh_hotkey_hint()
        self._refresh_position_hint()

    def _set(self, field: str, value) -> None:
        setattr(self.cfg, field, value)
        self.ctx.persist_clicker()
        self.ctx.apply_clicker_config()

    # ------------------------------------------------------------------ #
    #  Handlers
    # ------------------------------------------------------------------ #
    def _toggle(self) -> None:
        if self.ctx.clicker.running:
            self.ctx.clicker.stop("Stopped")
        else:
            if self.ctx.clicker.start(self.cfg):
                self.ctx.notify.emit("Auto clicker started", "ok")

    def _on_state(self, running: bool) -> None:
        if running:
            self.start_button.setText("Stop clicking")
            self.start_button.setIcon(icons.icon("stop", theme.DANGER, 17))
            self.start_button.setProperty("variant", "danger")
            self.status.set_state("live", "Running")
            self.graph.reset()
        else:
            self.start_button.setText("Start clicking")
            self.start_button.setIcon(icons.icon("play", theme.ON_ACCENT, 17))
            self.start_button.setProperty("variant", "hero")
            self.status.set_state("off", "Idle")
        from ..widgets import repolish
        repolish(self.start_button)
        self.start_button.setMinimumHeight(60)

    def _on_stats(self, cps: float, total: int, peak: float) -> None:
        self.tile_speed.set_value(f"{cps:,.0f}")
        self.tile_total.set_value(f"{total:,}")
        self.tile_peak.set_value(f"{peak:,.0f}")
        if self.ctx.clicker.running:
            self.graph.push(cps)
        self.runtime_hint.setText(f"Last run: {total:,} clicks" if total else "")

    def _apply_preset(self, cps: float, instant: bool) -> None:
        if instant:
            self.mode.set_value("instant", emit=True)
        else:
            self.mode.set_value("cps", emit=True)
            self.cps_row.set_value(cps)
        self.ctx.notify.emit(
            "Instant mode armed — every click fires immediately" if instant
            else f"Preset applied · {int(cps)} CPS", "ok")

    def _on_mode(self, mode: str) -> None:
        self._set("mode", mode)
        self._sync_mode_visibility()

    def _sync_mode_visibility(self) -> None:
        mode = self.cfg.mode
        self.cps_row.setVisible(mode == "cps")
        self.ms_row.setVisible(mode == "interval")
        self.instant_banner.setVisible(mode == "instant")
        if mode == "instant":
            self.runtime_hint.setText("Zero delay — maximum throughput")
        elif mode == "interval":
            self.runtime_hint.setText(f"{self.cfg.ms:.0f} ms between clicks")
        else:
            self.runtime_hint.setText(f"{self.cfg.cps:.0f} clicks per second")

    def _apply_limit(self) -> None:
        if self._limit_guard:
            return
        self._limit_guard = True
        try:
            mode = self.limit_seg.value()
            value = int(self.limit_spin.value())
            self.cfg.limit_mode = mode
            self.cfg.limit_clicks = value if mode == "clicks" else 0
            self.cfg.limit_seconds = float(value) if mode == "seconds" else 0.0
            self.ctx.persist_clicker()
            self.ctx.apply_clicker_config()
        finally:
            self._limit_guard = False

    def _on_limit_mode(self, mode: str) -> None:
        self._limit_guard = True
        try:
            if mode == "clicks":
                self.limit_spin.setRange(1, 1000000)
                self.limit_spin.setValue(int(self.cfg.limit_clicks) or 100)
                self.limit_suffix.setText("clicks")
            elif mode == "seconds":
                self.limit_spin.setRange(1, 86400)
                self.limit_spin.setValue(int(self.cfg.limit_seconds) or 10)
                self.limit_suffix.setText("seconds")
        finally:
            self._limit_guard = False
        self.limit_spin.setVisible(mode != "none")
        self.limit_suffix.setVisible(mode != "none")
        self._apply_limit()

    def _on_limit_value(self, _value: int) -> None:
        self._apply_limit()

    def _on_position_mode(self, mode: str) -> None:
        self._set("position", mode)
        fixed = mode == "fixed"
        for widget in (self.x_spin, self.y_spin, self.pick_button):
            widget.setEnabled(fixed)
        self._refresh_position_hint()

    def _refresh_position_hint(self) -> None:
        if self.cfg.position == "fixed":
            self.pos_hint.setText(
                f"Every click is sent to ({self.cfg.x}, {self.cfg.y}). Move the mouse freely — "
                "the engine puts the cursor back for each click.")
        else:
            self.pos_hint.setText("Clicks land wherever the cursor is at that moment.")

    def _start_pick(self) -> None:
        self._pick_countdown = 3
        self.pick_button.setText(f"Pick in {self._pick_countdown}…")
        self.pick_button.setEnabled(False)
        self._pick_timer.start()

    def _tick_pick(self) -> None:
        self._pick_countdown -= 1
        if self._pick_countdown > 0:
            self.pick_button.setText(f"Pick in {self._pick_countdown}…")
            return
        self._pick_timer.stop()
        pos = QCursor.pos()
        self.x_spin.setValue(pos.x())
        self.y_spin.setValue(pos.y())
        self.pick_button.setText("Pick in 3s")
        self.pick_button.setEnabled(True)
        self.ctx.notify.emit(f"Fixed point set to {pos.x()}, {pos.y()}", "ok")

    # ------------------------------------------------------------------ #
    #  Initial sync
    # ------------------------------------------------------------------ #
    def _refresh_hotkey_hint(self) -> None:
        combo = self.ctx.hotkeys.bindings.get("toggle_clicker", "f8")
        self.hotkey_hint.setText(f"Hotkey · {keymap.combo_text(combo)}")

    def _sync_widgets(self) -> None:
        cfg = self.cfg
        self._limit_guard = True
        self.mode.set_value(cfg.mode)
        self.cps_row.set_value(cfg.cps, emit=False)
        self.ms_row.set_value(cfg.ms, emit=False)
        self.burst_row.set_value(max(1, cfg.burst), emit=False)
        self.jitter_row.set_value(cfg.jitter * 100, emit=False)
        self.button_seg.set_value(cfg.button)
        self.double_row.setChecked(cfg.double)
        self.pos_seg.set_value(cfg.position)

        mode = cfg.limit_mode if cfg.limit_mode in ("none", "clicks", "seconds") else "none"
        if mode == "none":                       # tolerate older configs
            mode = "clicks" if cfg.limit_clicks else ("seconds" if cfg.limit_seconds else "none")
        if mode == "clicks":
            self.limit_seg.set_value("clicks")
            self.limit_spin.setRange(1, 1000000)
            self.limit_spin.setValue(int(cfg.limit_clicks) or 100)
            self.limit_suffix.setText("clicks")
        elif mode == "seconds":
            self.limit_seg.set_value("seconds")
            self.limit_spin.setRange(1, 86400)
            self.limit_spin.setValue(int(cfg.limit_seconds) or 10)
            self.limit_suffix.setText("seconds")
        else:
            self.limit_seg.set_value("none")
        self._limit_guard = False
        self._on_limit_mode(self.limit_seg.value())

        fixed = cfg.position == "fixed"
        for widget in (self.x_spin, self.y_spin, self.pick_button):
            widget.setEnabled(fixed)
        self._sync_mode_visibility()
        self._refresh_position_hint()
        self._refresh_hotkey_hint()
