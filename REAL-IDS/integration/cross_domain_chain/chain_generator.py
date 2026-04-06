r"""
Synthetic "pseudo-joint" attack-chain dataset for training GraphTransformerIDS.

Rules (examples):
  - Type 0: all timesteps = normal CAN + normal Eth
  - Type 1: early timesteps = Eth reconnaissance pattern, CAN stays normal
  - Type 2: CAN attack windows, Eth benign
  - Type 3: Eth scan in first K steps, then within remaining steps switch to CAN DoS (cross-domain chain)

Noise: random substitution of timesteps with normal traffic.

Outputs chain_dataset.pt with:
  sequences: (N, T, fused_dim)
  chain_labels: (N,)
  stage_labels: (N, T)  # per-timestep stage id
  meta: dict

Requires trained CrossDomainAligner weights to map (64×8) + (10×80) → concat(z_can, z_eth).
If --no-aligner, uses random linear projection (debug only).

Does not modify can_cnn_64x9 preprocess outputs (read-only).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from aligner import CrossDomainAligner
from synthetic_eth import synthetic_eth_window

# Chain scenario classes (GraphTransformerIDS chain head)
CHAIN_NAMES = [
    "benign",
    "eth_recon_only",
    "can_attack_only",
    "eth_then_can_chain",
]

# Per-timestep attack stage (probability head targets argmax)
STAGE_NAMES = [
    "normal",
    "eth_reconnaissance",
    "eth_anomaly",
    "can_presurge",
    "can_attack",
]


def sample_can_window(
    X: np.ndarray,
    y: np.ndarray,
    label: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Random window (64, 8) from class."""
    idx = np.where(y == label)[0]
    if len(idx) == 0:
        return np.zeros((64, 8), dtype=np.float32)
    j = int(rng.choice(idx))
    w = X[j]
    if w.shape[-1] >= 8:
        return w[:, :8].astype(np.float32)
    return np.zeros((64, 8), dtype=np.float32)


def load_aligner(path: Path, device: torch.device) -> Tuple[CrossDomainAligner, int]:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    latent = int(ckpt.get("latent_dim", 128))
    m = CrossDomainAligner(latent_dim=latent)
    m.load_state_dict(ckpt["state_dict"])
    m.eval()
    fused_dim = latent * 2
    return m, fused_dim


@torch.no_grad()
def fused_step_fixed(
    aligner: Optional[CrossDomainAligner],
    can_64x8: np.ndarray,
    eth_10x80: np.ndarray,
    device: torch.device,
    proj: torch.Tensor,
    proj_bias: torch.Tensor,
) -> np.ndarray:
    c = torch.from_numpy(can_64x8.copy()).float().unsqueeze(0).unsqueeze(1).to(device)
    e = torch.from_numpy(eth_10x80.copy()).float().unsqueeze(0).to(device)
    if aligner is not None:
        zc = aligner.encode_can(c)
        ze = aligner.encode_eth(e)
        z = torch.cat([zc, ze], dim=-1)
        return z.squeeze(0).cpu().numpy()
    raw = np.concatenate([can_64x8.flatten(), eth_10x80.flatten()])
    t = torch.from_numpy(raw).float().to(device)
    out = t @ proj + proj_bias
    return out.cpu().numpy()


