#!/usr/bin/env python3
"""Weighted geometric composite for ALPHA SWARM candidate scores.

    composite = Π (score_i / 10) ^ weight_i  × 10

A zero on any dimension yields 0. All 10s yield 10.
"""

from __future__ import annotations

WEIGHTS = {
    "acceleration": 0.25,
    "earliness": 0.20,
    "memeability": 0.15,
    "ticker_quality": 0.10,
    "narrative_legs": 0.10,
    "cultural_distance": 0.10,
    "saturation_inverse": 0.10,
}


def composite(scores: dict[str, float]) -> float:
    product = 1.0
    for name, weight in WEIGHTS.items():
        if name not in scores:
            raise KeyError(f"missing score dimension: {name}")
        value = scores[name]
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
        if value == 0:
            return 0.0
        product *= (value / 10.0) ** weight
    return product * 10.0


def _self_check() -> None:
    tens = {k: 10.0 for k in WEIGHTS}
    zeros_each = []
    for dim in WEIGHTS:
        s = {k: 10.0 for k in WEIGHTS}
        s[dim] = 0.0
        zeros_each.append((dim, composite(s)))

    all_tens = composite(tens)
    print("self-check: all 10s ->", all_tens)
    for dim, value in zeros_each:
        print(f"self-check: {dim}=0 (rest 10) -> {value}")

    ok_tens = abs(all_tens - 10.0) < 1e-12
    ok_zeros = all(v == 0.0 for _, v in zeros_each)
    if not ok_tens or not ok_zeros:
        raise SystemExit("SELF-CHECK FAILED")
    print("self-check: PASS")


if __name__ == "__main__":
    _self_check()
