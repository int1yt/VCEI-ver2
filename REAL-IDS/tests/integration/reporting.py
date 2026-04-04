"""Unified test report: JSON + plain text + console summary."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

Status = Literal["pass", "fail", "skip"]


@dataclass
class CorrectnessResult:
    id: str
    status: Status
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class LatencyResult:
    id: str
    endpoint: str
    method: str
    iterations: int
    warmup: int
    mean_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    errors: int = 0


@dataclass
class Report:
    started_at: str
    daemon_url: str
    bridge_url: str
    daemon_probe_error: str = ""
    bridge_probe_error: str = ""
    correctness: List[CorrectnessResult] = field(default_factory=list)
    latency: List[LatencyResult] = field(default_factory=list)
    classification: Optional[Dict[str, Any]] = None
    clock_skew: Optional[Dict[str, Any]] = None

    def counts(self) -> Dict[str, int]:
        c = {"pass": 0, "fail": 0, "skip": 0}
        for r in self.correctness:
            c[r.status] = c.get(r.status, 0) + 1
        return c

    def to_json_obj(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "started_at": self.started_at,
            "config": {"daemon_url": self.daemon_url, "bridge_url": self.bridge_url},
            "probe": {
                "daemon_ok": not bool(self.daemon_probe_error),
                "daemon_error": self.daemon_probe_error or None,
                "bridge_ok": not bool(self.bridge_probe_error),
                "bridge_error": self.bridge_probe_error or None,
            },
            "correctness": [asdict(r) for r in self.correctness],
            "latency": [asdict(r) for r in self.latency],
            "summary": {
                **self.counts(),
                "latency_groups": len(self.latency),
            },
        }
        if self.classification is not None:
            d["classification"] = self.classification
        if self.clock_skew is not None:
            d["clock_skew"] = self.clock_skew
        return d

    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        jpath = out_dir / "summary.json"
        tpath = out_dir / "summary.txt"
        jpath.write_text(json.dumps(self.to_json_obj(), indent=2), encoding="utf-8")
        lines = [
            f"REAL-IDS integration test report",
            f"started_at: {self.started_at}",
            f"daemon_url: {self.daemon_url}",
            f"bridge_url: {self.bridge_url}",
            f"probe_daemon: {'OK' if not self.daemon_probe_error else self.daemon_probe_error}",
            f"probe_bridge: {'OK' if not self.bridge_probe_error else self.bridge_probe_error}",
            "",
            "=== Correctness ===",
        ]
        for r in self.correctness:
            lines.append(f"  [{r.status.upper():4}] {r.id}  ({r.duration_ms:.2f} ms) {r.detail}")
        lines.append("")
        lines.append("=== Latency ===")
        for r in self.latency:
            lines.append(
                f"  {r.id}  {r.method} {r.endpoint}  n={r.iterations} (warmup {r.warmup})"
            )
            lines.append(
                f"    mean={r.mean_ms:.2f} ms  min={r.min_ms:.2f}  p50={r.p50_ms:.2f}  "
                f"p95={r.p95_ms:.2f}  p99={r.p99_ms:.2f}  max={r.max_ms:.2f}  errors={r.errors}"
            )
        lines.append("")
        if self.classification is not None:
            lines.append("=== CarHack classification (offline eval) ===")
            c = self.classification
            if c.get("enabled"):
                lines.append(
                    f"  accuracy={c.get('accuracy', 0):.4f}  n={c.get('n_samples', 0)}  weights={c.get('weights', '')}"
                )
                for name, row in (c.get("per_class") or {}).items():
                    lines.append(f"    {name}: n={row.get('n', 0)}  class_acc={row.get('acc', 0):.4f}")
            else:
                lines.append(f"  disabled: {c.get('error', '')}")
            lines.append("")
        if self.clock_skew is not None:
            lines.append("=== Clock-skew IDS (Python ref vs cpp/can_ids.cpp) ===")
            s = self.clock_skew
            if s.get("enabled"):
                lines.append(
                    f"  mean_ns_per_detect={s.get('mean_ns_per_detect', 0):.1f}  "
                    f"p95={s.get('p95_ns', 0):.1f}  p99={s.get('p99_ns', 0):.1f}  "
                    f"mean_us={s.get('mean_us_per_detect', 0):.4f}"
                )
                lines.append(
                    f"  iterations={s.get('iterations')}  warmup={s.get('warmup')}  "
                    f"threshold_ms={s.get('skew_threshold_ms')}"
                )
            else:
                lines.append(f"  disabled: {s.get('error', '')}")
            lines.append("")
        sc = self.counts()
        lines.append(
            f"=== Totals ===  pass={sc['pass']}  fail={sc['fail']}  skip={sc['skip']}  "
            f"latency_scenarios={len(self.latency)}"
        )
        tpath.write_text("\n".join(lines) + "\n", encoding="utf-8")


def percentile(sorted_samples: List[float], p: float) -> float:
    if not sorted_samples:
        return 0.0
    xs = sorted_samples
    n = len(xs)
    if n == 1:
        return xs[0]
    k = (n - 1) * p / 100.0
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return xs[f]
    return xs[f] * (c - k) + xs[c] * (k - f)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
