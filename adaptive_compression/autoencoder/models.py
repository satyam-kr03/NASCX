# autoencoder/models.py

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple


class ResidualBlock(nn.Module):
    """Residual block with two convolutional layers and batch normalization."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return F.relu(out)


class Encoder(nn.Module):
    """Encoder network with progressive downsampling and residual connections."""

    def __init__(self, latent_channels: int = 64) -> None:
        super().__init__()
        # Progressive downsampling: 224 -> 112 -> 56 -> 28 -> 14 -> 7
        self.conv1 = nn.Conv2d(3, 64, 4, stride=2, padding=1)  # 112x112
        self.bn1 = nn.BatchNorm2d(64)
        self.res1 = ResidualBlock(64)

        self.conv2 = nn.Conv2d(64, 128, 4, stride=2, padding=1)  # 56x56
        self.bn2 = nn.BatchNorm2d(128)
        self.res2 = ResidualBlock(128)

        self.conv3 = nn.Conv2d(128, 256, 4, stride=2, padding=1)  # 28x28
        self.bn3 = nn.BatchNorm2d(256)
        self.res3 = ResidualBlock(256)

        self.conv4 = nn.Conv2d(256, 512, 4, stride=2, padding=1)  # 14x14
        self.bn4 = nn.BatchNorm2d(512)

        self.conv5 = nn.Conv2d(512, latent_channels, 4, stride=2, padding=1)  # 7x7
        self.bn5 = nn.BatchNorm2d(latent_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.res1(x)

        x = F.relu(self.bn2(self.conv2(x)))
        x = self.res2(x)

        x = F.relu(self.bn3(self.conv3(x)))
        x = self.res3(x)

        x = F.relu(self.bn4(self.conv4(x)))
        x = F.relu(self.bn5(self.conv5(x)))

        return x


class Decoder(nn.Module):
    """Decoder network with progressive upsampling and residual connections."""

    def __init__(self, latent_channels: int = 64) -> None:
        super().__init__()
        self.conv1 = nn.ConvTranspose2d(latent_channels, 512, 4, stride=2, padding=1)  # 14x14
        self.bn1 = nn.BatchNorm2d(512)

        self.conv2 = nn.ConvTranspose2d(512, 256, 4, stride=2, padding=1)  # 28x28
        self.bn2 = nn.BatchNorm2d(256)
        self.res2 = ResidualBlock(256)

        self.conv3 = nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1)  # 56x56
        self.bn3 = nn.BatchNorm2d(128)
        self.res3 = ResidualBlock(128)

        self.conv4 = nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1)  # 112x112
        self.bn4 = nn.BatchNorm2d(64)
        self.res4 = ResidualBlock(64)

        self.conv5 = nn.ConvTranspose2d(64, 3, 4, stride=2, padding=1)  # 224x224

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.bn1(self.conv1(x)))

        x = F.relu(self.bn2(self.conv2(x)))
        x = self.res2(x)

        x = F.relu(self.bn3(self.conv3(x)))
        x = self.res3(x)

        x = F.relu(self.bn4(self.conv4(x)))
        x = self.res4(x)

        x = torch.sigmoid(self.conv5(x))

        return x


class VariableRateAutoencoder(nn.Module):
    """Variable rate autoencoder for compression with adjustable keep ratios."""

    def __init__(self, latent_channels: int = 64) -> None:
        super().__init__()
        self.encoder = Encoder(latent_channels)
        self.decoder = Decoder(latent_channels)
        self.latent_channels = latent_channels

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return reconstructed, latent

    def compress_and_reconstruct(self, x: torch.Tensor, keep_ratio: float = 1.0) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        Compress by keeping only top-k latent coefficients by magnitude.

        Args:
            x: Input tensor
            keep_ratio: Ratio of coefficients to keep (0.0 to 1.0)

        Returns:
            Tuple of (reconstructed, compressed_latent, keep_count)
        """
        with torch.no_grad():
            latent = self.encoder(x)

            if keep_ratio < 1.0:
                # Flatten spatial dimensions
                B, C, H, W = latent.shape
                latent_flat = latent.view(B, -1)  # (B, C*H*W)

                # Calculate how many coefficients to keep
                total_coeffs = latent_flat.shape[1]
                keep_count = int(total_coeffs * keep_ratio)

                # Keep top-k by absolute value (most important)
                abs_values = torch.abs(latent_flat)
                threshold_values, _ = torch.kthvalue(abs_values, total_coeffs - keep_count + 1, dim=1)
                threshold = threshold_values.unsqueeze(1)

                # Zero out small coefficients
                mask = abs_values >= threshold
                latent_compressed = latent_flat * mask.float()
                latent_compressed = latent_compressed.view(B, C, H, W)
            else:
                latent_compressed = latent
                keep_count = latent.numel() // latent.shape[0]

            # Decode
            reconstructed = self.decoder(latent_compressed)

            return reconstructed, latent_compressed, keep_count