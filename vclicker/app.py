"""Application bootstrap."""

from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QApplication

from . import __version__, theme
from .config import Config
from .context import AppContext
from .paths import asset_path, logs_dir
from .ui.main_window import MainWindow, app_icon


def load_fonts() -> str:
    """Register the bundled Inter weights; fall back to whatever the OS has."""
    family = ""
    for name in ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
        path = asset_path("fonts", name)
        if not os.path.exists(path):
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id >= 0 and not family:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
    return family or "Segoe UI"


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(text)
        try:
            path = os.path.join(logs_dir(), "error.log")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass

    sys.excepthook = hook


def create_app(argv: list[str] | None = None) -> tuple[QApplication, MainWindow, AppContext]:
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vclicker.app")
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("VClicker")
    app.setApplicationDisplayName("VClicker")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("VClicker")
    # Lets desktops (X11 and Wayland) match the window to its .desktop entry.
    app.setDesktopFileName("vclicker")
    app.setStyle("Fusion")

    family = load_fonts()
    font = QFont(family, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    config = Config()
    accent = str(config.get("ui.accent", "indigo"))
    theme.CURRENT_ACCENT = accent
    app.setStyleSheet(theme.build_stylesheet(
        accent,
        asset_path("icons", "check.svg"),
        asset_path("icons", "chevron-down.svg"),
    ))
    app.setWindowIcon(app_icon())

    ctx = AppContext(config)
    window = MainWindow(ctx)
    app.aboutToQuit.connect(ctx.shutdown)
    return app, window, ctx


def main(argv: list[str] | None = None) -> int:
    _install_excepthook()
    app, window, _ctx = create_app(argv)
    window.show()
    return app.exec()
