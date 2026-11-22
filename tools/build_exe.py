"""Build a single-file VClicker executable with PyInstaller.

    pip install pyinstaller
    python tools/build_exe.py

The result lands in ``dist/VClicker.exe`` (Windows) or ``dist/VClicker``
(macOS/Linux). Bundled fonts and icons are embedded automatically.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "vclicker", "assets")
ENTRY = os.path.join(ROOT, "run.py")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")


def make_icon() -> str | None:
    """Render the app icon to build/app.ico (Windows) or app.icns-less fallback."""
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        sys.path.insert(0, ROOT)
        from PySide6.QtWidgets import QApplication

        from vclicker.ui.main_window import app_icon

        app = QApplication.instance() or QApplication([])  # noqa: F841 - must outlive the icon
        icon = app_icon()
        os.makedirs(BUILD, exist_ok=True)
        target = os.path.join(BUILD, "app.ico")
        sizes = [16, 24, 32, 48, 64, 128, 256]
        pixmaps = [icon.pixmap(size, size) for size in sizes]
        if pixmaps and pixmaps[-1].save(target, "ICO"):
            print(f"icon written: {target}")
            return target
        png = os.path.join(BUILD, "app.png")
        if pixmaps and pixmaps[-1].save(png, "PNG"):
            print(f"icon written: {png}")
            return png if sys.platform != "win32" else None
    except Exception as exc:  # pragma: no cover - optional step
        print(f"icon generation skipped: {exc}")
    return None


def main() -> int:
    try:
        import PyInstaller  # noqa: F401 - availability check
    except ImportError:
        print("PyInstaller is required: pip install pyinstaller")
        return 1

    icon = make_icon()
    separator = ";" if sys.platform.startswith("win") else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "VClicker",
        "--add-data", f"{ASSETS}{separator}assets",
        "--collect-submodules", "PySide6",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtPdf",
        ENTRY,
    ]
    if icon:
        args[args.index("--name") + 2:args.index("--name") + 2] = ["--icon", icon]
    print(" ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode == 0:
        print(f"\nBuilt: {os.path.join(DIST, 'VClicker' + ('.exe' if sys.platform.startswith('win') else ''))}")
        shutil.rmtree(os.path.join(ROOT, "VClicker.spec"), ignore_errors=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
