"""
REAL-IDS ML fusion bridge:
- IntrusionDetectNet (CNN+Transformer) for Ethernet flow sequence (10x80).
- CAN: CarHackData CNN (models/carhack_can_clf.pth) if present, else SupCon+linear from supervised-main.

Run:  uvicorn server:app --host 0.0.0.0 --port 5055

Env:
  ETH_MODEL_PATH   path to transformer_ids_model.pth (under IntrusionDetectNet PycharmProjects)
  CARHACK_MODEL_PATH  optional override for CarHack CNN weights (default: ml_bridge/models/carhack_can_clf.pth)
  CAN_CNN64_MODEL_PATH  optional 64×9 CAN CNN (default: integration/can_cnn_64x9/artifacts/best_model.pth); takes priority over CarHack/SupCon
  CAN_CNN64_META_PATH  optional preprocess_meta.json (default: same directory as CAN_CNN64_MODEL_PATH)
  CAN_PRETRAINED_PATH  directory with ckpt_epoch_*.pth and ckpt_class_epoch_*.pth (used only if 64×9 and CarHack models missing)
  CAN_CKPT         checkpoint epoch number (default 200)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chain_builder import (
    CAN_CLASS_NAMES,
    build_attack_chain,
    fusion_summary_text,
)
from eth_intrusion_net import EthIntrusionNet
from can_supcon_infer import CanSupconInfer
from carhack_infer import CarHackCanInfer
from can_cnn64_infer import CanCnn64Infer
from features import can_packets_to_matrix_29x29, can_packets_to_matrix_64x9, eth_packets_to_sequence_10x80

app = FastAPI(title="REAL-IDS ML Bridge", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_eth: Optional[EthIntrusionNet] = None
_can: Optional[CanSupconInfer] = None
_carhack: Optional[CarHackCanInfer] = None
_cnn64: Optional[CanCnn64Infer] = None


def _packet_attackish(p: Dict[str, Any]) -> bool:
    return bool(p.get("isAttack") or p.get("synthetic_attack_flag"))


def _heuristic_eth_ml(eth_ctx: List[Dict[str, Any]]) -> Dict[str, Any]:
    """When PyTorch model is missing: infer from REAL-IDS simulation flags only."""
    susp = any(_packet_attackish(p) for p in eth_ctx) if eth_ctx else False
    return {
        "label": "ANOMALY" if susp else "BENIGN",
        "probability_anomaly": 0.88 if susp else 0.12,
        "source": "heuristic_real_ids_flags",
        "note": "No transformer_ids_model.pth loaded; label from Ethernet isAttack/synthetic_attack_flag in fusion window.",
    }


def _heuristic_can_ml(trigger: Dict[str, Any], hist: List[Dict[str, Any]]) -> Dict[str, Any]:
    """When SupCon checkpoint missing: infer malicious window from simulation CAN flags."""
    atk = _packet_attackish(trigger)
    if hist:
        atk = atk or any(_packet_attackish(h) for h in hist[-12:])
    if atk:
        return {
            "class_id": -2,
            "class_name": "UnclassifiedMalicious (heuristic)",
            "confidence": 0.78,
            "source": "heuristic_real_ids_flags",
            "note": "No CAN checkpoint; inferred from CAN isAttack/synthetic_attack_flag in REAL-IDS simulation.",
        }
    return {
        "class_id": -1,
        "class_name": "MODEL_UNAVAILABLE",
        "confidence": 0.0,
        "source": "stub",
        "note": "No CAN checkpoint and no attack flags in recent window.",
    }


def get_eth() -> EthIntrusionNet:
    global _eth
    if _eth is None:
        default_p = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "IntrusionDetectNet-CNN-Transformer-main",
            "PycharmProjects",
            "transformer_ids_model.pth",
        )
        path = os.environ.get("ETH_MODEL_PATH", os.path.normpath(default_p))
        _eth = EthIntrusionNet(path if os.path.isfile(path) else None)
    return _eth


def get_can() -> CanSupconInfer:
    global _can
    if _can is None:
        p = os.environ.get("CAN_PRETRAINED_PATH", "").strip()
        ckpt = int(os.environ.get("CAN_CKPT", "200"))
        dev = "cuda" if os.environ.get("ML_BRIDGE_CUDA", "") == "1" else "cpu"
        _can = CanSupconInfer(p if p else None, ckpt=ckpt, device=dev)
    return _can


def get_carhack_can() -> CarHackCanInfer:
    global _carhack
    if _carhack is None:
        dev = "cuda" if os.environ.get("ML_BRIDGE_CUDA", "") == "1" else "cpu"
        p = os.environ.get("CARHACK_MODEL_PATH", "").strip()
        _carhack = CarHackCanInfer(p if p else None, device=dev)
    return _carhack


def get_can_cnn64() -> CanCnn64Infer:
    global _cnn64
    if _cnn64 is None:
        dev = "cuda" if os.environ.get("ML_BRIDGE_CUDA", "") == "1" else "cpu"
        wp = os.environ.get("CAN_CNN64_MODEL_PATH", "").strip()
        mp = os.environ.get("CAN_CNN64_META_PATH", "").strip()
        _cnn64 = CanCnn64Infer(wp if wp else None, meta_path=mp if mp else None, device=dev)
    return _cnn64


def _default_can_cnn64_weights() -> str:
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "can_cnn_64x9",
            "artifacts",
            "best_model.pth",
        )
    )


class EnrichRequest(BaseModel):
    real_ids_classification: str = ""
    can_skew_triggered: bool = True
    trigger_can: Dict[str, Any] = Field(default_factory=dict)
    ethernet_context: List[Dict[str, Any]] = Field(default_factory=list)
    can_history: List[Dict[str, Any]] = Field(default_factory=list)
    flow_sequence_10x80: Optional[List[List[float]]] = None


def _default_eth_path() -> str:
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "IntrusionDetectNet-CNN-Transformer-main",
            "PycharmProjects",
            "transformer_ids_model.pth",
        )
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    eth = get_eth()
    can = get_can()
    ch = get_carhack_can()
    c64 = get_can_cnn64()
    eth_path = os.environ.get("ETH_MODEL_PATH", _default_eth_path())
    ch_path = os.environ.get("CARHACK_MODEL_PATH", "").strip()
    if not ch_path:
        ch_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "models", "carhack_can_clf.pth")
        )
    c64_path = os.environ.get("CAN_CNN64_MODEL_PATH", "").strip() or _default_can_cnn64_weights()
    if c64.model is not None:
        can_backend = "can_cnn64"
    elif ch.model is not None:
        can_backend = "carhack_cnn"
    else:
        can_backend = "supcon_or_stub"
    return {
        "status": "ok",
        "service": "real-ids-ml-bridge",
        "eth_model_loaded": eth.model is not None,
        "can_cnn64_loaded": c64.model is not None,
        "can_cnn64_model_path_resolved": c64_path,
        "can_cnn64_meta_dt_max_ms": c64.dt_max_ms if c64.model else None,
        "carhack_can_loaded": ch.model is not None,
        "carhack_model_path_resolved": ch_path,
        "can_model_loaded": can.model is not None,
        "can_backend": can_backend,
        "eth_model_path_resolved": eth_path,
        "eth_weights_file_exists": os.path.isfile(eth_path),
        "can_pretrained_path": os.environ.get("CAN_PRETRAINED_PATH", ""),
        "can_ckpt": int(os.environ.get("CAN_CKPT", "200")),
        "hint": "CAN: 64×9 CNN if can_cnn64_loaded else CarHack else SupCon. Daemon should send ≥64 CAN frames in can_history.",
    }


@app.post("/v1/enrich")
def enrich(body: EnrichRequest) -> Dict[str, Any]:
    eth_ctx = body.ethernet_context
    can_hist = body.can_history

    # Ethernet ML
    eth_ml: Optional[Dict[str, Any]] = None
    if body.flow_sequence_10x80 is not None and len(body.flow_sequence_10x80) == 10:
        x = np.array(body.flow_sequence_10x80, dtype=np.float32)
        if x.shape == (10, 80):
            label, prob, meta = get_eth().predict(x)
            eth_ml = {
                "label": label,
                "probability_anomaly": prob,
                **{k: v for k, v in meta.items() if k != "logits"},
            }
    if eth_ml is None and eth_ctx:
        x = eth_packets_to_sequence_10x80(eth_ctx)
        label, prob, meta = get_eth().predict(x)
        eth_ml = {
            "label": label,
            "probability_anomaly": prob,
            "note": "features_from_real_ids_stub",
            **{k: v for k, v in meta.items() if k != "logits"},
        }

    if eth_ml and eth_ml.get("label") == "MODEL_UNAVAILABLE" and eth_ctx:
        eth_ml = _heuristic_eth_ml(eth_ctx)

    # CAN ML — prefer 64×9 sliding-window CNN, then CarHack, then SupCon
    can_ml: Optional[Dict[str, Any]] = None
    if can_hist:
        c64 = get_can_cnn64()
        ch = get_carhack_can()
        meta: Dict[str, Any] = {}
        if c64.model is not None:
            mat64 = can_packets_to_matrix_64x9(can_hist, c64.dt_max_ms)
            cid, cname, conf, meta = c64.predict(mat64)
        elif ch.model is not None:
            mat = can_packets_to_matrix_29x29(can_hist)
            cid, cname, conf, meta = ch.predict_matrix(mat)
        else:
            mat = can_packets_to_matrix_29x29(can_hist)
            cid, cname, conf, meta = get_can().predict_matrix(mat)
        can_ml = {
            "class_id": cid,
            "class_name": cname if cid >= 0 else "MODEL_UNAVAILABLE",
            "confidence": conf,
            **{k: v for k, v in meta.items() if k not in ("probs", "class_names")},
        }
        if "class_names" in meta:
            can_ml["class_names_order"] = list(meta["class_names"])
        if "probs" in meta:
            names = list(meta.get("class_names", CAN_CLASS_NAMES))
            can_ml["class_probs"] = {
                names[i]: float(meta["probs"][i])
                for i in range(min(len(names), len(meta["probs"])))
            }

    if can_ml and can_ml.get("class_id") == -1:
        can_ml = _heuristic_can_ml(body.trigger_can, can_hist)
    elif can_ml is None and (body.trigger_can or can_hist):
        can_ml = _heuristic_can_ml(body.trigger_can, can_hist)

    eth_anomaly = bool(eth_ml and eth_ml.get("label") == "ANOMALY")
    fusion_type = body.real_ids_classification
    can_name = can_ml.get("class_name") if can_ml else None
    can_real_ml = can_name not in (None, "MODEL_UNAVAILABLE", "UnclassifiedMalicious (heuristic)")

    if eth_anomaly and can_ml and can_real_ml:
        detailed = f"Cross-domain: Ethernet anomaly + CAN attack class '{can_ml['class_name']}'"
    elif eth_anomaly and can_ml and can_name == "UnclassifiedMalicious (heuristic)":
        detailed = f"Cross-domain (heuristic): Ethernet anomaly flags + CAN attack flags; REAL-IDS: {fusion_type}"
    elif eth_anomaly:
        detailed = "Ethernet-layer anomaly dominant; CAN timing IDS corroborates bus stress."
    elif can_ml and can_real_ml:
        detailed = f"CAN-centric: ML class '{can_ml['class_name']}' with REAL-IDS fusion '{fusion_type}'"
    elif can_ml and can_name == "UnclassifiedMalicious (heuristic)":
        detailed = f"CAN attack flags (heuristic, no trained CAN classifier); REAL-IDS: {fusion_type}"
    else:
        detailed = f"Alert per REAL-IDS rules: {fusion_type}"

    summary = fusion_summary_text(
        real_ids_classification=body.real_ids_classification,
        eth_anomaly=eth_anomaly,
        can_anomaly_class=can_ml.get("class_name") if can_ml else None,
        eth_label=eth_ml.get("label") if eth_ml else None,
    )

    chain = build_attack_chain(
        real_ids_classification=body.real_ids_classification,
        can_skew_triggered=body.can_skew_triggered,
        eth_context=eth_ctx,
        eth_ml=eth_ml,
        can_ml=can_ml,
        fusion_summary=summary,
    )

    resp_can_names = CAN_CLASS_NAMES
    if can_ml and can_ml.get("class_names_order"):
        resp_can_names = list(can_ml["class_names_order"])

    return {
        "fusion_attack_type": detailed,
        "fusion_summary": summary,
        "attack_chain": chain,
        "ethernet_ml": eth_ml,
        "can_ml": can_ml,
        "can_class_names": resp_can_names,
        "eth_model_note": (
            "IntrusionDetectNet is binary (BENIGN/ANOMALY) on 10x80 flow windows. "
            "If source is heuristic_real_ids_flags, no .pth is loaded — see MODELS.md. "
            "Multi-class Ethernet needs retraining."
        ),
    }
