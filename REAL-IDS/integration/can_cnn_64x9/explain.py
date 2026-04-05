r"""
Grad-CAM on CAN_CNN conv3: one sample per class from test set → analysis_result.png

  python explain.py --artifacts ./artifacts --data-dir ./processed
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from model import CAN_CNN


def _grad_cam_conv3(model: CAN_CNN, x: torch.Tensor, target_class: int) -> np.ndarray:
    """x: (1,1,H,W) float, requires grad path through conv3."""
    model.eval()
    activations: List[torch.Tensor] = []
    gradients: List[torch.Tensor] = []

    def fwd_hook(_m, _inp, out):
        activations.append(out.detach())

    def full_bwd_hook(_m, _gi, go):
        if go[0] is not None:
            gradients.append(go[0].detach())

    h1 = model.conv3.register_forward_hook(fwd_hook)
    h2 = model.conv3.register_full_backward_hook(full_bwd_hook)
    try:
        x = x.clone().detach().requires_grad_(True)
        logits = model(x)
        model.zero_grad(set_to_none=True)
        score = logits[0, target_class]
        score.backward(retain_graph=False)
    finally:
        h1.remove()
        h2.remove()

    if not activations or not gradients:
        return np.zeros((x.shape[2], x.shape[3]), dtype=np.float32)

    act = activations[0].float()
    grad = gradients[0].float()
    # act, grad: (1, C, H', W')
    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = (weights * act).sum(dim=1, keepdim=True).squeeze()
    cam = torch.relu(cam)
    cam_np = cam.cpu().numpy().astype(np.float32)
    if cam_np.size == 0:
        return np.zeros((x.shape[2], x.shape[3]), dtype=np.float32)
    cam_np -= cam_np.min()
    if cam_np.max() > 1e-8:
        cam_np /= cam_np.max()
    # upsample to input size
    t = torch.from_numpy(cam_np).view(1, 1, *cam_np.shape)
    up = torch.nn.functional.interpolate(
        t, size=(x.shape[2], x.shape[3]), mode="bilinear", align_corners=False
    )
    return up[0, 0].cpu().numpy().astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", type=Path, default=Path(__file__).resolve().parent / "artifacts")
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "processed")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "analysis_result.png")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    wpath = args.artifacts / "best_model.pth"
    if not wpath.is_file():
        raise SystemExit(f"Missing {wpath}; run train.py first")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(wpath, map_location=device, weights_only=False)
    nc = int(ckpt["num_classes"])
    inh = int(ckpt["in_h"])
    inw = int(ckpt["in_w"])
    class_names = list(ckpt.get("class_names", [str(i) for i in range(nc)]))

    model = CAN_CNN(num_classes=nc, in_height=inh, in_width=inw).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.train(False)

    X_test = np.load(args.data_dir / "X_test.npy")
    y_test = np.load(args.data_dir / "y_test.npy")

    rng = np.random.default_rng(args.seed)
    samples: List[Tuple[np.ndarray, int, str]] = []
    for c in range(nc):
        idx = np.where(y_test == c)[0]
        if len(idx) == 0:
            continue
        i = int(rng.choice(idx))
        samples.append((X_test[i], c, class_names[c]))

    if len(samples) < 2:
        raise SystemExit("Not enough classes in y_test for visualization")

    n = len(samples)
    fig, axes = plt.subplots(n, 2, figsize=(6, 2.8 * n))
    if n == 1:
        axes = np.array([axes])

    for row, (mat, cid, cname) in enumerate(samples):
        x = torch.from_numpy(mat.astype(np.float32)).view(1, 1, inh, inw).to(device)
        with torch.no_grad():
            pred = int(model(x).argmax(dim=1).item())
        cam = _grad_cam_conv3(model, x, pred)

        axes[row, 0].imshow(mat, aspect="auto", cmap="gray", vmin=0, vmax=1)
        axes[row, 0].set_title(f"{cname} (true) — input 64×9")
        axes[row, 0].set_ylabel("window row")

        axes[row, 1].imshow(mat, aspect="auto", cmap="gray", vmin=0, vmax=1, alpha=0.45)
        axes[row, 1].imshow(cam, aspect="auto", cmap="jet", alpha=0.55)
        axes[row, 1].set_title(f"Grad-CAM (target=pred {class_names[pred]})")

    for ax in axes.ravel():
        ax.set_xlabel("feature (byte0–7 + Δt)")

    fig.suptitle("CAN 64×9: grayscale window vs conv3 Grad-CAM overlay", fontsize=11)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {args.out.resolve()}")


if __name__ == "__main__":
    main()
