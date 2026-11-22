"""Macro recorder, library and playback page."""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QSpinBox,
                               QVBoxLayout, QWidget)

from ... import icons, keys as keymap, theme
from ...core.macros import Macro, MacroStore
from ...paths import macros_dir
from ..widgets import (Card, EmptyState, MacroTimeline, SliderRow, StatusPill, StatTile,
                       ToggleRow, button, divider, icon_button, label, repolish)
from .base import Page


class MacroRow(QWidget):
    def __init__(self, macro: Macro, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 10, 6)
        layout.setSpacing(10)

        badge = QWidget()
        badge.setFixedSize(30, 30)
        badge.setStyleSheet(
            f"background: {theme.SURFACE}; border: 1px solid {theme.BORDER_SOFT}; border-radius: 9px;")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        icon_holder = label("")
        icon_holder.setPixmap(icons.pixmap("film", theme.MUTED, 15))
        icon_holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(icon_holder)
        layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        name = label(macro.name, "muted")
        name.setStyleSheet(f"color: {theme.TEXT}; font-size: 13px; font-weight: 600;")
        text_col.addWidget(name)
        meta = label(
            f"{macro.duration_text()} · {macro.clicks} clicks · {macro.key_events} keys · "
            f"{len(macro.events):,} events", "dim")
        meta.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        text_col.addWidget(meta)
        layout.addLayout(text_col, 1)

        duration_badge = label(macro.duration_text(), "badge")
        layout.addWidget(duration_badge)


