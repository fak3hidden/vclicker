#!/usr/bin/env python3
"""VClicker launcher.

    python run.py
"""

from __future__ import annotations

import sys


def _missing_dependency() -> None:
    message = (
        "\n  VClicker needs PySide6 (Qt 6) to draw its interface.\n\n"
        "    pip install PySide6-Essentials\n\n"
        "  or, if you prefer the full Qt bundle:\n\n"
        "    pip install PySide6\n"
    )
    print(message)
    try:
        input("  Press Enter to close…")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> int:
    try:
        import PySide6
        _ = PySide6.__version__
    except ImportError:
        _missing_dependency()
        return 1
    from vclicker.app import main as run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
