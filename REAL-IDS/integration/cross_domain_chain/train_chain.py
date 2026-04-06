r"""
Train GraphTransformerIDS on chain_dataset.pt.

Loss = CrossEntropy(chain) + mean CrossEntropy per-timestep stage.

Visualizations: artifacts/chain_training.png, chain_confusion_matrix.png

Usage:
  python train_chain.py --dataset ./artifacts/chain_dataset.pt --epochs 40 --out ./artifacts
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
import torch.nn as nn
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm

from GraphTransformerIDS import GraphTransformerIDS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parent / "artifacts" / "chain_dataset.pt")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--lambda-stage", type=float, default=0.5, help="weight for per-timestep stage loss")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "artifacts")
    args = ap.parse_args()

    if not args.dataset.is_file():
        raise SystemExit(f"Missing {args.dataset}; run chain_generator.py first")

    pack = torch.load(args.dataset, map_location="cpu", weights_only=False)
    seq = pack["sequences"].float()
    chain_y = pack["chain_labels"].long()
    stage_y = pack["stage_labels"].long()
    meta = pack.get("meta", {})
    fused_dim = int(meta.get("fused_dim", seq.shape[-1]))
    num_chain = int(chain_y.max().item()) + 1
    num_stages = int(stage_y.max().item()) + 1

    idx = np.arange(len(seq))
    tr, va = train_test_split(idx, test_size=0.15, random_state=args.seed, stratify=chain_y.numpy())

    train_ds = TensorDataset(seq[tr], chain_y[tr], stage_y[tr])
    val_ds = TensorDataset(seq[va], chain_y[va], stage_y[va])
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GraphTransformerIDS(
        d_in=fused_dim,
        d_model=256,
        nhead=8,
        num_layers=4,
        dim_feedforward=512,
        num_chain_classes=num_chain,
        num_stages=num_stages,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    crit = nn.CrossEntropyLoss()

    hist_tr: list[float] = []
    hist_va: list[float] = []
    best_state = None
    best_va = float("inf")

    for epoch in range(args.epochs):
        model.train()
        tl = 0.0
        for xb, cyb, syb in tqdm(train_loader, desc=f"epoch {epoch+1}/{args.epochs}"):
            xb, cyb, syb = xb.to(device), cyb.to(device), syb.to(device)
            opt.zero_grad()
            chain_logits, stage_logits = model(xb)
            lc = crit(chain_logits, cyb)
            # stage_logits: (B, T, S); syb: (B, T)
            ls = crit(stage_logits.reshape(-1, num_stages), syb.reshape(-1))
            loss = lc + args.lambda_stage * ls
            loss.backward()
            opt.step()
            tl += float(loss.item()) * xb.size(0)
        tl /= len(train_ds)

        model.eval()
        vl = 0.0
        with torch.no_grad():
            for xb, cyb, syb in val_loader:
                xb, cyb, syb = xb.to(device), cyb.to(device), syb.to(device)
                chain_logits, stage_logits = model(xb)
                lc = crit(chain_logits, cyb)
                ls = crit(stage_logits.reshape(-1, num_stages), syb.reshape(-1))
                loss = lc + args.lambda_stage * ls
                vl += float(loss.item()) * xb.size(0)
        vl /= len(val_ds)

        hist_tr.append(tl)
        hist_va.append(vl)
        if vl < best_va:
            best_va = vl
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        print(f"epoch {epoch+1} train_loss={tl:.4f} val_loss={vl:.4f}")

    args.out.mkdir(parents=True, exist_ok=True)
    if best_state is not None:
        model.load_state_dict(best_state)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "fused_dim": fused_dim,
            "num_chain_classes": num_chain,
            "num_stages": num_stages,
            "meta": meta,
        },
        args.out / "graph_transformer_ids.pt",
    )

    # Plots
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(hist_tr, label="train")
    ax.plot(hist_va, label="val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.legend()
    ax.set_title("GraphTransformerIDS training")
    fig.tight_layout()
    fig.savefig(args.out / "chain_training.png", dpi=150)
    plt.close(fig)

    # Confusion matrix (chain class)
    model.eval()
    preds: list[int] = []
    trues: list[int] = []
    with torch.no_grad():
        for xb, cyb, _ in DataLoader(TensorDataset(seq, chain_y, stage_y), batch_size=128, shuffle=False):
            xb = xb.to(device)
            cl, _ = model(xb)
            preds.extend(cl.argmax(dim=1).cpu().tolist())
            trues.extend(cyb.tolist())
    cm = confusion_matrix(trues, preds)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    plt.colorbar(im, ax=ax)
    names = meta.get("chain_names", [str(i) for i in range(num_chain)])
    ax.set_xticks(range(num_chain))
    ax.set_yticks(range(num_chain))
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticklabels(names)
    ax.set_ylabel("True")
    ax.set_xlabel("Predicted")
    ax.set_title("Chain-type confusion matrix")
    fig.tight_layout()
    fig.savefig(args.out / "chain_confusion_matrix.png", dpi=150)
    plt.close(fig)

    (args.out / "chain_train_meta.json").write_text(
        json.dumps(
            {
                "epochs": args.epochs,
                "best_val_loss": best_va,
                "num_chain_classes": num_chain,
                "num_stages": num_stages,
                "fused_dim": fused_dim,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {args.out / 'graph_transformer_ids.pt'}")


if __name__ == "__main__":
    main()
