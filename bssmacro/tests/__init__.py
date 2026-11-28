"""Headless test suite for the BSS Linux macro.

Run with::

    .venv/bin/python -m bssmacro.tests.run

or ``python run_bss.py selftest``. No display, no network and no Roblox needed —
the vision code is exercised with synthetic frames and the engine with a
:class:`FakeInput`.
"""

from __future__ import annotations

import os
import unittest


def run_tests() -> unittest.TestResult:
    loader = unittest.TestLoader()
    here = os.path.dirname(os.path.abspath(__file__))
    # Treat the repo root as the top-level package so sibling relative imports
    # (``from .helpers import ...``) resolve as ``bssmacro.tests.*``.
    top = os.path.dirname(os.path.dirname(here))
    suite = loader.discover(start_dir=here, pattern="test_*.py", top_level_dir=top)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    import sys

    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
