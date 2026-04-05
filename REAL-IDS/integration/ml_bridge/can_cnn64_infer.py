"""CAN 64×9 CNN inference (artifacts/best_model.pth + preprocess_meta.json)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_CAN_CNN_DIR = Path(__file__).resolve().parent.parent / "can_cnn_64x9"
if str(_CAN_CNN_DIR) not in sys.path:
    sys.path.insert(0, str(_CAN_CNN_DIR))

from model import CAN_CNN  # noqa: E402


class CanCnn64Infer:
    def __init__(self, weights_path: Optional[str], meta_path: Optional[str] = None, device: str = "cpu") -> None:
        self.model: Optional[torch.nn.Module] = None
        self.device = device
        self.class_names: List[str] = []
        self.dt_max_ms: float = 1.0

        wp = (weights_path or "").strip()
        if not wp:
            wp = os.path.normpath(str(_CAN_CNN_DIR / "artifacts" / "best_model.pth"))
        if not os.path.isfile(wp):
            return

        mp = (meta_path or "").strip()
        if not mp:
            mp = str(Path(wp).resolve().parent / "preprocess_meta.json")
        if not os.path.isfile(mp):
            print(f"[CanCnn64Infer] missing preprocess_meta.json next to weights: {mp}")
            return

        try:
            meta = json.loads(Path(mp).read_text(encoding="utf-8"))
            self.dt_max_ms = float(meta.get("dt_max_ms", 1.0))
            self.class_names = list(meta.get("class_names", ["Normal", "DoS", "Fuzzy", "Spoofing"]))
        except Exception as e:
            print(f"[CanCnn64Infer] bad meta: {e}")
            return

        try:
            try:
                ckpt = torch.load(wp, map_location=device, weights_only=False)
            except TypeError:
                ckpt = torch.load(wp, map_location=device)
            if isinstance(ckpt, dict) and "state_dict" in ckpt:
                sd = ckpt["state_dict"]
                nc = int(ckpt.get("num_classes", len(self.class_names)))
                inh = int(ckpt.get("in_h", 64))
                inw = int(ckpt.get("in_w", 9))
            else:
                sd = ckpt
                nc = len(self.class_names)
                inh, inw = 64, 9

            m = CAN_CNN(num_classes=nc, in_height=inh, in_width=inw).to(device)
            m.load_state_dict(sd)
            m.eval()
            self.model = m
        except Exception as e:
            print(f"[CanCnn64Infer] load failed: {e}")
            self.model = None

    def predict(self, mat: np.ndarray) -> Tuple[int, str, float, Dict[str, Any]]:
        if self.model is None or mat.shape != (64, 9):
            return -1, "MODEL_UNAVAILABLE", 0.0, {"source": "stub"}
        x = torch.from_numpy(mat.astype(np.float32)).view(1, 1, 64, 9).to(self.device)
        with torch.no_grad():
            logits = self.model(x)
            prob = torch.softmax(logits, dim=1)[0]
            cid = int(prob.argmax().item())
            conf = float(prob[cid].item())
        cname = self.class_names[cid] if 0 <= cid < len(self.class_names) else str(cid)
        return (
            cid,
            cname,
            conf,
            {
                "source": "can_cnn64",
                "probs": prob.cpu().tolist(),
                "class_names": self.class_names,
            },
        )
