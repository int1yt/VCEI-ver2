"""
Lightweight CNN for CAN bus 64×9 single-channel "image" tensors.
PEP8; input size configurable via constructor.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class CAN_CNN(nn.Module):
    """
    Three conv blocks (Conv2d → BatchNorm2d → ReLU → MaxPool2d), then AdaptiveAvgPool,
    Dropout, Linear classifier. Use with CrossEntropyLoss (logits, no final Softmax).
    """

    def __init__(
        self,
        num_classes: int = 4,
        in_channels: int = 1,
        in_height: int = 64,
        in_width: int = 9,
        dropout_p: float = 0.5,
    ) -> None:
        super().__init__()
        self.in_height = in_height
        self.in_width = in_width

        self.conv1 = nn.Conv2d(in_channels, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(2)

        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(2)

        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.pool3 = nn.MaxPool2d(2)

        # Stabilize variable spatial size before FC
        self.adaptive = nn.AdaptiveAvgPool2d((2, 2))
        self.dropout = nn.Dropout(dropout_p)
        self.fc = nn.Linear(128 * 2 * 2, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool1(torch.relu(self.bn1(self.conv1(x))))
        x = self.pool2(torch.relu(self.bn2(self.conv2(x))))
        x = self.pool3(torch.relu(self.bn3(self.conv3(x))))
        x = self.adaptive(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        return self.fc(x)
