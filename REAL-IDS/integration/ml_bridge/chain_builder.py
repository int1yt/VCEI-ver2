"""Build human-readable attack chain from REAL-IDS context + ML outputs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CAN_CLASS_NAMES = ["Normal", "DoS", "Fuzzy", "gear", "RPM"]


def build_attack_chain(
    *,
    real_ids_classification: str,
    can_skew_triggered: bool,
    eth_context: List[Dict[str, Any]],
    eth_ml: Optional[Dict[str, Any]],
    can_ml: Optional[Dict[str, Any]],
    fusion_summary: str,
) -> List[Dict[str, Any]]:
    """Ordered steps for dashboard / SIEM. Each step has time_order, stage, detail."""
    steps: List[Dict[str, Any]] = []
    order = 0

    def add(stage: str, detail: str) -> None:
        nonlocal order
        order += 1
        steps.append({"order": order, "stage": stage, "detail": detail})

    add("perception", "Ethernet ring buffer captured frames in [CAN_ts-500ms, CAN_ts+100ms].")
    if eth_context:
        atk = sum(1 for p in eth_context if p.get("isAttack") or p.get("synthetic_attack_flag"))
        add(
            "ethernet_observation",
            f"{len(eth_context)} frame(s) in fusion window; {atk} marked suspicious in simulation/metadata.",
        )

    if eth_ml:
        name = eth_ml.get("label", "unknown")
        p = eth_ml.get("probability_anomaly")
        src = eth_ml.get("source", "model")
        prob_s = f"{p:.4f}" if isinstance(p, (int, float)) else str(p)
        eth_title = "IntrusionDetectNet" if src == "IntrusionDetectNet" else f"Ethernet ({src})"
        add(
            "ethernet_ml",
            f"{eth_title}: {name}, P(anomaly)={prob_s}.",
        )
    else:
        add("ethernet_ml", "IntrusionDetectNet: not run (no model or no sequence).")

    if can_skew_triggered:
        add("can_timing_ids", "REAL-IDS clock-skew IDS: inter-arrival deviation exceeds learned baseline.")
    else:
        add("can_timing_ids", "REAL-IDS: CAN timing check (trigger packet associated with alert).")

    if can_ml:
        cid = can_ml.get("class_id")
        cname = can_ml.get("class_name", CAN_CLASS_NAMES[cid] if isinstance(cid, int) and 0 <= cid < len(CAN_CLASS_NAMES) else "?")
        conf = can_ml.get("confidence")
        cs = f"{conf:.4f}" if isinstance(conf, (int, float)) else str(conf)
        csrc = can_ml.get("source", "")
        if csrc == "carhack_cnn":
            can_title = "CarHackData CNN"
        elif csrc == "supcon_transfer":
            can_title = "backend supervised (SupCon+linear)"
        elif csrc == "heuristic_real_ids_flags":
            can_title = "CAN (heuristic from REAL-IDS flags)"
        else:
            can_title = f"CAN ({csrc or 'unknown'})"
        add(
            "can_ml",
            f"{can_title}: class={cname} (id={cid}), confidence={cs}.",
        )
    else:
        add("can_ml", "CAN classifier: not run (no checkpoint or tensor build failed).")

    add("rule_fusion", f"REAL-IDS CentralProcessor: {real_ids_classification}")
    add("correlation_summary", fusion_summary)
    return steps


def fusion_summary_text(
    *,
    real_ids_classification: str,
    eth_anomaly: bool,
    can_anomaly_class: Optional[str],
    eth_label: Optional[str],
) -> str:
    parts = []
    if eth_anomaly or (eth_label and eth_label.upper() not in ("BENIGN", "NORMAL")):
        parts.append("Ethernet side shows malicious or anomalous indicators.")
    else:
        parts.append("Ethernet side: no strong ML anomaly (or benign).")
    if can_anomaly_class and can_anomaly_class not in ("Normal", "MODEL_UNAVAILABLE"):
        if "heuristic" in str(can_anomaly_class).lower():
            parts.append(f"CAN (heuristic): {can_anomaly_class}.")
        else:
            parts.append(f"CAN ML suggests attack family: {can_anomaly_class}.")
    elif "CAN timing" in real_ids_classification or "Internal CAN" in real_ids_classification:
        parts.append("CAN timing anomaly consistent with bus-level intrusion or ECU stress.")
    parts.append(f"Rule label: {real_ids_classification}.")
    return " ".join(parts)
