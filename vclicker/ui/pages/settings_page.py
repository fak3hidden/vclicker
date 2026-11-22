"""Settings, diagnostics and about page."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QHBoxLayout,
                               QPushButton, QVBoxLayout, QWidget)

from ... import __version__, session, theme
from ...doctor import missing_libraries
from ...paths import app_dir, config_path, macros_dir
from ..widgets import Banner, Card, StatusPill, ToggleRow, button, divider, icon_badge, label
from .base import Page


class AccentSwatch(QPushButton):
    def __init__(self, name: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.setCheckable(True)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name.title())
        self.setStyleSheet(
            f"QPushButton {{ background: {color}; border-radius: 14px; border: 2px solid "
            f"transparent; }}"
            f"QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.55); }}"
            f"QPushButton:checked {{ border: 2px solid #FFFFFF; }}"
        )


class DiagnosticsDialog(QDialog):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VClicker diagnostics")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        layout.addWidget(label("Diagnostics", "pageTitle"))
        layout.addWidget(label("A quick check of the native input layer and global capture.",
                               "dim", wrap=True))

        backend = ctx.backend
        caps = backend.caps

        def check(title: str, ok: bool, detail: str) -> None:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            pill = StatusPill("OK" if ok else "N/A", "live" if ok else "warn")
            pill.setFixedWidth(58)
            row.addWidget(pill)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(1)
            text.addWidget(label(title, "muted"))
            if detail:
                text.addWidget(label(detail, "dim", wrap=True))
            row.addLayout(text, 1)
            layout.addLayout(row)

        check("Input backend", caps.clicking, backend.describe())
        check("Send clicks", caps.clicking,
              "Native click injection is available." if caps.clicking
              else "No backend — clicks cannot be sent on this system.")
        check("Send keys", caps.key_send,
              "Keyboard events can be injected." if caps.key_send
              else "Keyboard injection is not available.")
        check("Background key hold", caps.targeted_hold,
              "Keys can be held on windows without focus." if caps.targeted_hold
              else "Key hold uses focus switching on this platform.")
        check("Window list", caps.window_list,
              f"{len(backend.list_windows())} windows visible right now." if caps.window_list
              else "Window targeting is not supported here.")
        check("Global capture / hotkeys", bool(caps.hotkeys and ctx.monitor.running),
              caps.recording_quality or "Monitor not running.")
        for note in caps.notes:
            layout.addWidget(label("• " + note, "dim", wrap=True))
        if backend.needs_permissions_hint:
            layout.addWidget(Banner(backend.needs_permissions_hint, "warn"))

        close_row = QHBoxLayout()
        close_row.setContentsMargins(0, 0, 0, 0)
        close_row.addStretch(1)
        close = button("Close", "primary", None, theme.ON_ACCENT)
        close.clicked.connect(self.accept)
        close.setMinimumHeight(36)
        close.setFixedWidth(120)
        close_row.addWidget(close)
        layout.addLayout(close_row)


class SettingsPage(Page):
    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__("Settings", "Make VClicker yours and check that everything is wired up.",
                         parent)
        self.ctx = ctx
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        self._build_appearance()
        self._build_backend()
        self._build_data()
        self._build_about()
        self.add_pair(self.appearance_card, self.backend_card, row=0)
        self.add_pair(self.data_card, self.about_card, row=1)

    # ------------------------------------------------------------------ #
    def _build_appearance(self) -> None:
        card = Card("Appearance", "Theme details for this machine.", "sliders")
        card.add(label("ACCENT COLOUR", "sectionTitle"))
        swatches = QHBoxLayout()
        swatches.setContentsMargins(0, 0, 0, 0)
        swatches.setSpacing(9)
        self._accent_group = QButtonGroup(self)
        self._accent_group.setExclusive(True)
        current = self.ctx.config.get("ui.accent", "indigo")
        for name, (main, _h, _p, _s, _l) in theme.ACCENTS.items():
            swatch = AccentSwatch(name, main)
            swatch.setChecked(name == current)
            swatch.clicked.connect(lambda _c=False, n=name: self._set_accent(n))
            self._accent_group.addButton(swatch)
            swatches.addWidget(swatch)
        swatches.addStretch(1)
        card.add_layout(swatches)

        card.add(divider())
        self.always_on_top = ToggleRow("Always on top",
                                       "Keep the window above games and browsers",
                                       bool(self.ctx.config.get("ui.always_on_top", False)))
        self.always_on_top.toggled.connect(self._on_always_on_top)
        card.add(self.always_on_top)

        card.add(Banner(
            "Accent changes repaint the whole interface instantly and are remembered next launch.",
            "info"))
        self.appearance_card = card

    def _build_backend(self) -> None:
        backend = self.ctx.backend
        card = Card("System", "What VClicker is using to send input.", "shield")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(icon_badge("shield", theme.SUCCESS if backend.caps.clicking else theme.DANGER,
                                 theme.SURFACE, 32, 16))
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        text.addWidget(label(backend.name, "muted"))
        text.addWidget(label(f"{backend.os_name.title()} · Python {sys.version.split()[0]}", "dim"))
        row.addLayout(text, 1)
        card.add_layout(row)

        caps_row = QHBoxLayout()
        caps_row.setContentsMargins(0, 0, 0, 0)
        caps_row.setSpacing(6)
        for text_value, ok in (("clicks", backend.caps.clicking), ("keys", backend.caps.key_send),
                               ("windows", backend.caps.targeted_hold),
                               ("capture", backend.caps.recording)):
            badge = label(text_value, "badge")
            if ok:
                badge.setProperty("tone", "accent")
            caps_row.addWidget(badge)
        caps_row.addStretch(1)
        card.add_layout(caps_row)

        if backend.needs_permissions_hint:
            card.add(Banner(backend.needs_permissions_hint, "warn"))

        if sys.platform.startswith("linux"):
            missing = missing_libraries() if not backend.caps.clicking else []
            if missing:
                names = ", ".join(name.split(".so")[0] for name in missing)
                card.add(Banner(f"Not installed: {names}", "bad"))
                command = session.install_command(missing)
                fix_row = QHBoxLayout()
                fix_row.setContentsMargins(0, 0, 0, 0)
                fix_row.setSpacing(8)
                code = label(command, "key")
                code.setWordWrap(True)
                code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                fix_row.addWidget(code, 1)
                copy = button("Copy", "ghost", "copy", theme.TEXT)
                copy.setMinimumHeight(32)
                copy.clicked.connect(lambda _=False, cmd=command: self._copy(cmd))
                fix_row.addWidget(copy)
                card.add_layout(fix_row)
                card.add(label("Then restart VClicker. Run “python run.py --check” to verify.",
                               "dim", wrap=True))
        if sys.platform.startswith("linux") and session.kind() == "wayland":
            card.add(Banner(
                "Wayland session detected: input only reaches X11 (XWayland) windows. "
                "Log into an “X11 / Xorg” session for native Wayland apps.", "warn"))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        diag = button("Run diagnostics", "ghost", "check", theme.TEXT)
        diag.clicked.connect(self._open_diagnostics)
        folder = button("Data folder", "ghost", "folder", theme.TEXT)
        folder.clicked.connect(lambda: self._open_path(app_dir()))
        buttons.addWidget(diag)
        buttons.addWidget(folder)
        buttons.addStretch(1)
        card.add_layout(buttons)
        self.backend_card = card

    def _copy(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.ctx.notify.emit("Command copied to clipboard", "ok")

    def _build_data(self) -> None:
        card = Card("Data", "Everything stays on this computer.", "save")
        for title, path in (("Config", config_path()), ("Macros", macros_dir())):
            line_row = QHBoxLayout()
            line_row.setContentsMargins(0, 0, 0, 0)
            line_row.addWidget(label(title, "dim"))
            line_row.addStretch(1)
            value = label(path, "mono")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            line_row.addWidget(value)
            card.add_layout(line_row)
        card.add(divider())
        reset = button("Reset all settings", "danger", "refresh", theme.DANGER)
        reset.clicked.connect(self._reset_settings)
        reset.setFixedWidth(190)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(reset)
        reset_row.addStretch(1)
        card.add_layout(reset_row)
        self.data_card = card

    def _build_about(self) -> None:
        card = Card("About", f"VClicker {__version__}", "info")
        card.add(label(
            "A native auto clicker, key holder, macro recorder and hotkey daemon in one window. "
            "No accounts, no telemetry — nothing ever leaves your machine.", "dim", wrap=True))
        card.add(divider())
        for name, detail in (
            ("Interface", "PySide6 / Qt 6 with a custom dark theme"),
            ("Input", "ctypes — SendInput, XTest and CoreGraphics"),
            ("Fonts", "Inter by Rasmus Andersson (SIL OFL 1.1)"),
            ("Icons", "Lucide icon set (MIT)"),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(label(name, "dim"))
            row.addStretch(1)
            row.addWidget(label(detail, "muted"))
            card.add_layout(row)
        self.about_card = card

    # ------------------------------------------------------------------ #
    def _set_accent(self, name: str) -> None:
        self.ctx.set_accent(name)

    def _on_always_on_top(self, value: bool) -> None:
        self.ctx.config.set("ui.always_on_top", bool(value))
        window = self.window()
        if window:
            window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(value))
            window.show()

    def _open_diagnostics(self) -> None:
        dialog = DiagnosticsDialog(self.ctx, self)
        dialog.exec()

    def _open_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _reset_settings(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(
            self, "Reset settings",
            "Reset every setting, hotkey and saved preference to its default?\n"
            "Recorded macros are kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from ...config import DEFAULTS
        import copy
        self.ctx.config.data = copy.deepcopy(DEFAULTS)
        self.ctx.config.save()
        self.ctx.notify.emit("Settings reset — restart VClicker to apply everything", "warn")
