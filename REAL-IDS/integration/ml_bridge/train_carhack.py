r"""
Train CarHack CAN classifier from VCEI/CarHackData (5 classes).
Writes models/carhack_can_clf.pth next to this file.

  cd REAL-IDS/integration/ml_bridge
  .venv/Scripts/activate
  python train_carhack.py --epochs 8

Options tune memory vs quality: --max-lines-per-file, --stride, --max-windows-per-class.
"""
from __future__ import annotations

import argparse
import os
import random
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from carhack_io import CARHACK_FILES, default_carhack_data_root, iter_packets_from_file
from carhack_model import CarHackCanCNN
from features import can_packets_to_matrix_29x29


def collect_windows(
    data_root: Path,
    max_lines_per_file: int,
    stride: int,
    max_windows_per_class: int,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    random.seed(seed)
    np.random.seed(seed)
    all_X: List[np.ndarray] = []
    all_y: List[int] = []

    for fname, label_id in CARHACK_FILES:
        path = data_root / fname
        if not path.is_file():
            print(f"[skip] missing {path}")
            continue
        dq: Deque[Dict] = deque(maxlen=29)
        windows = 0
        step = 0
        for pkt in iter_packets_from_file(path, max_lines=max_lines_per_file):
            dq.append(pkt)
            if len(dq) < 29:
                continue
            step += 1
            if step % stride != 0:
                continue
            mat = can_packets_to_matrix_29x29(list(dq))
            all_X.append(mat)
            all_y.append(label_id)
            windows += 1
            if windows >= max_windows_per_class:
                break
        print(f"{fname}: label={label_id} windows={windows}")

    if not all_X:
        raise RuntimeError("No windows collected — check CarHackData paths and parsers.")

    X = np.stack(all_X, axis=0).astype(np.float32)
    y = np.array(all_y, dtype=np.int64)
    return X, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-lines-per-file", type=int, default=120_000)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--max-windows-per-class", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    root = args.data_root or default_carhack_data_root()
    out = args.out or (Path(__file__).resolve().parent / "models" / "carhack_can_clf.pth")
    out.parent.mkdir(parents=True, exist_ok=True)

    X, y = collect_windows(
        root,
        max_lines_per_file=args.max_lines_per_file,
        stride=args.stride,
        max_windows_per_class=args.max_windows_per_class,
        seed=args.seed,
    )
    n = X.shape[0]
    idx = np.random.permutation(n)
    X, y = X[idx], y[idx]
    n_val = max(1, int(0.15 * n))
    X_val, y_val = X[:n_val], y[:n_val]
    X_tr, y_tr = X[n_val:], y[n_val:]

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CarHackCanCNN(num_classes=5).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss()

    tr_ds = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr))
    tr_loader = DataLoader(tr_ds, batch_size=args.batch_size, shuffle=True, drop_last=False)
    Xv = torch.from_numpy(X_val).to(dev)
    yv = torch.from_numpy(y_val).to(dev)

    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for xb, yb in tr_loader:
            xb = xb.to(dev).unsqueeze(1)
            yb = yb.to(dev)
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * xb.size(0)
        model.eval()
        with torch.no_grad():
            pred = model(Xv.unsqueeze(1)).argmax(dim=1)
            acc = float((pred == yv).float().mean().item())
        print(f"epoch {epoch+1}/{args.epochs} train_loss={total/len(tr_ds):.4f} val_acc={acc:.4f}")

    torch.save(model.state_dict(), str(out))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
