# autoencoder/models.py
#
# Convolutional autoencoder for video frame compression.
# Provides the ConvAutoencoder network and the AutoencoderCompressor
# manager that trains one model per target latent dimension with
# warm-starting.

import copy
import logging
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from . import DEFAULT_LATENT_DIMS, DEFAULT_EPOCHS, DEFAULT_LR


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class ConvAutoencoder(nn.Module):
    """
    Symmetric convolutional autoencoder with a flat bottleneck.

    Encoder: 4 × (Conv2d → BN → ReLU) → Flatten → Linear → z ∈ ℝ^d
    Decoder: Linear → Reshape → 4 × (ConvTranspose2d → BN → ReLU) → Sigmoid

    Channel progression: [3, 32, 64, 128, 256].
    Each conv block uses kernel=4, stride=2, padding=1 → halves spatial dims.
    Input: (B, 3, 224, 224) → after 4 down-samples: (B, 256, 14, 14).
    Flat dim = 256 × 14 × 14 = 50176.
    """

    CHANNELS = [3, 32, 64, 128, 256]
    FLAT_DIM = 256 * 14 * 14  # 50176

    def __init__(self, latent_dim: int, img_size: int = 224) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.img_size = img_size

        # ---------- Encoder convolutions --------------------------------
        enc_layers: list = []
        for i in range(len(self.CHANNELS) - 1):
            enc_layers.append(
                nn.Conv2d(
                    self.CHANNELS[i], self.CHANNELS[i + 1],
                    kernel_size=4, stride=2, padding=1,
                )
            )
            enc_layers.append(nn.BatchNorm2d(self.CHANNELS[i + 1]))
            enc_layers.append(nn.ReLU(inplace=True))
        self.encoder_conv = nn.Sequential(*enc_layers)

        # ---------- Encoder FC (flat → latent) --------------------------
        self.encoder_fc = nn.Linear(self.FLAT_DIM, latent_dim)

        # ---------- Decoder FC (latent → flat) --------------------------
        self.decoder_fc = nn.Linear(latent_dim, self.FLAT_DIM)

        # ---------- Decoder convolutions --------------------------------
        dec_layers: list = []
        rev_ch = list(reversed(self.CHANNELS))  # [256, 128, 64, 32, 3]
        for i in range(len(rev_ch) - 1):
            is_last = i == len(rev_ch) - 2
            dec_layers.append(
                nn.ConvTranspose2d(
                    rev_ch[i], rev_ch[i + 1],
                    kernel_size=4, stride=2, padding=1,
                )
            )
            if is_last:
                dec_layers.append(nn.Sigmoid())
            else:
                dec_layers.append(nn.BatchNorm2d(rev_ch[i + 1]))
                dec_layers.append(nn.ReLU(inplace=True))
        self.decoder_conv = nn.Sequential(*dec_layers)

    # ----- forward helpers -------------------------------------------
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode (B, 3, H, W) → (B, latent_dim)."""
        h = self.encoder_conv(x)                  # (B, 256, 14, 14)
        h = h.view(h.size(0), -1)                 # (B, 50176)
        z = self.encoder_fc(h)                     # (B, d)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decode (B, latent_dim) → (B, 3, H, W)."""
        h = self.decoder_fc(z)                     # (B, 50176)
        h = h.view(h.size(0), 256, 14, 14)        # (B, 256, 14, 14)
        x_hat = self.decoder_conv(h)               # (B, 3, H, W)
        return x_hat

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decode(self.encode(x))


# ---------------------------------------------------------------------------
# Manager: one model per latent dimension, with warm-starting
# ---------------------------------------------------------------------------

class AutoencoderCompressor:
    """
    Trains and manages one ConvAutoencoder per target latent dimension.

    Models are trained smallest-first with warm-starting: after finishing
    dimension d_i, the convolutional backbone weights (encoder_conv,
    decoder_conv) are copied to the model for d_{i+1} before training it.
    Only the FC bottleneck layers (encoder_fc, decoder_fc) differ in width
    and are freshly initialised.
    """

    def __init__(
        self,
        latent_dims: List[int] = DEFAULT_LATENT_DIMS,
        img_size: int = 224,
        device: str = "cpu",
    ) -> None:
        self.latent_dims = sorted(latent_dims)  # ascending for warm-start
        self.img_size = img_size
        self.device = torch.device(device)
        self.models: Dict[int, ConvAutoencoder] = {}

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        dataloader: DataLoader,
        epochs: int = DEFAULT_EPOCHS,
        lr: float = DEFAULT_LR,
    ) -> None:
        """
        Train one model per latent dimension with warm-starting.

        After training dim d_i, its convolutional backbone is copied
        to the model for d_{i+1} before that model begins training.
        """
        prev_model: ConvAutoencoder | None = None

        for dim in self.latent_dims:
            logging.info(f"Training autoencoder  latent_dim={dim}")

            model = ConvAutoencoder(latent_dim=dim, img_size=self.img_size).to(self.device)

            # --- warm-start from previous model's conv layers ----------
            if prev_model is not None:
                model.encoder_conv.load_state_dict(
                    prev_model.encoder_conv.state_dict()
                )
                model.decoder_conv.load_state_dict(
                    prev_model.decoder_conv.state_dict()
                )
                logging.info(f"  Warm-started conv backbone from latent_dim={prev_model.latent_dim}")

            optimiser = torch.optim.Adam(model.parameters(), lr=lr)
            criterion = nn.MSELoss()
            model.train()

            for epoch in range(1, epochs + 1):
                epoch_loss = 0.0
                n_batches = 0
                for batch in dataloader:
                    batch = batch.to(self.device)
                    reconstructed = model(batch)
                    loss = criterion(reconstructed, batch)

                    optimiser.zero_grad()
                    loss.backward()
                    optimiser.step()

                    epoch_loss += loss.item()
                    n_batches += 1

                avg_loss = epoch_loss / max(n_batches, 1)
                if epoch % 10 == 0 or epoch == epochs:
                    logging.info(
                        f"  latent_dim={dim}  epoch {epoch:3d}/{epochs}  "
                        f"loss={avg_loss:.6f}"
                    )

            model.eval()
            self.models[dim] = model
            prev_model = model

        logging.info(f"All {len(self.latent_dims)} autoencoder models trained.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    @torch.no_grad()
    def compress_and_reconstruct(
        self,
        frame: np.ndarray,
        latent_dim: int,
    ) -> np.ndarray:
        """
        Compress and reconstruct a single frame via the autoencoder
        for the given latent dimension.

        Args:
            frame: (H, W, 3) float32 in [0, 1].
            latent_dim: Bottleneck dimension (must have been trained).

        Returns:
            Reconstructed frame (H, W, 3) float32, clamped to [0, 1].
        """
        model = self.models[latent_dim]

        # (H, W, 3) → (1, 3, H, W) tensor on device
        x = torch.from_numpy(
            np.transpose(frame, (2, 0, 1))[np.newaxis]
        ).to(self.device)

        x_hat = model(x)                          # (1, 3, H, W)
        x_hat = torch.clamp(x_hat, 0.0, 1.0)

        # (1, 3, H, W) → (H, W, 3)
        return x_hat.squeeze(0).permute(1, 2, 0).cpu().numpy()

    def get_num_params(self, latent_dim: int) -> int:
        """Return the total number of trainable parameters for the model."""
        model = self.models[latent_dim]
        return sum(p.numel() for p in model.parameters())
