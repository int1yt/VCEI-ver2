"""
Load CrossDomainAligner + GraphTransformerIDS for online attack-chain inference.

Builds T=10 fused vectors from daemon-provided can_history + ethernet_context:
  - Per timestep t: CAN window = last 64 frames ending at offset t (needs ~73+ frames for diversity).
  - Eth: same 10×80 flow matrix from eth_packets_to_sequence_10x80 (shared across steps; CAN sliding provides temporal variation).

Env:
  CHAIN_ALIGNER_PATH   default: integration/cross_domain_chain/artifacts/aligner_encoders.pt
  CHAIN_GRAPH_PATH     default: integration/cross_domain_chain/artifacts/graph_transformer_ids.pt
  CHAIN_DT_MAX_MS      optional override for CAN Δt scaling if no CAN_CNN64 meta (default 1e6)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_CDC = Path(__file__).resolve().parent.parent / "cross_domain_chain"
if str(_CDC) not in sys.path:
    sys.path.insert(0, str(_CDC))

from aligner import CrossDomainAligner  # noqa: E402
from GraphTransformerIDS import GraphTransformerIDS  # noqa: E402

from features import eth_packets_to_sequence_10x80, can_packets_to_matrix_64x9

DEFAULT_CHAIN_NAMES = ["benign", "eth_recon_only", "can_attack_only", "eth_then_can_chain"]
DEFAULT_STAGE_NAMES = [
    "normal",
    "eth_reconnaissance",
    "eth_anomaly",
    "can_presurge",
    "can_attack",
]


def _can_window_ending_at(
    can_hist: List[Dict[str, Any]],
    end_offset: int,
    dt_max_ms: float,
) -> np.ndarray:
    """
    Extract 64 consecutive frames ending at index len-1-end_offset.
    Returns (64, 8) normalized byte values.
    """
    n = len(can_hist)
    if n == 0:
        return np.zeros((64, 8), dtype=np.float32)
    end_idx = n - 1 - end_offset
    start_idx = end_idx - 63
    if start_idx < 0:
        pad_n = -start_idx
        pad = [{"id": "0", "data": "00" * 8, "timestamp": 0}] * pad_n
        seq = pad + can_hist[: end_idx + 1]
    else:
        seq = can_hist[start_idx : end_idx + 1]
    if len(seq) < 64:
        while len(seq) < 64:
            seq.insert(0, seq[0] if seq else {"id": "0", "data": "00" * 8, "timestamp": 0})
    seq = seq[-64:]
    mat = can_packets_to_matrix_64x9(seq, dt_max_ms)
    return mat[:, :8].astype(np.float32)


def build_fused_sequence(
    can_hist: List[Dict[str, Any]],
    ethernet_context: List[Dict[str, Any]],
    dt_max_ms: float,
    aligner: CrossDomainAligner,
    device: torch.device,
    T: int = 10,
) -> torch.Tensor:
    """Returns (1, T, fused_dim)."""
    eth_10x80 = eth_packets_to_sequence_10x80(ethernet_context)
    fused_chunks: List[np.ndarray] = []
    for t in range(T):
        can_64x8 = _can_window_ending_at(can_hist, end_offset=t, dt_max_ms=dt_max_ms)
        c = torch.from_numpy(can_64x8).float().unsqueeze(0).unsqueeze(1).to(device)
        e = torch.from_numpy(eth_10x80).float().unsqueeze(0).to(device)
        with torch.no_grad():
            zc = aligner.encode_can(c)
            ze = aligner.encode_eth(e)
            z = torch.cat([zc, ze], dim=-1)
        fused_chunks.append(z.squeeze(0).cpu().numpy())
    x = np.stack(fused_chunks, axis=0)
    return torch.from_numpy(x).float().unsqueeze(0).to(device)


class AttackChainInfer:
    def __init__(
        self,
        aligner_path: Optional[str],
        graph_path: Optional[str],
        device: str = "cpu",
    ) -> None:
        self.device = torch.device(device)
        self.aligner: Optional[CrossDomainAligner] = None
        self.graph: Optional[GraphTransformerIDS] = None
        self.chain_names: List[str] = list(DEFAULT_CHAIN_NAMES)
        self.stage_names: List[str] = list(DEFAULT_STAGE_NAMES)
        self.fused_dim: int = 256
        self._load(aligner_path, graph_path)

    def _load(self, aligner_path: Optional[str], graph_path: Optional[str]) -> None:
        base = Path(__file__).resolve().parent.parent / "cross_domain_chain" / "artifacts"
        ap = (aligner_path or "").strip() or str(base / "aligner_encoders.pt")
        gp = (graph_path or "").strip() or str(base / "graph_transformer_ids.pt")
        if not Path(ap).is_file() or not Path(gp).is_file():
            return
        try:
            ack = torch.load(ap, map_location=self.device, weights_only=False)
            latent = int(ack.get("latent_dim", 128))
            self.aligner = CrossDomainAligner(latent_dim=latent).to(self.device)
            self.aligner.load_state_dict(ack["state_dict"])
            self.aligner.eval()
            self.fused_dim = latent * 2

            gck = torch.load(gp, map_location=self.device, weights_only=False)
            meta = gck.get("meta") or {}
            nc = int(gck.get("num_chain_classes", 4))
            ns = int(gck.get("num_stages", 5))
            fd = int(gck.get("fused_dim", self.fused_dim))
            self.graph = GraphTransformerIDS(
                d_in=fd,
                d_model=256,
                nhead=8,
                num_layers=4,
                dim_feedforward=512,
                num_chain_classes=nc,
                num_stages=ns,
            ).to(self.device)
            self.graph.load_state_dict(gck["state_dict"])
            self.graph.eval()
            self.chain_names = list(meta.get("chain_names", DEFAULT_CHAIN_NAMES[:nc]))
            self.stage_names = list(meta.get("stage_names", DEFAULT_STAGE_NAMES[:ns]))
            while len(self.chain_names) < nc:
                self.chain_names.append(f"chain_{len(self.chain_names)}")
            while len(self.stage_names) < ns:
                self.stage_names.append(f"stage_{len(self.stage_names)}")
        except Exception as e:
            print(f"[AttackChainInfer] load failed: {e}")
            self.aligner = None
            self.graph = None

    @property
    def ok(self) -> bool:
        return self.aligner is not None and self.graph is not None

    def predict(
        self,
        can_hist: List[Dict[str, Any]],
        ethernet_context: List[Dict[str, Any]],
        dt_max_ms: float,
    ) -> Dict[str, Any]:
        if not self.ok:
            return {
                "source": "unavailable",
                "note": "Set CHAIN_ALIGNER_PATH and CHAIN_GRAPH_PATH to trained artifacts.",
            }
        x = build_fused_sequence(
            can_hist, ethernet_context, dt_max_ms, self.aligner, self.device, T=10
        )
        with torch.no_grad():
            chain_logits, stage_logits = self.graph(x)
            cp = torch.softmax(chain_logits, dim=-1)[0].cpu().numpy()
            sp = torch.softmax(stage_logits, dim=-1)[0].cpu().numpy()
        cid = int(np.argmax(cp))
        cname = self.chain_names[cid] if cid < len(self.chain_names) else str(cid)
        nlab = min(len(self.chain_names), len(cp))
        return {
            "source": "graph_transformer_ids",
            "chain_class_id": cid,
            "chain_name": cname,
            "chain_probs": {self.chain_names[i]: float(cp[i]) for i in range(nlab)},
            "stage_names": self.stage_names,
            "stage_probs_per_timestep": sp.tolist(),
            "fused_timesteps": 10,
            "can_sliding_windows_used": len(can_hist) >= 73,
            "note": "CAN uses 10 end-aligned 64-frame windows when history≥73; else padded.",
        }


def load_dt_max_from_meta(path: Optional[Path]) -> Optional[float]:
    if not path or not path.is_file():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        return float(meta.get("dt_max_ms", 0))
    except Exception:
        return None


def get_attack_chain_infer() -> AttackChainInfer:
    dev = "cuda" if os.environ.get("ML_BRIDGE_CUDA", "") == "1" else "cpu"
    ap = os.environ.get("CHAIN_ALIGNER_PATH", "").strip()
    gp = os.environ.get("CHAIN_GRAPH_PATH", "").strip()
    return AttackChainInfer(ap or None, gp or None, device=dev)
