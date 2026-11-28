"""Bee Swarm Simulator macro for Linux — built to run with Sober (the Linux Roblox client).

The package is intentionally split into small, dependency-light modules so the
*logic* can be unit-tested headless while the *heavy* parts (OpenCV, mss,
requests) are imported lazily only when the feature is actually used.

Pipeline::

    capture (Sober window) -> vision/detector (find tokens) -> vision/collector
    (rank by priority) -> engine (move + act) -> webhook (progress report)

The "AI collector" is the :class:`bssmacro.vision.collector.Collector`: it turns a
frame full of raw detections into a single ranked navigation target so the macro
always walks toward the most valuable thing on screen.
"""

from __future__ import annotations

__version__ = "0.1.0"
