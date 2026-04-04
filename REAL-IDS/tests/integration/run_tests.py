#!/usr/bin/env python3
"""
Integration tests: correctness + latency for real_ids_daemon and ml_bridge.
Unified output: ./results/summary.json and ./results/summary.txt

  cd REAL-IDS/tests/integration
  pip install -r requirements.txt
  python run_tests.py

Services must be running unless they will be marked skip (use --strict to fail on down).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx

from reporting import CorrectnessResult, LatencyResult, Report, percentile, now_iso


def normalize_client_base(url: str) -> str:
    """Client must use 127.0.0.1, not 0.0.0.0 (invalid connect target on many systems)."""
    raw = url.strip().rstrip("/")
    if "://" not in raw:
        raw = "http://" + raw
    p = urlparse(raw)
    host = (p.hostname or "").lower()
    if host in ("0.0.0.0", "::"):
        port = f":{p.port}" if p.port else ""
        p = p._replace(netloc=f"127.0.0.1{port}")
    return urlunparse(p).rstrip("/")


def http_probe(base: str, path: str, timeout: float = 10.0) -> Tuple[bool, str]:
    """
    trust_env=False: ignore HTTP(S)_PROXY so 127.0.0.1 is not sent to a corporate proxy (common skip cause).
    """
    try:
        with httpx.Client(base_url=base, timeout=timeout, trust_env=False) as c:
            r = c.get(path)
            if r.status_code == 200:
                return True, ""
            return False, f"HTTP {r.status_code} (expected 200) GET {path}"
    except httpx.ConnectError as e:
        return (
            False,
            f"ConnectError: {e!s} | 确认服务已监听、端口正确；URL 用 http://127.0.0.1:端口 不要用 0.0.0.0",
        )
    except Exception as e:
        return False, f"{type(e).__name__}: {e!s}"


# -----------------------------------------------------------------------------
# Payload builders
# -----------------------------------------------------------------------------


def can_history_n(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(n):
        out.append(
            {
                "id": f"0x{i + 0x100:03X}",
                "data": f"{(i * 17) & 0xFF:02x}" * 8,
                "timestamp": 1_000_000 + i * 10,
                "isAttack": False,
            }
        )
    return out


def eth_context_sample() -> List[Dict[str, Any]]:
    rows = []
    for i in range(5):
        rows.append(
            {
                "id": i,
                "timestamp": 2_000_000 + i,
                "srcIp": f"192.168.1.{i + 1}",
                "dstIp": "10.0.0.1",
                "protocol": "TCP",
                "length": 512 + i,
                "isAttack": i == 4,
            }
        )
    return rows


def enrich_body_full() -> Dict[str, Any]:
    return {
        "real_ids_classification": "TestFusion",
        "can_skew_triggered": True,
        "trigger_can": {"id": "0x1A4", "data": "0102030405060708", "timestamp": 3_000_000},
        "ethernet_context": eth_context_sample(),
        "can_history": can_history_n(29),
    }


def enrich_body_minimal() -> Dict[str, Any]:
    return {
        "real_ids_classification": "",
        "can_skew_triggered": False,
        "trigger_can": {},
        "ethernet_context": [],
        "can_history": [],
    }


def flow_10x80() -> List[List[float]]:
    return [[0.01 * (i + j) for j in range(80)] for i in range(10)]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def measure_latency(
    fn: Callable[[], None],
    iterations: int,
    warmup: int,
) -> Tuple[List[float], int]:
    times: List[float] = []
    errors = 0
    for _ in range(warmup):
        try:
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            errors += 1
    times.clear()
    for _ in range(iterations):
        try:
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            errors += 1
    return times, errors


def summarize_times(samples: List[float]) -> Tuple[float, float, float, float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    s = sorted(samples)
    return (
        sum(s) / len(s),
        s[0],
        s[-1],
        percentile(s, 50),
        percentile(s, 95),
        percentile(s, 99),
    )


# -----------------------------------------------------------------------------
# Correctness cases
# -----------------------------------------------------------------------------


def run_correctness(
    client_d: httpx.Client,
    client_b: httpx.Client,
    daemon_ok: bool,
    bridge_ok: bool,
    strict: bool,
    daemon_detail: str = "",
    bridge_detail: str = "",
) -> List[CorrectnessResult]:
    results: List[CorrectnessResult] = []

    def add(cid: str, ok: bool, detail: str, ms: float, skip: bool = False) -> None:
        if skip:
            results.append(CorrectnessResult(id=cid, status="skip", detail=detail, duration_ms=ms))
            return
        if ok:
            results.append(CorrectnessResult(id=cid, status="pass", detail=detail, duration_ms=ms))
        else:
            results.append(CorrectnessResult(id=cid, status="fail", detail=detail, duration_ms=ms))

    # --- daemon ---
    if not daemon_ok:
        msg = f"daemon unreachable — {daemon_detail}"
        add("daemon_reachable", False, msg, 0.0, skip=not strict)
        if strict:
            for cid in (
                "daemon_health_v1",
                "daemon_stats_v1",
                "daemon_simulation_cycle",
                "daemon_attack_invalid_json",
            ):
                add(cid, False, msg, 0.0)
    else:
        t0 = time.perf_counter()
        try:
            r = client_d.get("/api/v1/health")
            ms = (time.perf_counter() - t0) * 1000.0
            ok = r.status_code == 200 and r.json().get("status") == "ok"
            add("daemon_health_v1", ok, f"HTTP {r.status_code}", ms)
        except Exception as e:
            add("daemon_health_v1", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            r = client_d.get("/api/v1/stats")
            ms = (time.perf_counter() - t0) * 1000.0
            j = r.json()
            ok = r.status_code == 200 and "subscribers" in j
            add("daemon_stats_v1", ok, f"keys={list(j.keys())[:5]}", ms)
        except Exception as e:
            add("daemon_stats_v1", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            r1 = client_d.post("/api/v1/simulation/start")
            r2 = client_d.post(
                "/api/v1/simulation/attack",
                json={"type": "can-internal"},
            )
            r3 = client_d.post("/api/v1/simulation/stop")
            ms = (time.perf_counter() - t0) * 1000.0
            ok = (
                r1.status_code == 200
                and r2.status_code == 200
                and r3.status_code == 200
                and r1.json().get("status") == "started"
                and r2.json().get("status") == "attack_launched"
                and r3.json().get("status") == "stopped"
            )
            add("daemon_simulation_cycle", ok, f"start={r1.status_code} attack={r2.status_code} stop={r3.status_code}", ms)
        except Exception as e:
            add("daemon_simulation_cycle", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            r = client_d.post(
                "/api/v1/simulation/attack",
                content=b"{not json",
                headers={"Content-Type": "application/json"},
            )
            ms = (time.perf_counter() - t0) * 1000.0
            ok = r.status_code == 400
            add("daemon_attack_invalid_json", ok, f"HTTP {r.status_code} (expect 400)", ms)
        except Exception as e:
            add("daemon_attack_invalid_json", False, str(e), 0.0)

    # --- bridge ---
    if not bridge_ok:
        msg = f"ml_bridge unreachable — {bridge_detail}"
        add("bridge_reachable", False, msg, 0.0, skip=not strict)
        if strict:
            for cid in (
                "bridge_health",
                "bridge_enrich_minimal",
                "bridge_enrich_full",
                "bridge_enrich_flow_10x80",
            ):
                add(cid, False, msg, 0.0)
    else:
        t0 = time.perf_counter()
        try:
            r = client_b.get("/health")
            ms = (time.perf_counter() - t0) * 1000.0
            j = r.json()
            ok = r.status_code == 200 and j.get("status") == "ok" and j.get("service")
            add("bridge_health", ok, f"can_backend={j.get('can_backend')}", ms)
        except Exception as e:
            add("bridge_health", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            r = client_b.post("/v1/enrich", json=enrich_body_minimal())
            ms = (time.perf_counter() - t0) * 1000.0
            j = r.json()
            ok = (
                r.status_code == 200
                and "fusion_summary" in j
                and "attack_chain" in j
                and isinstance(j["attack_chain"], list)
            )
            add("bridge_enrich_minimal", ok, f"keys fusion+chain", ms)
        except Exception as e:
            add("bridge_enrich_minimal", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            r = client_b.post("/v1/enrich", json=enrich_body_full())
            ms = (time.perf_counter() - t0) * 1000.0
            j = r.json()
            cm = j.get("can_ml")
            ok = r.status_code == 200 and cm is not None and "class_name" in cm
            src = cm.get("source", "") if isinstance(cm, dict) else ""
            add("bridge_enrich_full", ok, f"can_ml.source={src}", ms)
        except Exception as e:
            add("bridge_enrich_full", False, str(e), 0.0)

        t0 = time.perf_counter()
        try:
            body = enrich_body_minimal()
            body["flow_sequence_10x80"] = flow_10x80()
            r = client_b.post("/v1/enrich", json=body)
            ms = (time.perf_counter() - t0) * 1000.0
            j = r.json()
            em = j.get("ethernet_ml")
            ok = r.status_code == 200 and em is not None and em.get("label") is not None
            add("bridge_enrich_flow_10x80", ok, f"eth label={em.get('label')}", ms)
        except Exception as e:
            add("bridge_enrich_flow_10x80", False, str(e), 0.0)

    return results


def run_latency(
    client_d: httpx.Client,
    client_b: httpx.Client,
    daemon_ok: bool,
    bridge_ok: bool,
    iterations: int,
    warmup: int,
) -> List[LatencyResult]:
    out: List[LatencyResult] = []

    def push(
        lid: str,
        endpoint: str,
        method: str,
        fn: Callable[[], None],
        enabled: bool,
    ) -> None:
        if not enabled:
            return
        samples, errs = measure_latency(fn, iterations, warmup)
        mean, mn, mx, p50, p95, p99 = summarize_times(samples)
        out.append(
            LatencyResult(
                id=lid,
                endpoint=endpoint,
                method=method,
                iterations=iterations,
                warmup=warmup,
                mean_ms=mean,
                min_ms=mn,
                max_ms=mx,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                errors=errs,
            )
        )

    push(
        "lat_daemon_health",
        "/api/v1/health",
        "GET",
        lambda: client_d.get("/api/v1/health").raise_for_status(),
        daemon_ok,
    )
    push(
        "lat_daemon_sim_start",
        "/api/v1/simulation/start",
        "POST",
        lambda: client_d.post("/api/v1/simulation/start").raise_for_status(),
        daemon_ok,
    )
    push(
        "lat_bridge_health",
        "/health",
        "GET",
        lambda: client_b.get("/health").raise_for_status(),
        bridge_ok,
    )
    push(
        "lat_bridge_enrich_minimal",
        "/v1/enrich",
        "POST",
        lambda: client_b.post("/v1/enrich", json=enrich_body_minimal()).raise_for_status(),
        bridge_ok,
    )
    push(
        "lat_bridge_enrich_full",
        "/v1/enrich",
        "POST",
        lambda: client_b.post("/v1/enrich", json=enrich_body_full()).raise_for_status(),
        bridge_ok,
    )

    if daemon_ok:
        try:
            client_d.post("/api/v1/simulation/stop")
        except Exception:
            pass

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="REAL-IDS daemon + ml_bridge integration tests")
    ap.add_argument("--daemon-url", default="http://127.0.0.1:8080")
    ap.add_argument("--bridge-url", default="http://127.0.0.1:5055")
    ap.add_argument("--latency-iterations", type=int, default=30)
    ap.add_argument("--latency-warmup", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Treat unreachable services as fail (default: skip daemon/bridge blocks)",
    )
    ap.add_argument("--no-latency", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print probe diagnostics to stderr")
    ap.add_argument(
        "--carhack-data",
        type=Path,
        default=None,
        help="CarHackData dir (default: <VCEI>/CarHackData)",
    )
    ap.add_argument("--classification-windows", type=int, default=400, help="Max windows per class for accuracy eval")
    ap.add_argument("--classification-stride", type=int, default=5)
    ap.add_argument("--classification-max-lines", type=int, default=120_000)
    ap.add_argument("--no-classification", action="store_true", help="Skip offline CarHack CNN accuracy")
    ap.add_argument("--skew-iterations", type=int, default=50_000, help="detect() calls for clock-skew timing")
    ap.add_argument("--skew-warmup", type=int, default=5_000)
    ap.add_argument("--skew-threshold-ms", type=float, default=15.0)
    ap.add_argument("--no-skew-bench", action="store_true", help="Skip clock-skew micro-benchmark")
    args = ap.parse_args()

    d_base = normalize_client_base(args.daemon_url)
    b_base = normalize_client_base(args.bridge_url)

    daemon_ok, d_err = http_probe(d_base, "/api/v1/health")
    bridge_ok, b_err = http_probe(b_base, "/health")

    if args.verbose or not daemon_ok or not bridge_ok:
        print(f"[probe] daemon  {d_base}/api/v1/health -> {'OK' if daemon_ok else d_err}", file=sys.stderr)
        print(f"[probe] bridge   {b_base}/health -> {'OK' if bridge_ok else b_err}", file=sys.stderr)

    timeout = httpx.Timeout(args.timeout)

    report = Report(
        started_at=now_iso(),
        daemon_url=d_base,
        bridge_url=b_base,
        daemon_probe_error=d_err if not daemon_ok else "",
        bridge_probe_error=b_err if not bridge_ok else "",
    )

    with httpx.Client(base_url=d_base, timeout=timeout, trust_env=False) as client_d, httpx.Client(
        base_url=b_base, timeout=timeout, trust_env=False
    ) as client_b:
        report.correctness = run_correctness(
            client_d, client_b, daemon_ok, bridge_ok, args.strict, d_err, b_err
        )
        if not args.no_latency:
            report.latency = run_latency(
                client_d,
                client_b,
                daemon_ok,
                bridge_ok,
                args.latency_iterations,
                args.latency_warmup,
            )

    vcei_root = Path(__file__).resolve().parents[3]
    carhack_data = args.carhack_data if args.carhack_data is not None else vcei_root / "CarHackData"

    if not args.no_classification:
        from metrics_ml import run_classification_eval

        report.classification = run_classification_eval(
            data_root=carhack_data,
            max_windows_per_class=args.classification_windows,
            stride=args.classification_stride,
            max_lines_per_file=args.classification_max_lines,
        )
    if not args.no_skew_bench:
        from metrics_ml import run_skew_latency

        report.clock_skew = run_skew_latency(
            iterations=args.skew_iterations,
            warmup=args.skew_warmup,
            skew_threshold_ms=args.skew_threshold_ms,
        )

    args.output.mkdir(parents=True, exist_ok=True)
    report.write(args.output)

    # Console summary
    sc = report.counts()
    print(f"Report written to {args.output / 'summary.json'} and summary.txt")
    print(f"Correctness: pass={sc['pass']} fail={sc['fail']} skip={sc['skip']}")
    for r in report.correctness:
        print(f"  [{r.status:4}] {r.id}: {r.detail}")
    if report.latency:
        print("Latency:")
        for r in report.latency:
            print(
                f"  {r.id}: mean={r.mean_ms:.2f}ms p95={r.p95_ms:.2f}ms max={r.max_ms:.2f}ms err={r.errors}"
            )
    if report.classification and report.classification.get("enabled"):
        print(
            f"CarHack accuracy: {report.classification.get('accuracy', 0):.4f} "
            f"(n={report.classification.get('n_samples', 0)})"
        )
    elif report.classification:
        print(f"CarHack accuracy: skipped — {report.classification.get('error', '')}")
    if report.clock_skew and report.clock_skew.get("enabled"):
        print(
            f"Clock-skew detect: mean {report.clock_skew.get('mean_ns_per_detect', 0):.0f} ns/call "
            f"(p95 {report.clock_skew.get('p95_ns', 0):.0f} ns)"
        )
    elif report.clock_skew:
        print(f"Clock-skew bench: skipped — {report.clock_skew.get('error', '')}")

    failed = sc["fail"] > 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
