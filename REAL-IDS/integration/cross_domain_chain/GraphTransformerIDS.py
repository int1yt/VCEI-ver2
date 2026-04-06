"""
Temporal Transformer for cross-domain attack-chain classification.

Input: sequence of fused vectors (B, T, d_in), T=10 by default.
Outputs:
  - chain_logits: attack-chain / scenario class
  - stage_logits: per-timestep attack-stage distribution (num_stages)

Additive module; does not replace IntrusionDetectNet or CAN_CNN in ml_bridge.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 128, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, d_model)
        t = x.size(1)
        x = x + self.pe[:, :t, :]
        return self.dropout(x)


class GraphTransformerIDS(nn.Module):
    """
    Multi-head self-attention over time; cross-protocol coupling is learned in fused input.
    """

    def __init__(
        self,
        d_in: int,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 512,
        num_chain_classes: int = 4,
        num_stages: int = 5,
        dropout: float = 0.1,
        max_seq_len: int = 32,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.input_proj = nn.Linear(d_in, d_model)
        self.pos = PositionalEncoding(d_model, max_len=max_seq_len, dropout=dropout)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=num_layers)
        self.norm = nn.LayerNorm(d_model)
        self.chain_head = nn.Linear(d_model, num_chain_classes)
        self.stage_head = nn.Linear(d_model, num_stages)

    def forward(
        self, x: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        x: (B, T, d_in)
        mask: optional (B, T) bool, True = valid (not used in encoder if all valid)

        Returns:
          chain_logits: (B, num_chain_classes)
          stage_logits: (B, T, num_stages)
        """
        h = self.input_proj(x)
        h = self.pos(h)
        if mask is not None:
            # Transformer expects True = masked positions
            src_key_padding_mask = ~mask.bool()
        else:
            src_key_padding_mask = None
        h = self.encoder(h, src_key_padding_mask=src_key_padding_mask)
        h = self.norm(h)
        pooled = h.mean(dim=1)
        chain_logits = self.chain_head(pooled)
        stage_logits = self.stage_head(h)
        return chain_logits, stage_logits