@torch.no_grad()
def build_chain_sample(
    chain_type: int,
    X: np.ndarray,
    y: np.ndarray,
    rng: np.random.Generator,
    aligner: Optional[CrossDomainAligner],
    device: torch.device,
    proj: torch.Tensor,
    proj_bias: torch.Tensor,
    fused_dim: int,
    T: int = 10,
    noise_prob: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns sequence (T, fused_dim) and stage_labels (T,).
    """
    seq = np.zeros((T, fused_dim), dtype=np.float32)
    stages = np.zeros(T, dtype=np.int64)

    def step_with_noise(t: int, can_lab: int, eth_lab: int, st: int) -> None:
        if rng.random() < noise_prob:
            can_lab, eth_lab = 0, 0
            st = 0
        can_w = sample_can_window(X, y, can_lab, rng)
        eth_w = synthetic_eth_window(eth_lab, rng, steps=10)
        seq[t] = fused_step_fixed(aligner, can_w, eth_w, device, proj, proj_bias)
        stages[t] = st

    if chain_type == 0:
        for t in range(T):
            step_with_noise(t, 0, 0, 0)
    elif chain_type == 1:
        for t in range(T):
            step_with_noise(t, 0, 1 if t < T // 2 else 0, 1 if t < T // 2 else 0)
    elif chain_type == 2:
        for t in range(T):
            lab = int(rng.choice([1, 2, 3]))
            step_with_noise(t, lab, 0, 4)
    else:
        # eth_then_can: first half eth anomaly, second half CAN attack
        split = T // 2
        for t in range(T):
            if t < split:
                step_with_noise(t, 0, 1, 1)
            else:
                lab = int(rng.choice([1, 2, 3]))
                step_with_noise(t, lab, 0, 4)

    return seq, stages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--can-x", type=Path, default=None, help="X_train.npy from can_cnn_64x9/processed")
    ap.add_argument("--can-y", type=Path, default=None, help="y_train.npy")
    ap.add_argument(
        "--demo-n",
        type=int,
        default=0,
        help="If >0 and CAN npy missing, use random windows (smoke test only)",
    )
    ap.add_argument("--aligner", type=Path, default=None, help="aligner_encoders.pt")
    ap.add_argument("--no-aligner", action="store_true")
    ap.add_argument("--n-samples", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--T", type=int, default=10, help="sequence length (time steps)")
    ap.add_argument("--noise", type=float, default=0.15)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "artifacts" / "chain_dataset.pt")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1] / "can_cnn_64x9" / "processed"
    can_x = args.can_x or (root / "X_train.npy")
    can_y = args.can_y or (root / "y_train.npy")
    if not can_x.is_file():
        if args.demo_n > 0:
            rng0 = np.random.default_rng(args.seed)
            X = rng0.uniform(0, 1, size=(args.demo_n, 64, 8)).astype(np.float32)
            y = rng0.integers(0, 4, size=(args.demo_n,), dtype=np.int64)
            print(f"[chain_generator] demo mode: random CAN pool {X.shape}")
        else:
            raise SystemExit(f"Missing CAN data: {can_x} (or use --demo-n 5000)")
    else:
        X = np.load(can_x)
        y = np.load(can_y)
    if X.ndim == 3 and X.shape[-1] >= 8:
        X = X[:, :, :8]

    rng = np.random.default_rng(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    aligner: Optional[CrossDomainAligner] = None
    fused_dim = 256
    if args.aligner and args.aligner.is_file() and not args.no_aligner:
        aligner, fused_dim = load_aligner(args.aligner, device)
    # random projection fallback when no aligner (debug)
    proj = torch.randn(64 * 8 + 10 * 80, fused_dim, device=device) * 0.02
    proj_bias = torch.zeros(fused_dim, device=device)

    sequences: List[np.ndarray] = []
    chain_labels: List[int] = []
    stage_list: List[np.ndarray] = []

    chain_types = [0, 1, 2, 3]
    for _ in range(args.n_samples):
        ct = int(rng.choice(chain_types))
        seq, st = build_chain_sample(
            ct,
            X,
            y,
            rng,
            aligner,
            device,
            proj,
            proj_bias,
            fused_dim,
            T=args.T,
            noise_prob=args.noise,
        )
        sequences.append(seq)
        chain_labels.append(ct)
        stage_list.append(st)

    batch_seq = np.stack(sequences, axis=0)
    batch_chain = np.array(chain_labels, dtype=np.int64)
    batch_stages = np.stack(stage_list, axis=0)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "sequences": torch.from_numpy(batch_seq).float(),
            "chain_labels": torch.from_numpy(batch_chain).long(),
            "stage_labels": torch.from_numpy(batch_stages).long(),
            "meta": {
                "chain_names": CHAIN_NAMES,
                "stage_names": STAGE_NAMES,
                "T": args.T,
                "fused_dim": fused_dim,
                "aligner_used": aligner is not None,
                "can_x": str(can_x),
            },
        },
        args.out,
    )

    meta_path = args.out.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "n": args.n_samples,
                "T": args.T,
                "fused_dim": fused_dim,
                "chain_names": CHAIN_NAMES,
                "stage_names": STAGE_NAMES,
                "out": str(args.out),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {args.out} (fused_dim={fused_dim}) meta={meta_path}")


if __name__ == "__main__":
    main()
