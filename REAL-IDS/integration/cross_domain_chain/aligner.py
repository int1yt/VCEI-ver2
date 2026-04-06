"""
Cross-domain feature alignment: CANEncoder (64×8) + EthernetEncoder (10×80) → shared latent space.

Losses:
  - InfoNCE-style symmetric contrastive loss (same unified attack label → high similarity)
  - MMD (RBF kernel) between CAN-normal and Ethernet-normal latent vectors

Does not replace can_cnn_64x9 or ml_bridge eth models; this is an additive training module.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class CANEncoder(nn.Module):
    """Encode a single CAN window (64×8) to latent_dim."""

    def __init__(self, latent_dim: int = 128) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.net = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((2, 2)),
        )
        self.fc = nn.Linear(128 * 2 * 2, latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 1, 64, 8)
        h = self.net(x)
        h = torch.flatten(h, 1)
        return self.fc(h)


class EthernetEncoder(nn.Module):
    """Encode Ethernet window (10×80) to latent_dim."""

    def __init__(self, latent_dim: int = 128, in_steps: int = 10, in_dim: int = 80) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.in_steps = in_steps
        self.in_dim = in_dim
        self.embed = nn.Linear(in_dim, 128)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=128,
            nhead=4,
            dim_feedforward=256,
            dropout=0.1,
            batch_first=True,
        )
        self.tr = nn.TransformerEncoder(enc_layer, num_layers=2)
        self.pool = nn.Linear(128 * in_steps, latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 10, 80)
        h = self.embed(x)
        h = self.tr(h)
        h = torch.flatten(h, 1)
        return self.pool(h)


class CrossDomainAligner(nn.Module):
    """Dual encoders + optional temperature for contrastive loss."""

    def __init__(self, latent_dim: int = 128, can_h: int = 64, can_w: int = 8) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.can_enc = CANEncoder(latent_dim)
        self.eth_enc = EthernetEncoder(latent_dim)
        self.logit_scale = nn.Parameter(torch.ones([]) * math.log(1 / 0.07))

    def encode_can(self, can_64x8: torch.Tensor) -> torch.Tensor:
        if can_64x8.dim() == 3:
            can_64x8 = can_64x8.unsqueeze(1)
        return self.can_enc(can_64x8)

    def encode_eth(self, eth_10x80: torch.Tensor) -> torch.Tensor:
        return self.eth_enc(eth_10x80)

    def forward(
        self, can_64x8: torch.Tensor, eth_10x80: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        z_c = self.encode_can(can_64x8)
        z_e = self.encode_eth(eth_10x80)
        return z_c, z_e


def symmetric_infonce(
    z_can: torch.Tensor,
    z_eth: torch.Tensor,
    temperature: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """
    CLIP-style symmetric cross-entropy. Batch is paired: (can_i, eth_i) should match.
    """
    z_can = F.normalize(z_can, dim=-1)
    z_eth = F.normalize(z_eth, dim=-1)
    if temperature is None:
        temperature = torch.tensor(0.07, device=z_can.device, dtype=z_can.dtype)
    else:
        temperature = torch.exp(temperature.clamp(-10, 10))
    logits = (z_can @ z_eth.T) / temperature
    b = z_can.size(0)
    targets = torch.arange(b, device=z_can.device)
    loss_c = F.cross_entropy(logits, targets)
    loss_e = F.cross_entropy(logits.T, targets)
    return 0.5 * (loss_c + loss_e)


def rbf_kernel_matrix(a: torch.Tensor, b: torch.Tensor, sigma: float = 1.0) -> torch.Tensor:
    """a: (n,d), b: (m,d) -> (n,m)"""
    a = a.unsqueeze(1)
    b = b.unsqueeze(0)
    dist = ((a - b) ** 2).sum(dim=-1)
    return torch.exp(-dist / (2.0 * sigma * sigma + 1e-8))


def mmd_rbf(x: torch.Tensor, y: torch.Tensor, sigma: float = 1.0) -> torch.Tensor:
    """Unbiased MMD^2 with RBF kernel (simplified full expansion)."""
    n, m = x.size(0), y.size(0)
    if n < 2 or m < 2:
        return torch.tensor(0.0, device=x.device, dtype=x.dtype)
    Kxx = rbf_kernel_matrix(x, x, sigma)
    Kyy = rbf_kernel_matrix(y, y, sigma)
    Kxy = rbf_kernel_matrix(x, y, sigma)
    term_xx = (Kxx.sum() - Kxx.diag().sum()) / (n * (n - 1))
    term_yy = (Kyy.sum() - Kyy.diag().sum()) / (m * (m - 1))
    term_xy = Kxy.mean()
    return term_xx + term_yy - 2.0 * term_xy


def contrastive_with_class_labels(
    z_can: torch.Tensor,
    z_eth: torch.Tensor,
    labels: torch.Tensor,
    temperature: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """
    Supervised contrastive alignment: pull cross-modal pairs with the same unified label,
    push different labels. Uses InfoNCE with positives = all same-class indices in batch.
    """
    z_can = F.normalize(z_can, dim=-1)
    z_eth = F.normalize(z_eth, dim=-1)
    if temperature is None:
        t = torch.tensor(0.07, device=z_can.device, dtype=z_can.dtype)
    else:
        t = torch.exp(temperature.clamp(-10, 10))
    logits = (z_can @ z_eth.T) / t
    b = labels.size(0)
    mask = labels.unsqueeze(0) == labels.unsqueeze(1)
    mask = mask.float()
    # For each row i, sum exp over j where same class (including self)
    exp_logits = torch.exp(logits)
    masked_sum = (exp_logits * mask).sum(dim=1).clamp(min=1e-8)
    pos = torch.exp(torch.diag(logits))
    loss_row = -torch.log(pos / masked_sum)
    # symmetric columns
    logits_t = logits.T
    mask_t = mask.T
    exp_logits_t = torch.exp(logits_t)
    masked_sum_t = (exp_logits_t * mask_t).sum(dim=1).clamp(min=1e-8)
    pos_t = torch.exp(torch.diag(logits_t))
    loss_col = -torch.log(pos_t / masked_sum_t)
    return 0.5 * (loss_row.mean() + loss_col.mean())
