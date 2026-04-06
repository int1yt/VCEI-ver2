r"""
Train CrossDomainAligner on CAN windows + synthetic paired Ethernet windows.

Data: can_cnn_64x9/processed/X_train.npy, y_train.npy (uses first 8 columns as 64×8).

Visualizations: artifacts/aligner_loss.png, aligner_latent_tsne.png (subset)

Usage:
  python train_aligner.py --can-dir ../can_cnn_64x9/processed --epochs 20 --out ./artifacts
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.optim as optim
from sklearn.manifold import TSNE
from tqdm import tqdm

from aligner import CrossDomainAligner, contrastive_with_class_labels, mmd_rbf


def make_eth_batch(
    y_batch: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthetic (B,10,80) with unified labels matching CAN batch."""
    from synthetic_eth import synthetic_eth_window

    b = y_batch.shape[0]
    out = np.zeros((b, 10, 80), dtype=np.float32)
    for i in range(b):
        lab = int(y_batch[i])
        out[i] = synthetic_eth_window(lab, rng, steps=10)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--can-dir", type=Path, default=Path(__file__).resolve().parent.parent / "can_cnn_64x9" / "processed")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--lambda-mmd", type=float, default=0.5)
    ap.add_argument("--mmd-sigma", type=float, default=1.0)
    ap.add_argument("--latent-dim", type=int, default=128)
    ap.add_argument("--max-samples", type=int, default=0, help="0 = use all training windows")
    ap.add_argument(
        "--demo-n",
        type=int,
        default=0,
        help="If >0 and X_train.npy missing, use this many random CAN windows (smoke test only)",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "artifacts")
    args = ap.parse_args()

    xp = args.can_dir / "X_train.npy"
    yp = args.can_dir / "y_train.npy"
    if not xp.is_file():
        if args.demo_n > 0:
            rng = np.random.default_rng(args.seed)
            X = rng.uniform(0, 1, size=(args.demo_n, 64, 8)).astype(np.float32)
            y = rng.integers(0, 4, size=(args.demo_n,), dtype=np.int64)
            print(f"[train_aligner] demo mode: random X shape {X.shape}")
        else:
            raise SystemExit(f"Missing {xp}; run can_cnn_64x9/preprocess.py first or pass --demo-n 2000")
    else:
        X = np.load(xp)
        y = np.load(yp)
    if X.ndim != 3:
        raise SystemExit("X_train must be (N, 64, C)")
    X = X[:, :, :8].astype(np.float32)

    if args.max_samples > 0 and len(X) > args.max_samples:
        rng_s = np.random.default_rng(args.seed)
        idx = rng_s.choice(len(X), size=args.max_samples, replace=False)
        X, y = X[idx], y[idx]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(args.seed + 1)

    model = CrossDomainAligner(latent_dim=args.latent_dim).to(device)
    opt = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))

    n = len(X)
    hist_total: list[float] = []
    hist_ctr: list[float] = []
    hist_mmd: list[float] = []

    for epoch in range(args.epochs):
        perm = np.random.default_rng(args.seed + epoch).permutation(n)
        total_l = ctr_l = mmd_l = 0.0
        steps = 0
        for start in tqdm(range(0, n, args.batch_size), desc=f"epoch {epoch+1}/{args.epochs}"):
            idx = perm[start : start + args.batch_size]
            if len(idx) < 2:
                continue
            xb = torch.from_numpy(X[idx]).to(device)
            yb = torch.from_numpy(y[idx].astype(np.int64)).to(device)
            eth = torch.from_numpy(make_eth_batch(y[idx], rng)).to(device)
            xb = xb.unsqueeze(1)

            opt.zero_grad()
            zc, ze = model(xb, eth)
            loss_ctr = contrastive_with_class_labels(zc, ze, yb, model.logit_scale)
            mask_n = yb == 0
            if mask_n.sum() > 1 and (~mask_n).sum() >= 0:
                zn_c = zc[mask_n]
                zn_e = ze[mask_n]
                loss_mmd = mmd_rbf(zn_c, zn_e, sigma=args.mmd_sigma)
            else:
                loss_mmd = torch.tensor(0.0, device=device)
            loss = loss_ctr + args.lambda_mmd * loss_mmd
            loss.backward()
            opt.step()

            total_l += float(loss.item())
            ctr_l += float(loss_ctr.item())
            mmd_l += float(loss_mmd.item()) if isinstance(loss_mmd, torch.Tensor) else loss_mmd
            steps += 1

        sched.step()
        if steps:
            hist_total.append(total_l / steps)
            hist_ctr.append(ctr_l / steps)
            hist_mmd.append(mmd_l / steps)
        print(
            f"epoch {epoch+1} loss={hist_total[-1]:.4f} contrastive={hist_ctr[-1]:.4f} mmd={hist_mmd[-1]:.4f}"
        )

    args.out.mkdir(parents=True, exist_ok=True)
    ckpt_path = args.out / "aligner_encoders.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "latent_dim": args.latent_dim,
            "can_shape": [64, 8],
            "eth_shape": [10, 80],
        },
        ckpt_path,
    )
    print(f"Saved {ckpt_path}")

    # Loss curves
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(hist_total, label="total")
    ax.plot(hist_ctr, label="contrastive")
    ax.plot(hist_mmd, label="MMD (unnormalized)")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.legend()
    ax.set_title("Cross-domain aligner training")
    fig.tight_layout()
    fig.savefig(args.out / "aligner_loss.png", dpi=150)
    plt.close(fig)

    # t-SNE on subset
    model.eval()
    n_vis = min(2000, n)
    idx = np.random.default_rng(args.seed).choice(n, size=n_vis, replace=False)
    with torch.no_grad():
        xc = torch.from_numpy(X[idx]).unsqueeze(1).to(device)
        ye = torch.from_numpy(make_eth_batch(y[idx], rng)).to(device)
        zc, ze = model(xc, ye)

    z = torch.cat([zc, ze], dim=0).cpu().numpy()
    labs = np.concatenate([y[idx], y[idx]], axis=0)
    mod = np.array([0] * n_vis + [1] * n_vis)
    z2 = TSNE(n_components=2, random_state=args.seed, perplexity=30).fit_transform(z)
    fig, ax = plt.subplots(figsize=(7, 6))
    for m, name, mk in [(0, "CAN", "o"), (1, "Eth", "^")]:
        sub = mod == m
        sc = ax.scatter(z2[sub, 0], z2[sub, 1], c=labs[sub], cmap="tab10", s=8, alpha=0.6, marker=mk, label=name)
    plt.colorbar(sc, ax=ax, label="unified label")
    ax.legend()
    ax.set_title("t-SNE of latent z (CAN vs Eth encoders)")
    fig.tight_layout()
    fig.savefig(args.out / "aligner_latent_tsne.png", dpi=150)
    plt.close(fig)

    (args.out / "aligner_train_meta.json").write_text(
        json.dumps(
            {
                "epochs": args.epochs,
                "n_samples": int(n),
                "latent_dim": args.latent_dim,
                "lambda_mmd": args.lambda_mmd,
                "final_loss": hist_total[-1] if hist_total else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
