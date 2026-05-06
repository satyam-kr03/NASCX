"""
Fusion model architectures.

Three variants of increasing complexity, all operating pixel-wise:

1. Conv1x1Fusion  — 1×1 convolutions (learned pixel-wise weighted combination)
2. PixelMLP       — flattened pixel-wise MLP (equivalent but explicit)
3. Conv3x3Fusion  — small spatial context via 3×3 convolutions

The default (conv1x1) is the cleanest and most defensible for a viva:
"It learns spatially varying weights for how much to trust gaze prediction
versus object detection at each pixel, optimised against human fixation GT."
"""

from __future__ import annotations

import torch
import torch.nn as nn

from config import ModelConfig


class Conv1x1Fusion(nn.Module):
    """
    Pixel-wise learned fusion via stacked 1×1 convolutions.

    This is equivalent to applying a small MLP independently at every pixel.
    Clean, fast, and trivially parallelised by the GPU.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        layers = []

        in_c = cfg.in_channels  # 2
        for _ in range(cfg.n_hidden):
            layers.append(nn.Conv2d(in_c, cfg.hidden_channels, 1))
            layers.append(nn.ReLU(inplace=True))
            if cfg.dropout > 0:
                layers.append(nn.Dropout2d(cfg.dropout))
            in_c = cfg.hidden_channels

        layers.append(nn.Conv2d(in_c, 1, 1))
        layers.append(nn.Sigmoid())

        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        x : Tensor [B, 2, H, W]
            Channel 0 = gaze saliency, Channel 1 = object saliency.

        Returns
        -------
        Tensor [B, 1, H, W] — fused saliency in [0, 1].
        """
        return self.net(x)


class PixelMLP(nn.Module):
    """
    Explicit pixel-wise MLP.  Reshapes the spatial dims, applies an MLP to
    each pixel's 2-channel feature vector, then reshapes back.
    Functionally equivalent to Conv1x1Fusion but makes the "per pixel" nature
    explicit for clarity.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        layers = []
        in_f = cfg.in_channels
        for _ in range(cfg.n_hidden):
            layers.append(nn.Linear(in_f, cfg.hidden_channels))
            layers.append(nn.ReLU(inplace=True))
            if cfg.dropout > 0:
                layers.append(nn.Dropout(cfg.dropout))
            in_f = cfg.hidden_channels
        layers.append(nn.Linear(in_f, 1))
        layers.append(nn.Sigmoid())
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        # Reshape: [B, C, H, W] → [B*H*W, C]
        x = x.permute(0, 2, 3, 1).reshape(-1, C)
        x = self.net(x)  # [B*H*W, 1]
        return x.reshape(B, H, W, 1).permute(0, 3, 1, 2)  # [B, 1, H, W]


class Conv3x3Fusion(nn.Module):
    """
    Fusion with small spatial context via 3×3 convolutions.

    Uses padding=1 to maintain spatial resolution.  Gives the model the ability
    to learn from the immediate neighbourhood — useful if gaze and object maps
    are slightly mis-aligned or if local spatial gradients carry information.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        layers = []
        in_c = cfg.in_channels
        for _ in range(cfg.n_hidden):
            layers.append(nn.Conv2d(in_c, cfg.hidden_channels, 3, padding=1))
            layers.append(nn.ReLU(inplace=True))
            if cfg.dropout > 0:
                layers.append(nn.Dropout2d(cfg.dropout))
            in_c = cfg.hidden_channels
        # Final 1×1 to collapse to single channel
        layers.append(nn.Conv2d(in_c, 1, 1))
        layers.append(nn.Sigmoid())
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ── Factory ─────────────────────────────────────────────────────────────────

_MODELS = {
    "conv1x1": Conv1x1Fusion,
    "mlp": PixelMLP,
    "conv3x3": Conv3x3Fusion,
}


def build_model(cfg: ModelConfig) -> nn.Module:
    """Instantiate a fusion model from config."""
    if cfg.variant not in _MODELS:
        raise ValueError(
            f"Unknown model variant '{cfg.variant}'. "
            f"Choose from: {list(_MODELS.keys())}"
        )
    model = _MODELS[cfg.variant](cfg)

    # Count parameters
    n_params = sum(p.numel() for p in model.parameters())
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Fusion model: {cfg.variant}  |  "
          f"{n_params:,} params ({n_train:,} trainable)")

    return model
