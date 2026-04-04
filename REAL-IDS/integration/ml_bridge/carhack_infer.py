"""Load CarHackData-trained CNN for CAN (29x29) — same features as features.can_packets_to_matrix_29x29."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

from carhack_model import CarHackCanCNN

CARHACK_CLASS_NAMES = ["Normal", "DoS", "Fuzzy", "gear", "RPM"]


def _default_weights_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "models", "carhack_can_clf.pth")
    )


class CarHackCanInfer:
    def __init__(self, weights_path: Optional[str], device: str = "cpu") -> None:
        self.model: Optional[torch.nn.Module] = None
        self.device = device
        path = (weights_path or "").strip()
        if not path:
            path = _default_weights_path()
        if not path or not os.path.isfile(path):
            return
        try:
            m = CarHackCanCNN(num_classes=len(CARHACK_CLASS_NAMES))
            try:
                state = torch.load(path, map_location=device, weights_only=True)
            except TypeError:
                state = torch.load(path, map_location=device)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            m.load_state_dict(state)
            m.to(device)
            m.eval()
            self.model = m
        except Exception as e:
            print(f"[CarHackCanInfer] load failed: {e}")
            self.model = None

    def predict_matrix(self, mat: np.ndarray) -> Tuple[int, str, float, Dict[str, Any]]:
        if self.model is None:
            return -1, "MODEL_UNAVAILABLE", 0.0, {"source": "stub"}
        x = torch.from_numpy(mat.astype(np.float32)).view(1, 1, 29, 29).to(self.device)
        with torch.no_grad():
            logits = self.model(x)
            prob = torch.softmax(logits, dim=1)[0]
            cid = int(prob.argmax().item())
            conf = float(prob[cid].item())
        return (
            cid,
            CARHACK_CLASS_NAMES[cid],
            conf,
            {"source": "carhack_cnn", "probs": prob.cpu().tolist()},
        )
