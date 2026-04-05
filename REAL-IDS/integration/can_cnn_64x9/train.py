r"""
Train CAN_CNN on processed .npy; save best_model.pth, eval_metrics.json, training curves.

  python train.py --data-dir ./processed
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from model import CAN_CNN
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, TensorDataset


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "processed")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "artifacts")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--eval-only",
        action="store_true",
        help="Skip training; load best_model.pth from --out and write test metrics only.",
    )
    args = ap.parse_args()

    d = args.data_dir
    meta_path = d / "preprocess_meta.json"
    if not meta_path.is_file():
        raise SystemExit(f"Missing {meta_path}; run preprocess.py first")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    shutil.copy(meta_path, args.out / "preprocess_meta.json")
    class_names = meta["class_names"]
    num_classes = len(class_names)

    X_train = np.load(d / "X_train.npy")
    y_train = np.load(d / "y_train.npy")
    X_val = np.load(d / "X_val.npy")
    y_val = np.load(d / "y_val.npy")
    X_test = np.load(d / "X_test.npy")
    y_test = np.load(d / "y_test.npy")

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_ds = TensorDataset(
        torch.from_numpy(X_train).float().unsqueeze(1),
        torch.from_numpy(y_train).long(),
    )
    val_ds = TensorDataset(
        torch.from_numpy(X_val).float().unsqueeze(1),
        torch.from_numpy(y_val).long(),
    )
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    model = CAN_CNN(num_classes=num_classes, in_height=X_train.shape[1], in_width=X_train.shape[2]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss()
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=3)

    hist_train_loss: list[float] = []
    hist_val_loss: list[float] = []
    hist_val_acc: list[float] = []
    best_val = float("inf")
    best_path = args.out / "best_model.pth"

    def batched_predict(x_arr: np.ndarray) -> np.ndarray:
        """Avoid OOM on large test sets."""
        out_chunks: list[np.ndarray] = []
        bs = max(args.batch_size, 256)
        model.eval()
        with torch.no_grad():
            for i in range(0, len(x_arr), bs):
                xb = torch.from_numpy(x_arr[i : i + bs]).float().unsqueeze(1).to(device)
                out_chunks.append(model(xb).argmax(dim=1).cpu().numpy())
        return np.concatenate(out_chunks, axis=0)

    if args.eval_only:
        if not best_path.is_file():
            raise SystemExit(f"Missing {best_path}; train first or drop --eval-only")
        ckpt = torch.load(best_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["state_dict"])
        pred = batched_predict(X_test)
        y_t = y_test
        acc = float(accuracy_score(y_t, pred))
        prec_macro = float(precision_score(y_t, pred, average="macro", zero_division=0))
        rec_macro = float(recall_score(y_t, pred, average="macro", zero_division=0))
        f1_macro = float(f1_score(y_t, pred, average="macro", zero_division=0))
        cm = confusion_matrix(y_t, pred).tolist()
        report = classification_report(y_t, pred, target_names=class_names, zero_division=0)
        eval_out = {
            "test_accuracy": acc,
            "test_precision_macro": prec_macro,
            "test_recall_macro": rec_macro,
            "test_f1_macro": f1_macro,
            "confusion_matrix": cm,
            "class_names": class_names,
            "classification_report_text": report,
            "best_val_loss": float(ckpt.get("best_val_loss", 0)) if isinstance(ckpt, dict) else None,
            "eval_only": True,
        }
        (args.out / "eval_metrics.json").write_text(json.dumps(eval_out, indent=2), encoding="utf-8")
        (args.out / "classification_report.txt").write_text(report, encoding="utf-8")
        print(report)
        print(f"Wrote eval_metrics.json from {best_path}")
        return

    for epoch in range(args.epochs):
        model.train()
        tl = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            opt.step()
            tl += float(loss.item()) * xb.size(0)
        tl /= len(train_ds)

        model.eval()
        vl = 0.0
        correct = 0
        total = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                loss = crit(logits, yb)
                vl += float(loss.item()) * xb.size(0)
                pred = logits.argmax(dim=1)
                correct += int((pred == yb).sum().item())
                total += xb.size(0)
        vl /= len(val_ds)
        vacc = correct / max(total, 1)
        sched.step(vl)

        hist_train_loss.append(tl)
        hist_val_loss.append(vl)
        hist_val_acc.append(vacc)

        if vl < best_val:
            best_val = vl
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "num_classes": num_classes,
                    "in_h": X_train.shape[1],
                    "in_w": X_train.shape[2],
                    "class_names": class_names,
                    "best_val_loss": best_val,
                },
                best_path,
            )
        print(f"epoch {epoch+1}/{args.epochs} train_loss={tl:.4f} val_loss={vl:.4f} val_acc={vacc:.4f}")

    # Plots
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(hist_train_loss, label="train")
    ax[0].plot(hist_val_loss, label="val")
    ax[0].set_title("Loss")
    ax[0].legend()
    ax[1].plot(hist_val_acc, label="val_acc")
    ax[1].set_title("Val accuracy")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(args.out / "training_curves.png", dpi=150)
    plt.close(fig)

    # Test metrics with best weights
    ckpt = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    y_t = y_test
    pred = batched_predict(X_test)

    acc = float(accuracy_score(y_t, pred))
    prec_macro = float(precision_score(y_t, pred, average="macro", zero_division=0))
    rec_macro = float(recall_score(y_t, pred, average="macro", zero_division=0))
    f1_macro = float(f1_score(y_t, pred, average="macro", zero_division=0))
    cm = confusion_matrix(y_t, pred).tolist()
    report = classification_report(y_t, pred, target_names=class_names, zero_division=0)

    eval_out = {
        "test_accuracy": acc,
        "test_precision_macro": prec_macro,
        "test_recall_macro": rec_macro,
        "test_f1_macro": f1_macro,
        "confusion_matrix": cm,
        "class_names": class_names,
        "classification_report_text": report,
        "best_val_loss": best_val,
    }
    (args.out / "eval_metrics.json").write_text(json.dumps(eval_out, indent=2), encoding="utf-8")
    (args.out / "classification_report.txt").write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved {best_path} and eval_metrics.json")


if __name__ == "__main__":
    main()
