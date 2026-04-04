"""
Reference implementation matching REAL-IDS cpp/src/can_ids.cpp (CanClockSkewIds).
Used for latency micro-benchmarks only; production logic remains in C++.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class _BaselineState:
    interval_ms: float
    last_seen_ms: int


class CanClockSkewIdsPy:
    """Mirrors real_ids::CanClockSkewIds."""

    def __init__(self, skew_threshold_ms: float = 15.0) -> None:
        self.skew_threshold_ms = skew_threshold_ms
        self._baselines: Dict[str, _BaselineState] = {}

    def train(self, can_id: str, timestamp_ms: int) -> None:
        it = self._baselines.get(can_id)
        if it is None:
            self._baselines[can_id] = _BaselineState(0.0, timestamp_ms)
            return
        state = it
        if state.interval_ms == 0.0:
            state.interval_ms = float(timestamp_ms - state.last_seen_ms)
        else:
            delta = float(timestamp_ms - state.last_seen_ms)
            state.interval_ms = state.interval_ms * 0.9 + delta * 0.1
        state.last_seen_ms = timestamp_ms

    def detect(self, can_id: str, timestamp_ms: int) -> bool:
        it = self._baselines.get(can_id)
        if it is None:
            return False
        state = it
        interval = state.interval_ms if state.interval_ms > 0.0 else 0.0
        expected = float(state.last_seen_ms) + interval
        skew = abs(float(timestamp_ms) - expected)
        state.last_seen_ms = timestamp_ms
        return skew > self.skew_threshold_ms


def benchmark_detect_ns(
    *,
    iterations: int,
    warmup: int,
    skew_threshold_ms: float = 15.0,
) -> Tuple[float, float, float, float, float]:
    """Returns mean_ns, min_ns, p95_ns, p99_ns, max_ns for one detect() call."""
    import math
    import time

    ids = CanClockSkewIdsPy(skew_threshold_ms=skew_threshold_ms)
    cid = "0x1A4"
    t = 1_000_000
    for _ in range(400):
        ids.train(cid, t)
        t += 20

    for _ in range(warmup):
        ids.detect(cid, t)
        t += 20

    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        ids.detect(cid, t)
        t1 = time.perf_counter_ns()
        samples.append(float(t1 - t0))
        t += 20

    s = sorted(samples)
    if not s:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    def pct(p: float) -> float:
        n = len(s)
        if n == 1:
            return s[0]
        k = (n - 1) * p / 100.0
        f = int(math.floor(k))
        c = int(math.ceil(k))
        if f == c:
            return s[int(k)]
        return s[f] * (c - k) + s[c] * (k - f)

    return (
        sum(s) / len(s),
        s[0],
        pct(95),
        pct(99),
        s[-1],
    )
