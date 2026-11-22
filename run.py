#!/usr/bin/env python3
"""VClicker launcher.

    python run.py            start the app
    python run.py --check    report on the native input layer (no GUI)
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
    if any(arg in ("--check", "--doctor", "doctor") for arg in sys.argv[1:]):
        from vclicker.doctor import main as doctor_main
        return doctor_main(sys.argv[1:])
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
