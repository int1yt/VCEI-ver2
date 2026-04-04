"""CarHack classification accuracy (offline) + clock-skew benchmark — unified dicts for report."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REAL_IDS_ROOT = Path(__file__).resolve().parents[2]
ML_BRIDGE = REAL_IDS_ROOT / "integration" / "ml_bridge"


def _ensure_ml_bridge_path() -> None:
    p = str(ML_BRIDGE)
    if p not in sys.path:
        sys.path.insert(0, p)


def run_classification_eval(
    *,
    data_root: Path,
    max_windows_per_class: int,
    stride: int,
    max_lines_per_file: int,
) -> Dict[str, Any]:
    """
    Load carhack_can_clf.pth via CarHackCanInfer; evaluate on sliding windows (same as training).
    """
    _ensure_ml_bridge_path()
    try:
        import numpy as np
        from carhack_infer import CARHACK_CLASS_NAMES, CarHackCanInfer
        from features import can_packets_to_matrix_29x29
        from train_carhack import collect_windows
    except Exception as e:
        return {"enabled": False, "error": f"import_failed: {e}"}

    out_path = ML_BRIDGE / "models" / "carhack_can_clf.pth"
    if not out_path.is_file():
        return {
            "enabled": False,
            "error": f"no_weights: {out_path}",
        }

    try:
        infer = CarHackCanInfer(str(out_path), device="cpu")
        if infer.model is None:
            return {"enabled": False, "error": "CarHackCanInfer model is None"}
    except Exception as e:
        return {"enabled": False, "error": str(e)}

    try:
        X, y = collect_windows(
            data_root,
            max_lines_per_file=max_lines_per_file,
            stride=stride,
            max_windows_per_class=max_windows_per_class,
            seed=42,
        )
    except Exception as e:
        return {"enabled": False, "error": f"collect_windows: {e}"}

    preds: List[int] = []
    import torch

    infer.model.eval()
    with torch.no_grad():
        for i in range(X.shape[0]):
            mat = X[i]
            cid, _name, _conf, _meta = infer.predict_matrix(mat)
            preds.append(cid)

    preds_a = np.array(preds, dtype=np.int64)
    y = np.asarray(y)
    acc = float((preds_a == y).mean()) if len(y) else 0.0

    n_cls = len(CARHACK_CLASS_NAMES)
    cm = np.zeros((n_cls, n_cls), dtype=np.int64)
    for i in range(len(y)):
        cm[int(y[i]), int(preds_a[i])] += 1

    per_class: Dict[str, Dict[str, float]] = {}
    for c in range(len(CARHACK_CLASS_NAMES)):
        m = y == c
        n = int(m.sum())
        if n == 0:
            per_class[CARHACK_CLASS_NAMES[c]] = {"n": 0, "acc": 0.0}
        else:
            per_class[CARHACK_CLASS_NAMES[c]] = {
                "n": n,
                "acc": float((preds_a[m] == c).mean()),
            }

    return {
        "enabled": True,
        "weights": str(out_path),
        "n_samples": int(len(y)),
        "accuracy": acc,
        "per_class": per_class,
        "class_names": list(CARHACK_CLASS_NAMES),
        "confusion_matrix": cm.tolist(),
        "note": "CarHack CNN on sliding windows; same pipeline as train_carhack.collect_windows",
    }


def run_skew_latency(
    *,
    iterations: int,
    warmup: int,
    skew_threshold_ms: float,
) -> Dict[str, Any]:
    from clock_skew_ref import benchmark_detect_ns

    try:
        mean_ns, min_ns, p95_ns, p99_ns, max_ns = benchmark_detect_ns(
            iterations=iterations,
            warmup=warmup,
            skew_threshold_ms=skew_threshold_ms,
        )
        return {
            "enabled": True,
            "algorithm": "CanClockSkewIds.detect (Python ref, matches cpp/can_ids.cpp)",
            "skew_threshold_ms": skew_threshold_ms,
            "iterations": iterations,
            "warmup": warmup,
            "mean_ns_per_detect": mean_ns,
            "min_ns": min_ns,
            "p95_ns": p95_ns,
            "p99_ns": p99_ns,
            "max_ns": max_ns,
            "mean_us_per_detect": mean_ns / 1000.0,
        }
    except Exception as e:
        return {"enabled": False, "error": str(e)}
