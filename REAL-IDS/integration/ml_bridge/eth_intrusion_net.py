"""Load IntrusionDetectNet TransformerClassifier (binary flow anomaly)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

# Resolve IntrusionDetectNet repo (sibling under VCEI)
_VCEI_ROOT = Path(__file__).resolve().parents[3]
_INTRUSION_ROOT = _VCEI_ROOT / "IntrusionDetectNet-CNN-Transformer-main" / "PycharmProjects"


class EthIntrusionNet:
    def __init__(self, model_path: Optional[str], device: str = "cpu") -> None:
        self.model = None
        self.device = device
        self.model_path = model_path or ""
        if not model_path or not os.path.isfile(model_path):
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("idn_model", str(_INTRUSION_ROOT / "model.py"))
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            TransformerClassifier = mod.TransformerClassifier
            m = TransformerClassifier(ninp=80, nhead=4, nhid=1024, nlayers=3)
            try:
                state = torch.load(model_path, map_location=device, weights_only=False)
            except TypeError:
                state = torch.load(model_path, map_location=device)
            m.load_state_dict(state)
            m.eval()
            m.to(device)
            self.model = m
        except Exception as e:
            print(f"[EthIntrusionNet] load failed: {e}")
            self.model = None

    def predict(self, x: np.ndarray) -> Tuple[str, float, Dict[str, Any]]:
        """
        x: shape (10, 80) float32
        Returns (label_name, p_anomaly, meta)
        """
        if self.model is None:
            return "MODEL_UNAVAILABLE", 0.0, {"source": "stub"}
        t = torch.from_numpy(x.astype(np.float32)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model.forward2(t)
            prob = torch.sigmoid(logits)[0, 1].item()
        pred = 1 if prob > 0.5 else 0
        label = "ANOMALY" if pred == 1 else "BENIGN"
        return label, prob, {"source": "IntrusionDetectNet", "logits": logits.cpu().tolist()}
