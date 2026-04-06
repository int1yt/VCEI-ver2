"""Synthetic Ethernet (10×80) windows for alignment / chain synthesis when no real Eth dataset is wired."""
from __future__ import annotations

import numpy as np


def synthetic_eth_window(
    unified_label: int,
    rng: np.random.Generator,
    steps: int = 10,
    dim: int = 80,
) -> np.ndarray:
    """
    Unified label 0..3 aligned with CAN classes (Normal, DoS, Fuzzy, Spoofing).
    """
    x = rng.normal(0.0, 0.04, size=(steps, dim)).astype(np.float32)
    x[:, 0] = np.clip(rng.normal(0.2, 0.1, steps), 0, 1)
    x[:, 1] = rng.uniform(0.0, 0.3, steps).astype(np.float32)
    if unified_label == 0:
        x[:, 2] = 0.0
        x[:, 3] = rng.uniform(0.0, 0.2, steps).astype(np.float32)
    else:
        x[:, 2] = 1.0
        x[:, 1] = np.clip(x[:, 1] + 0.5, 0, 1)
        x[:, 3] = rng.uniform(0.5, 1.0, steps).astype(np.float32)
    return x
