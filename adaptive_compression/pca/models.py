# pca/models.py

import numpy as np
from sklearn.decomposition import IncrementalPCA
from typing import Tuple

from . import DEFAULT_IMG_SIZE


class PCACompressor:
    """
    PCA-based image compressor.
    
    Fits PCA on flattened image channels and provides compression/reconstruction
    at different component counts.
    """

    def __init__(self, n_components: int = 16, img_size: int = DEFAULT_IMG_SIZE) -> None:
        """
        Initialize PCA compressor.
        
        Args:
            n_components: Maximum number of principal components to keep
            img_size: Image size (assumes square images)
        """
        self.n_components = n_components
        self.img_size = img_size
        self.pca = IncrementalPCA(n_components=n_components)
        self.fitted = False

    def fit(self, frames: np.ndarray) -> None:
        """
        Fit PCA on training frames.
        
        Args:
            frames: Training frames of shape (N, H, W, 3) with values 0-255
        """
        # Normalize and reshape frames for PCA
        # Each frame becomes a row: (N, H*W*3)
        n_frames = len(frames)
        frames_normalized = frames.astype(np.float32) / 255.0
        
        # Resize frames to img_size x img_size if needed
        import torch
        import torch.nn.functional as F
        
        resized_frames = []
        for frame in frames_normalized:
            frame_tensor = torch.from_numpy(frame).float().permute(2, 0, 1).unsqueeze(0)
            frame_resized = F.interpolate(frame_tensor, size=(self.img_size, self.img_size),
                                         mode='bilinear', align_corners=False)
            resized_frames.append(frame_resized.squeeze(0).permute(1, 2, 0).numpy())
        
        frames_resized = np.stack(resized_frames)
        
        # Flatten: (N, H*W*3)
        frames_flat = frames_resized.reshape(n_frames, -1)
        
        # Fit PCA incrementally to handle memory
        batch_size = min(100, n_frames)
        for i in range(0, n_frames, batch_size):
            batch = frames_flat[i:i+batch_size]
            self.pca.partial_fit(batch)
        
        self.fitted = True

    def compress_and_reconstruct(self, frame: np.ndarray, n_components: int) -> Tuple[np.ndarray, int]:
        """
        Compress and reconstruct a frame using specified number of components.
        
        Args:
            frame: Single frame of shape (H, W, 3) normalized to [0, 1]
            n_components: Number of principal components to use
        
        Returns:
            Tuple of (reconstructed_frame, compressed_size_bytes)
        """
        if not self.fitted:
            raise RuntimeError("PCA must be fitted before compression")
        
        # Limit n_components to available
        n_components = min(n_components, self.n_components)
        
        # Flatten frame
        frame_flat = frame.reshape(1, -1)
        
        # Transform to PCA space (all components)
        transformed = self.pca.transform(frame_flat)
        
        # Zero out components beyond n_components
        transformed_truncated = np.zeros_like(transformed)
        transformed_truncated[0, :n_components] = transformed[0, :n_components]
        
        # Inverse transform
        reconstructed_flat = self.pca.inverse_transform(transformed_truncated)
        reconstructed = reconstructed_flat.reshape(self.img_size, self.img_size, 3)
        
        # Clip to valid range
        reconstructed = np.clip(reconstructed, 0, 1)
        
        # Calculate compressed size (n_components float32 values)
        size_bytes = n_components * self.img_size * 4  # 4 bytes per float32
        
        return reconstructed, size_bytes