class MacrosPage(Page):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(
            "Macros",
            "Record real input with millisecond timestamps, save it, and replay it any time.",
            parent,
        )
        self.ctx = ctx
        self.store: MacroStore = ctx.store
        self.macros: list[Macro] = []
        self._current: Macro | None = None

        self._build_recorder_card()
        self._build_library_card()
        self._build_details_card()
        self.add_pair(self.library_card, self.details_card, row=1)

        self._wire()
        self.reload(select_path=ctx.config.get("macro.selected", ""))

    # ------------------------------------------------------------------ #
    #  Recorder
    # ------------------------------------------------------------------ #
    def _build_recorder_card(self) -> None:
        card = Card("Recorder", "Every click, key and mouse move is captured as you make it.", "record")
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self.record_button = button("Start recording", "hero", "record")
        self.record_button.setMinimumHeight(56)
        self.record_button.setMinimumWidth(196)

        self.save_button = button("Save & stop", "primary", "save", theme.ON_ACCENT)
        self.save_button.setMinimumHeight(56)
        self.save_button.hide()

        button_col = QVBoxLayout()
        button_col.setContentsMargins(0, 0, 0, 0)
        button_col.setSpacing(6)
        button_col.addWidget(self.record_button)
        button_col.addWidget(self.save_button)
        top.addLayout(button_col)

        self.tile_time = StatTile("Duration", "0.0", "s", "clock")
        self.tile_events = StatTile("Events", "0", "", "layers")
        self.tile_last = StatTile("Library", "0", "macros", "film")
        for tile in (self.tile_time, self.tile_events, self.tile_last):
            top.addWidget(tile, 1)
        card.add_layout(top)

        self.record_timeline = MacroTimeline(empty_text="Recorded events show up here")
        self.record_timeline.setMinimumHeight(56)
        card.add(self.record_timeline)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self.record_status = StatusPill("Idle", "off")
        footer.addWidget(self.record_status)
        self.record_hint = label("", "dim")
        footer.addWidget(self.record_hint)
        footer.addStretch(1)
        self.progress_label = label("", "dim")
        footer.addWidget(self.progress_label)
        card.add_layout(footer)

        self.recorder_card = card
        self.add_row(card, row=0)

    # ------------------------------------------------------------------ #
    #  Library
    # ------------------------------------------------------------------ #
    def _build_library_card(self) -> None:
        card = Card("Macro library", "Saved in your VClicker data folder.", "folder")
        self.import_button = icon_button("import", "Import a macro file", theme.MUTED)
        self.import_button.clicked.connect(self._import_macro)
        card.add_header_widget(self.import_button)
        self.folder_button = icon_button("folder", "Open macro folder", theme.MUTED)
        self.folder_button.clicked.connect(self._open_folder)
        card.add_header_widget(self.folder_button)

        self.list = QListWidget()
        self.list.setMinimumHeight(212)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.currentItemChanged.connect(self._on_selection)
        card.add(self.list, 1)

        self.empty = EmptyState("film", "No macros yet",
                                "Hit record and perform a few clicks — they will show up here.")
        self.empty.hide()
        card.add(self.empty)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.play_button = button("Play", "primary", "play", theme.ON_ACCENT)
        self.play_button.setMinimumHeight(34)
        self.rename_button = button("Rename", "ghost")
        self.duplicate_button = icon_button("copy", "Duplicate macro", theme.MUTED)
        self.export_button = icon_button("export", "Export macro", theme.MUTED)
        self.delete_button = icon_button("trash", "Delete macro", theme.DANGER)
        for widget in (self.rename_button, self.duplicate_button, self.export_button,
                       self.delete_button):
            widget.setMinimumHeight(34)
        actions.addWidget(self.play_button, 1)
        actions.addWidget(self.rename_button)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.delete_button)
        card.add_layout(actions)

        self.library_card = card

    # ------------------------------------------------------------------ #
    #  Details
    # ------------------------------------------------------------------ #
    def _build_details_card(self) -> None:
        card = Card("Playback", "Tune how the selected macro is replayed.", "sliders")

        self.name_label = label("No macro selected", "cardTitle")
        card.add(self.name_label)
        self.meta_label = label("", "dim")
        card.add(self.meta_label)

        self.detail_timeline = MacroTimeline()
        card.add(self.detail_timeline)

        card.add(divider())
        self.speed_row = SliderRow("Playback speed", 0.25, 4.0,
                                   float(self.ctx.config.get("macro.speed", 1.0) or 1.0),
                                   "×", 2, 0.25)
        card.add(self.speed_row)

        loops_row = QHBoxLayout()
        loops_row.setContentsMargins(0, 0, 0, 0)
        loops_row.setSpacing(8)
        loops_row.addWidget(label("Repeat", "muted"))
        loops_row.addStretch(1)
        self.loops_spin = QSpinBox()
        self.loops_spin.setRange(1, 9999)
        self.loops_spin.setValue(int(self.ctx.config.get("macro.loops", 1) or 1))
        self.loops_spin.setSuffix(" loops")
        self._apply_loop_suffix(int(self.ctx.config.get("macro.loops", 1) or 1))
        self.loops_spin.setMinimumHeight(32)
        self.loops_spin.setFixedWidth(120)
        loops_row.addWidget(self.loops_spin)
        card.add_layout(loops_row)

        self.instant_row = ToggleRow("Ignore delays (turbo)",
                                     "Replay events back-to-back with no waiting",
                                     bool(self.ctx.config.get("macro.instant", False)))
        card.add(self.instant_row)

        self.play_hero = button("Play macro", "hero", "play")
        self.play_hero.setMinimumHeight(48)
        card.add(self.play_hero)

        self.details_card = card

    # ------------------------------------------------------------------ #
    #  Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        ctx = self.ctx
        self.record_button.clicked.connect(self._toggle_record)
        self.save_button.clicked.connect(self._stop_record)
        self.play_button.clicked.connect(self._play_selected)
        self.play_hero.clicked.connect(self._play_selected)
        self.rename_button.clicked.connect(self._rename)
        self.duplicate_button.clicked.connect(self._duplicate)
        self.delete_button.clicked.connect(self._delete)
        self.export_button.clicked.connect(self._export)
        self.speed_row.value_changed.connect(self._on_speed)
        self.loops_spin.valueChanged.connect(self._on_loops)
        self.instant_row.toggled.connect(self._on_instant)

        ctx.recorder.state_changed.connect(self._on_record_state)
        ctx.recorder.counted.connect(self._on_counted)
        ctx.recorder.finished.connect(lambda _m: self._finish_record())
        ctx.player.state_changed.connect(self._on_play_state)
        ctx.player.progress.connect(self._on_progress)
        ctx.library_changed.connect(lambda: self.reload())
        ctx.macro_recorded.connect(lambda _m: self.reload())

        self._tick = QTimer(self)
        self._tick.setInterval(120)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

        self._refresh_hotkey_hints()

    # ------------------------------------------------------------------ #
    #  Library helpers
    # ------------------------------------------------------------------ #
    def reload(self, select_path: str | None = None) -> None:
        keep = select_path
        if keep is None and self._current and self._current.path:
            keep = self._current.path
        self.macros = self.store.list()
        self.list.clear()
        for macro in self.macros:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 52))
            item.setData(Qt.ItemDataRole.UserRole, macro.path)
            self.list.addItem(item)
            self.list.setItemWidget(item, MacroRow(macro))
        has_macros = bool(self.macros)
        self.list.setVisible(has_macros)
        self.empty.setVisible(not has_macros)
        self.tile_last.set_value(str(len(self.macros)))

        target_index = 0
        if keep:
            for index, macro in enumerate(self.macros):
                if macro.path == keep:
                    target_index = index
                    break
        if self.macros:
            self.list.setCurrentRow(target_index)
            self._on_selection(self.list.currentItem(), None)
        else:
            self._current = None
            self._refresh_details()

    def _selected_macro(self) -> Macro | None:
        item = self.list.currentItem()
        if item is None:
            return None
        path = item.data(Qt.ItemDataRole.UserRole)
        return next((m for m in self.macros if m.path == path), None)

    def _on_selection(self, current, previous) -> None:
        macro = self._selected_macro()
        self._current = macro
        if macro is not None:
            self.ctx.set_selected_macro(macro)
        self._refresh_details()

    def _refresh_details(self) -> None:
        macro = self._current
        has = macro is not None
        for widget in (self.play_button, self.play_hero, self.rename_button,
                       self.duplicate_button, self.export_button, self.delete_button):
            widget.setEnabled(has)
        if not macro:
            self.name_label.setText("No macro selected")
            self.meta_label.setText("Record one above, or import a .json macro file.")
            self.detail_timeline.set_events([], 0)
            return
        self.name_label.setText(macro.name)
        self.meta_label.setText(
            f"{macro.duration_text()} · {macro.clicks} clicks · {macro.key_events} key events · "
            f"{macro.moves:,} moves · created {macro.created.replace('T', ' ')}")
        self.detail_timeline.set_events(macro.events, macro.duration)

    # ------------------------------------------------------------------ #
    #  Recording
    # ------------------------------------------------------------------ #
    def _toggle_record(self) -> None:
        if self.ctx.recorder.recording:
            self._stop_record()
            return
        if self.ctx.clicker.running:
            self.ctx.clicker.stop("Stopped for recording")
        if self.ctx.player.playing:
            self.ctx.player.stop()
        if self.ctx.recorder.start():
            self.ctx.notify.emit("Recording started", "warn")

    def _stop_record(self) -> None:
        if self.ctx.recorder.recording:
            self.ctx.recorder.stop()

    def _on_record_state(self, recording: bool) -> None:
        self.record_button.setText("Recording…" if recording else "Start recording")
        self.record_button.setProperty("variant", "danger" if recording else "hero")
        self.record_button.setIcon(icons.icon("record", theme.DANGER if recording else theme.ON_ACCENT, 17))
        repolish(self.record_button)
        self.record_button.setMinimumHeight(56)
        self.save_button.setVisible(recording)
        self.record_status.set_state("live" if recording else "off",
                                     "Recording" if recording else "Idle")
        if recording:
            self.record_hint.setText("Press the record hotkey again to stop and save")
        if not recording:
            self.record_timeline.set_events([], 0)
            self._refresh_hotkey_hints()

    def _on_counted(self, count: int, elapsed: float) -> None:
        self.tile_events.set_value(f"{count:,}")
        self.tile_time.set_value(f"{elapsed:.1f}")

    def _on_tick(self) -> None:
        if self.ctx.recorder.recording:
            elapsed = self.ctx.recorder.elapsed()
            self.tile_time.set_value(f"{elapsed:.1f}")
            events = self.ctx.recorder.events_snapshot()
            self.record_timeline.set_events(events, max(elapsed, 0.1))

    def _finish_record(self) -> None:
        self._on_record_state(False)
        self.tile_events.set_value("0")
        self.tile_time.set_value("0.0")
        self.reload()

    # ------------------------------------------------------------------ #
    #  Playback
    # ------------------------------------------------------------------ #
    def _play_selected(self) -> None:
        if self.ctx.player.playing:
            self.ctx.player.stop()
            return
        macro = self._current
        if macro is None:
            macro = self.ctx.selected_macro
        if macro is None:
            self.ctx.notify.emit("Select a macro first", "warn")
            return
        if self.ctx.clicker.running:
            self.ctx.clicker.stop("Stopped for playback")
        if self.ctx.recorder.recording:
            self.ctx.recorder.stop()
        speed = float(self.speed_row.value())
        loops = int(self.loops_spin.value())
        instant = self.instant_row.isChecked()
        self.ctx.selected_macro = macro
        self.ctx.config.set("macro.speed", speed)
        self.ctx.config.set("macro.loops", loops)
        self.ctx.config.set("macro.instant", instant)
        if self.ctx.player.play(macro, speed, loops, instant):
            self.ctx.notify.emit(f"Playing “{macro.name}”", "ok")

    def _on_play_state(self, playing: bool) -> None:
        text = "Stop playback" if playing else "Play"
        for widget in (self.play_button, self.play_hero):
            widget.setText(text if widget is self.play_button else
                           ("Stop playback" if playing else "Play macro"))
            widget.setProperty("variant", "danger" if playing else
                               ("primary" if widget is self.play_button else "hero"))
            widget.setIcon(icons.icon("stop" if playing else "play",
                                      theme.DANGER if playing else theme.ON_ACCENT, 17))
            repolish(widget)
        self.play_button.setMinimumHeight(34)
        self.play_hero.setMinimumHeight(48)
        if not playing:
            self.progress_label.setText("")

    def _on_progress(self, fraction: float, index: int) -> None:
        self.progress_label.setText(f"Replay {int(fraction * 100)}% · event {index + 1}")

    def _on_speed(self, value: float) -> None:
        self.ctx.config.set("macro.speed", float(value))

    def _on_loops(self, value: int) -> None:
        self._apply_loop_suffix(int(value))
        self.ctx.config.set("macro.loops", int(value))

    def _apply_loop_suffix(self, value: int) -> None:
        self.loops_spin.setSuffix(" loop" if int(value) == 1 else " loops")

    def _on_instant(self, value: bool) -> None:
        self.ctx.config.set("macro.instant", bool(value))

    # ------------------------------------------------------------------ #
    #  Library actions
    # ------------------------------------------------------------------ #
    def _rename(self) -> None:
        macro = self._current
        if not macro:
            return
        name, ok = QInputDialog.getText(self, "Rename macro", "Macro name:", QLineEdit.EchoMode.Normal,
                                        macro.name)
        if ok and name.strip():
            macro.name = name.strip()
            self.store.save(macro)
            self.reload(select_path=macro.path)

    def _duplicate(self) -> None:
        macro = self._current
        if not macro:
            return
        clone = Macro(name=self.store.unique_name(macro.name + " copy"),
                      events=list(macro.events), duration=macro.duration)
        self.store.save(clone)
        self.ctx.notify.emit(f"Duplicated “{macro.name}”", "ok")
        self.reload(select_path=clone.path)

    def _delete(self) -> None:
        macro = self._current
        if not macro:
            return
        confirm = QMessageBox.question(
            self, "Delete macro", f"Delete “{macro.name}”? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.store.delete(macro)
            if self.ctx.selected_macro is macro:
                self.ctx.selected_macro = None
            self.ctx.notify.emit("Macro deleted", "info")
            self.reload()

    def _export(self) -> None:
        macro = self._current
        if not macro:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Export macro", os.path.join(os.path.expanduser("~"), f"{macro.name}.json"),
            "VClicker macro (*.json)")
        if target:
            self.store.export(macro, target)
            self.ctx.notify.emit("Macro exported", "ok")

    def _import_macro(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Import macro", macros_dir(), "VClicker macro (*.json)")
        if not source:
            return
        try:
            macro = self.store.import_file(source)
        except Exception as exc:
            self.ctx.notify.emit(f"Import failed: {exc}", "bad")
            return
        self.ctx.notify.emit(f"Imported “{macro.name}”", "ok")
        self.reload(select_path=macro.path)

    def _open_folder(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(macros_dir()))

    def _refresh_hotkey_hints(self) -> None:
        record_combo = keymap.combo_text(self.ctx.hotkeys.bindings.get("record_macro", "f10"))
        play_combo = keymap.combo_text(self.ctx.hotkeys.bindings.get("play_macro", "f11"))
        self.record_hint.setText(f"{record_combo} records · {play_combo} plays")
