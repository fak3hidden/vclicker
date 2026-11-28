#!/usr/bin/env python3
"""Launcher for the Bee Swarm Simulator Linux macro (works with Sober).

    python run_bss.py run              start farming
    python run_bss.py calibrate        capture Sober + crop templates
    python run_bss.py webhook-test     test your Discord webhook
    python run_bss.py selftest         run the headless tests
    python run_bss.py --help           all subcommands
"""

from __future__ import annotations

import sys

from bssmacro.cli import main

if __name__ == "__main__":
    sys.exit(main())
