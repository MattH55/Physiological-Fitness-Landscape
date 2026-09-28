"""Pair featurization for Phase 4.

The same function serves a drug and, later, a modifier. There is no
branch on perturbagen type. A missing mutation profile stays None. It is
not filled with zeros.
"""
from __future__ import annotations

from typing import Any


def featurize(
    signature_a: list[float | None],
    signature_b: list[float | None],
    baseline: list[float | None],
    mutations: dict[str, Any] | None,
    schedule: str,
    interval_min: float,
) -> dict:
    if schedule not in ("simultaneous", "A_first", "B_first"):
        raise ValueError(f"Unknown schedule {schedule!r}")
    if interval_min < 0:
        raise ValueError("interval_min cannot be negative")
    n = len(signature_a)
    if len(signature_b) != n or len(baseline) != n:
        raise ValueError("Signature and baseline vectors must share one length")
    return {
        "signature_a": signature_a,
        "signature_b": signature_b,
        "baseline": baseline,
        "mutations": mutations,
        "schedule": schedule,
        "interval_min": interval_min,
    }
