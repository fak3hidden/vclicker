"""Main window: sidebar navigation, page stack and live status strip."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import __version__, icons, keys as keymap, theme
from ..context import AppContext
from .pages.clicker_page import ClickerPage
from .pages.hotkeys_page import HotkeysPage
from .pages.keyholder_page import KeyHolderPage
from .pages.macros_page import MacrosPage
from .pages.settings_page import SettingsPage
from .widgets import StatusPill, button, label, letter_spacing, repolish

NAV = [
    ("clicker", "Auto Clicker", "cursor", ClickerPage),
    ("keyholder", "Key Holder", "keyboard", KeyHolderPage),
    ("macros", "Macros", "film", MacrosPage),
    ("hotkeys", "Hotkeys", "command", HotkeysPage),
    ("settings", "Settings", "sliders", SettingsPage),
]

TONE_COLORS = {
    "info": theme.MUTED,
    "ok": theme.SUCCESS,
    "warn": theme.WARN,
    "bad": theme.DANGER,
}


def app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    main, _h, _p, _s, _l = theme.accent_tuple(getattr(theme, "CURRENT_ACCENT", "indigo"))
    gradient = QLinearGradient(0, 0, 256, 256)
    gradient.setColorAt(0.0, QColor(main))
    gradient.setColorAt(1.0, QColor(_p))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(8, 8, 240, 240, 56, 56)
    painter.setPen(QColor(theme.ON_ACCENT))
    font = QFont("Inter", 128)
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "V")
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"VClicker {__version__}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1040, 700)

        width, height = ctx.config.get("ui.window", [1240, 840])
        self.resize(int(width), int(height))
        if ctx.config.get("ui.always_on_top", False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.root = QWidget()
        self.root.setObjectName("Root")
        self.setCentralWidget(self.root)
        root_layout = QHBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        content = QFrame()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        self._build_status_strip(content_layout)
        root_layout.addWidget(content, 1)

        self.pages: list[QWidget] = []
        self._build_pages()
        self._wire()

        index = int(ctx.config.get("ui.last_page", 0) or 0)
        self.set_page(max(0, min(len(NAV) - 1, index)))
        self._refresh_global_state()

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(7000)
        self._status_timer.timeout.connect(self._idle_status)

    # ------------------------------------------------------------------ #
    #  Sidebar
    # ------------------------------------------------------------------ #
    def _build_sidebar(self) -> None:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(236)
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setContentsMargins(4, 0, 0, 0)
        brand.setSpacing(10)
        logo = QLabel("V")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main, _h, _p, _s, _l = theme.accent_tuple(getattr(theme, "CURRENT_ACCENT", "indigo"))
        self.logo = logo
        self._style_logo()
        brand.addWidget(logo)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        wordmark = label("VCLICKER")
        wordmark.setStyleSheet("font-size: 15px; font-weight: 800; letter-spacing: 1.6px;")
        title_col.addWidget(wordmark)
        version = label(f"v{__version__} · native input", "dim")
        version.setStyleSheet(f"color: {theme.DIM}; font-size: 10.5px;")
        title_col.addWidget(version)
        brand.addLayout(title_col, 1)
        layout.addLayout(brand)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text, icon_name, _page in NAV:
            btn = QPushButton(f"   {text}")
            btn.setProperty("variant", "nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(18, 18))
            btn.setMinimumHeight(42)
            btn.clicked.connect(lambda _c=False, k=key: self.set_page_by_key(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addSpacing(12)
        self.quick_keys_holder = QWidget()
        quick_layout = QVBoxLayout(self.quick_keys_holder)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(0)
        quick_layout.addWidget(self._sidebar_hotkey_card())
        layout.addWidget(self.quick_keys_holder)
        layout.addStretch(1)
        layout.addWidget(self._sidebar_status_card())

    def _style_logo(self) -> None:
        main, _h, pressed, _s, _l = theme.accent_tuple(getattr(theme, "CURRENT_ACCENT", "indigo"))
        self.logo.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {main}, stop:1 {pressed});"
            f"border-radius: 11px; color: {theme.ON_ACCENT}; font-size: 19px; font-weight: 800;")

    def _sidebar_hotkey_card(self) -> QWidget:
        holder = QFrame()
        holder.setProperty("role", "inset")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(12, 11, 12, 12)
        layout.setSpacing(8)
        caption = label("QUICK KEYS", "sectionTitle")
        letter_spacing(caption, 0.8)
        layout.addWidget(caption)
        bindings = self.ctx.hotkeys.bindings
        for action, name in (("toggle_clicker", "Clicker"), ("toggle_keyhold", "Key hold"),
                             ("panic", "Panic stop")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(label(name, "dim"))
            row.addStretch(1)
            combo = keymap.combo_text(bindings.get(action, ""))
            cap = QLabel(combo or "—")
            cap.setProperty("role", "key")
            row.addWidget(cap)
            layout.addLayout(row)
        hint = label("Change these on the Hotkeys page", "dim", wrap=True)
        hint.setStyleSheet(f"color: {theme.DIM}; font-size: 10.5px;")
        layout.addWidget(hint)
        return holder

    def _refresh_quick_keys(self) -> None:
        layout = self.quick_keys_holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        layout.addWidget(self._sidebar_hotkey_card())

    def _sidebar_status_card(self) -> QWidget:
        holder = QFrame()
        holder.setProperty("role", "inset")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(12, 11, 12, 12)
        layout.setSpacing(7)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label("INPUT LAYER", "sectionTitle"))
        row.addStretch(1)
        self.backend_dot = QLabel()
        row.addWidget(self.backend_dot)
        layout.addLayout(row)
        backend = self.ctx.backend
        ok = backend.caps.clicking
        self.backend_dot.setPixmap(icons.pixmap("check" if ok else "alert",
                                                theme.SUCCESS if ok else theme.DANGER, 12))
        name = label(backend.name, "dim", wrap=True)
        name.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        layout.addWidget(name)
        if not backend.caps.recording:
            capture_text = "Capture unavailable"
        elif self.ctx.monitor.running:
            capture_text = "Capture active"
        else:
            capture_text = "Capture stopped"
        self.monitor_label = label(capture_text, "dim")
        self.monitor_label.setStyleSheet(f"color: {theme.DIM}; font-size: 10.5px;")
        layout.addWidget(self.monitor_label)
        return holder

    # ------------------------------------------------------------------ #
    #  Status strip
    # ------------------------------------------------------------------ #
    def _build_status_strip(self, parent_layout: QVBoxLayout) -> None:
        strip = QFrame()
        strip.setFixedHeight(46)
        strip.setStyleSheet(
            f"#StatusStrip {{ background: {theme.SIDEBAR}; border-top: 1px solid {theme.BORDER_SOFT}; }}")
        strip.setObjectName("StatusStrip")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)

        self.status_dot = QLabel()
        self.status_dot.setPixmap(icons.pixmap("info", theme.MUTED, 13))
        layout.addWidget(self.status_dot)
        self.status_label = label("Ready", "dim")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.state_pill = StatusPill("Idle", "off")
        layout.addWidget(self.state_pill)

        self.stop_button = button("Stop everything", "ghost", "power", theme.DIM)
        self.stop_button.setMinimumHeight(30)
        self.stop_button.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.stop_button.clicked.connect(self.ctx.panic)
        layout.addWidget(self.stop_button)

        parent_layout.addWidget(strip)

    # ------------------------------------------------------------------ #
    #  Pages
    # ------------------------------------------------------------------ #
    def _build_pages(self) -> None:
        for _key, _text, _icon, page_class in NAV:
            page = page_class(self.ctx)
            self.stack.addWidget(page)
            self.pages.append(page)

    def _rebuild_pages(self) -> None:
        index = self.stack.currentIndex()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()
        self.pages.clear()
        self._build_pages()
        self.set_page(index)

    def set_page_by_key(self, key: str) -> None:
        for index, (nav_key, _text, _icon, _page) in enumerate(NAV):
            if nav_key == key:
                self.set_page(index)

    def set_page(self, index: int) -> None:
        index = max(0, min(self.stack.count() - 1, int(index)))
        self.stack.setCurrentIndex(index)
        key = NAV[index][0]
        for nav_key, btn in self.nav_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(nav_key == key)
            btn.blockSignals(False)
        self._update_nav_icons()
        self.ctx.config.set("ui.last_page", index)

    def _update_nav_icons(self) -> None:
        main, _h, _p, _s, _l = theme.accent_tuple(getattr(theme, "CURRENT_ACCENT", "indigo"))
        for key, text, icon_name, _page in NAV:
            btn = self.nav_buttons.get(key)
            if btn is None:
                continue
            color = main if btn.isChecked() else theme.MUTED
            btn.setIcon(icons.icon(icon_name, color, 18))
            btn.setText(f"   {text}")
            font = btn.font()
            font.setWeight(QFont.Weight.DemiBold if btn.isChecked() else QFont.Weight.Normal)
            btn.setFont(font)

    # ------------------------------------------------------------------ #
    #  Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        ctx = self.ctx
        ctx.notify.connect(self.show_status)
        ctx.clicker.state_changed.connect(lambda _r: self._refresh_global_state())
        ctx.clicker.stats.connect(self._on_stats)
        ctx.keyholder.state_changed.connect(lambda _r: self._refresh_global_state())
        ctx.player.state_changed.connect(lambda _r: self._refresh_global_state())
        ctx.recorder.state_changed.connect(lambda _r: self._refresh_global_state())
        ctx.accent_changed.connect(self.apply_accent)
        ctx.bindings_changed.connect(self._refresh_quick_keys)

    def _on_stats(self, cps: float, total: int, peak: float) -> None:
        if self.ctx.clicker.running:
            self.state_pill.set_state("live", f"Clicking · {cps:,.0f} CPS")

    def _refresh_global_state(self) -> None:
        active: list[str] = []
        if self.ctx.recorder.recording:
            active.append("Recording")
        if self.ctx.player.playing:
            active.append("Playing macro")
        if self.ctx.keyholder.active:
            keys = ", ".join(keymap.label(k) for k in self.ctx.keyholder.keys)
            active.append(f"Holding {keys}")
        if self.ctx.clicker.running:
            active.append("Clicking")
        if active:
            self.state_pill.set_state("live", " · ".join(active))
        else:
            self.state_pill.set_state("off", "Idle")
        self.stop_button.setEnabled(bool(active))
        self.stop_button.setProperty("variant", "danger" if active else "ghost")
        self.stop_button.setIcon(icons.icon("power", theme.DANGER if active else theme.DIM, 15))
        repolish(self.stop_button)

    def show_status(self, message: str, tone: str = "info") -> None:
        color = TONE_COLORS.get(tone, theme.MUTED)
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        icon_name = {"ok": "check", "bad": "alert", "warn": "alert"}.get(tone, "info")
        self.status_dot.setPixmap(icons.pixmap(icon_name, color, 13))
        self._status_timer.start()

    def _idle_status(self) -> None:
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet(f"color: {theme.DIM}; font-size: 12px;")
        self.status_dot.setPixmap(icons.pixmap("info", theme.MUTED, 13))

    # ------------------------------------------------------------------ #
    #  Theme
    # ------------------------------------------------------------------ #
    def apply_accent(self, name: str) -> None:
        theme.CURRENT_ACCENT = name
        from ..paths import asset_path
        check_icon = asset_path("icons", "check.svg")
        chevron = asset_path("icons", "chevron-down.svg")
        self.ctx.config.set("ui.accent", name, save=False)
        self.ctx.config.save()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.build_stylesheet(name, check_icon, chevron))
        self.setWindowIcon(app_icon())
        self._style_logo()
        self._update_nav_icons()
        self._rebuild_pages()
        self.show_status(f"{name.title()} accent applied", "ok")

    # ------------------------------------------------------------------ #
    #  Window events
    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:
        try:
            self.ctx.config.set("ui.window", [self.width(), self.height()], save=False)
            self.ctx.shutdown()
        except Exception:
            pass
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            busy = (self.ctx.clicker.running or self.ctx.keyholder.active
                    or self.ctx.player.playing or self.ctx.recorder.recording)
            if busy:
                self.ctx.panic()
                return
        super().keyPressEvent(event)
