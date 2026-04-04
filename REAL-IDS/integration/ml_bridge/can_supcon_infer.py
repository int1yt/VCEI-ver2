"""Load backend-main supervised TransferModel (5-class CAN)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

_VCEI_ROOT = Path(__file__).resolve().parents[3]
_SUPERVISED = _VCEI_ROOT / "backend-main" / "backend-main" / "ids" / "supervised-main"

CAN_CLASS_NAMES = ["Normal", "DoS", "Fuzzy", "gear", "RPM"]


def _ensure_supervised_path() -> None:
    p = str(_SUPERVISED)
    if p not in sys.path:
        sys.path.insert(0, p)


class CanSupconInfer:
    def __init__(
        self,
        pretrained_path: Optional[str],
        ckpt: int = 200,
        device: str = "cpu",
    ) -> None:
        self.model = None
        self.device = device
        self.pretrained_path = pretrained_path or ""
        if not pretrained_path or not os.path.isdir(pretrained_path):
            return
        try:
            _ensure_supervised_path()
            from test_model import load_model  # type: ignore

            args = SimpleNamespace(
                pretrained_model="supcon",
                pretrained_path=pretrained_path,
                ckpt=ckpt,
                data_path=str(_SUPERVISED / "Data"),
                car_model=None,
                window_size=29,
                strided=29,
                batch_size=1,
                num_workers=0,
                trial_id=1,
            )
            self.model = load_model(args, verbose=False, is_cuda=(device == "cuda"))
            self.model.eval()
        except Exception as e:
            print(f"[CanSupconInfer] load failed: {e}")
            self.model = None

    def predict_matrix(self, mat: np.ndarray) -> Tuple[int, str, float, Dict[str, Any]]:
        """
        mat: (29, 29) float — matches CANDataset id_seq layout (simplified).
        """
        if self.model is None:
            return -1, "MODEL_UNAVAILABLE", 0.0, {"source": "stub"}
        # ResNet expects NCHW; in_channel=1 -> (1, 1, 29, 29)
        x = torch.from_numpy(mat.astype(np.float32)).view(1, 1, 29, 29).to(self.device)
        with torch.no_grad():
            out = self.model(x)
            prob = torch.softmax(out, dim=1)[0]
            cid = int(prob.argmax().item())
            conf = float(prob[cid].item())
        return cid, CAN_CLASS_NAMES[cid], conf, {"source": "supcon_transfer", "probs": prob.cpu().tolist()}
