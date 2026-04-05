"""Feature builders: bridge REAL-IDS JSON to model tensors."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

import numpy as np


def eth_packets_to_sequence_10x80(packets: List[Dict[str, Any]]) -> np.ndarray:
    """
    Map last<=10 Ethernet-like dicts to (10, 80). Pads by repeating last row.
    Not equivalent to CIC-IDS77 columns — use for demo wiring; replace with
    real flow stats + StandardScaler from IntrusionDetectNet training pipeline.
    """
    rows: List[np.ndarray] = []
    for p in packets[-10:]:
        row = np.zeros(80, dtype=np.float32)
        row[0] = 1.0 if str(p.get("protocol", "")).upper() == "TCP" else 0.0
        row[1] = float(p.get("length", 0) or 0) / 1500.0
        row[2] = 1.0 if p.get("isAttack") or p.get("synthetic_attack_flag") else 0.0
        row[3] = float(p.get("timestamp", 0) or 0) % 100000 / 100000.0
        sip = str(p.get("srcIp", "0.0.0.0"))
        parts = sip.split(".")
        for i in range(min(4, len(parts))):
            try:
                row[4 + i] = int(parts[i]) / 255.0
            except ValueError:
                pass
        h = hashlib.sha256(sip.encode()).digest()
        for i in range(8, 80):
            row[i] = h[i % 32] / 255.0
        rows.append(row)
    if not rows:
        return np.zeros((10, 80), dtype=np.float32)
    while len(rows) < 10:
        rows.insert(0, rows[0].copy())
    return np.stack(rows[-10:], axis=0)


def can_packets_to_matrix_29x29(packets: List[Dict[str, Any]]) -> np.ndarray:
    """
    Build (29, 29) float matrix from up to 29 CAN dicts {id, data}.
    Row t uses CAN ID bits (11) + data nibbles projected into 29 dims.
    """
    mat = np.zeros((29, 29), dtype=np.float32)
    if not packets:
        return mat
    seq = packets[-29:]
    while len(seq) < 29:
        seq.insert(0, seq[0] if seq else {"id": "0", "data": "00"})
    for t, p in enumerate(seq[-29:]):
        id_s = str(p.get("id", "0"))
        try:
            if id_s.startswith("0x") or id_s.startswith("0X"):
                cid = int(id_s, 16) & 0x7FF
            else:
                cid = int(id_s, 0) & 0x7FF
        except ValueError:
            cid = 0
        for k in range(min(11, 29)):
            mat[t, k] = float((cid >> k) & 1)
        data_hex = str(p.get("data", "")).replace(" ", "")[:16]
        try:
            for b in range(8):
                if 11 + b >= 29:
                    break
                chunk = data_hex[b * 2 : b * 2 + 2]
                if len(chunk) < 2:
                    break
                byte_v = int(chunk, 16)
                mat[t, min(11 + b, 28)] = (byte_v % 16) / 15.0
        except ValueError:
            pass
    return mat


def _parse_data8_hex(data_hex: str) -> List[int]:
    s = str(data_hex).replace(" ", "")[:16]
    out = [0] * 8
    for b in range(8):
        chunk = s[b * 2 : b * 2 + 2]
        if len(chunk) < 2:
            break
        try:
            out[b] = int(chunk, 16) & 0xFF
        except ValueError:
            out[b] = 0
    return out


def can_packets_to_matrix_64x9(
    packets: List[Dict[str, Any]],
    dt_max_ms: float,
) -> np.ndarray:
    """
    Last 64 CAN dicts {id, data, timestamp} -> (64, 9): bytes/255 + Δt(ms)/dt_max_ms clipped [0,1].
    Timestamps are expected in milliseconds (REAL-IDS daemon).
    """
    mat = np.zeros((64, 9), dtype=np.float32)
    if not packets:
        return mat
    seq = list(packets[-64:])
    while len(seq) < 64:
        seq.insert(0, seq[0] if seq else {"id": "0", "data": "00" * 8, "timestamp": 0})
    seq = seq[-64:]
    dtm = float(dt_max_ms) + 1e-6
    for i, p in enumerate(seq):
        data8 = _parse_data8_hex(str(p.get("data", "")))
        mat[i, :8] = np.array(data8, dtype=np.float32) / 255.0
        if i == 0:
            dt = 0.0
        else:
            try:
                dt = float(p.get("timestamp", 0) or 0) - float(seq[i - 1].get("timestamp", 0) or 0)
            except (TypeError, ValueError):
                dt = 0.0
            if dt < 0:
                dt = 0.0
        mat[i, 8] = min(1.0, max(0.0, dt / dtm))
    return mat
