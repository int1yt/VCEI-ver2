from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    root = Path(__file__).resolve().parent
    metrics_path = root / "../../REAL-IDS/integration/can_cnn_64x9/artifacts/eval_metrics.json"
    out_dir = root / "real-training-images"
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    cm = np.array(metrics["confusion_matrix"], dtype=float)
    classes = metrics["class_names"]

    # 1) Confusion matrix heatmap (counts)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_title("CAN-CNN(64x9) Confusion Matrix (Test)")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_xticks(np.arange(len(classes)), labels=classes, rotation=20)
    ax.set_yticks(np.arange(len(classes)), labels=classes)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{int(cm[i, j])}", ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix_can_cnn64.png", dpi=220)
    plt.close(fig)

    # 2) Class-wise P/R/F1 bars from report text (stable with current output format)
    report = metrics.get("classification_report_text", "")
    rows = []
    for line in report.splitlines():
        if not line.strip():
            continue
        if line.strip().startswith(("accuracy", "macro avg", "weighted avg")):
            continue
        parts = line.split()
        if len(parts) >= 5 and parts[0] in classes:
            rows.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))

    labels = [r[0] for r in rows]
    precision = np.array([r[1] for r in rows], dtype=float)
    recall = np.array([r[2] for r in rows], dtype=float)
    f1 = np.array([r[3] for r in rows], dtype=float)

    x = np.arange(len(labels))
    w = 0.24
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    ax.bar(x - w, precision, w, label="Precision")
    ax.bar(x, recall, w, label="Recall")
    ax.bar(x + w, f1, w, label="F1-score")
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Score")
    ax.set_title("Class-wise Metrics of CAN-CNN(64x9)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout()
    fig.savefig(out_dir / "class_metrics_can_cnn64.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
