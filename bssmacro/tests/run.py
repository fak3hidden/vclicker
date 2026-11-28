"""Execute the headless test suite: ``python -m bssmacro.tests.run``."""

from __future__ import annotations

import sys

from . import run_tests

if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
