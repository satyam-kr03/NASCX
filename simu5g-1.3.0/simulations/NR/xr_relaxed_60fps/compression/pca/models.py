# pca/models.py
#
# PCA-based video frame compressor using scikit-learn IncrementalPCA.

import logging
from typing import Tuple

import numpy as np
from sklearn.decomposition import IncrementalPCA


class PCACompressor:
    """
    PCA-based image compressor.

    Fits IncrementalPCA on flattened, normalised (float32, [0,1]) frames
    and provides compression / reconstruction at arbitrary component counts
    up to *n_components*.
    """

    def __init__(self, n_components: int = 80) -> None:
        self.n_components = n_components
        self.frame_shape: Tuple[int, ...] = ()  # set during fit
        self.pca = IncrementalPCA(n_components=n_components)
        self.fitted = False

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, frames: np.ndarray, batch_size: int = 100) -> None:
        """
        Fit PCA on training frames using incremental batches.

        Args:
            frames: Training frames, shape (N, H, W, 3), dtype uint8.
            batch_size: Frames per partial_fit call.  Must be ≥ n_components.
        """
        n_frames = len(frames)
        batch_size = max(batch_size, self.n_components)
        batch_size = min(batch_size, n_frames)

        frames_f32 = frames.astype(np.float32) / 255.0
        self.frame_shape = frames_f32.shape[1:]  # (H, W, 3)

        # Flatten: (N, H*W*3)
        frames_flat = frames_f32.reshape(n_frames, -1)
        # Free the non-flat view immediately
        del frames_f32

        n_batches = (n_frames + batch_size - 1) // batch_size
        for i in range(0, n_frames, batch_size):
            batch = frames_flat[i : i + batch_size]
            self.pca.partial_fit(batch)
            batch_num = i // batch_size + 1
            if batch_num % 5 == 0 or batch_num == n_batches:
                logging.debug(f"  partial_fit batch {batch_num}/{n_batches}")

        del frames_flat
        self.fitted = True

    # ------------------------------------------------------------------
    # Compression & reconstruction
    # ------------------------------------------------------------------

    def compress_and_reconstruct(
        self, frame: np.ndarray, n_components: int
    ) -> np.ndarray:
        """
        Compress and reconstruct a single frame via PCA truncation.

        Standard PCA truncation: project onto the first *k* principal
        components and reconstruct from those alone.  This is equivalent
        to the best rank-k approximation in the L2 sense.

        Args:
            frame: Single frame, shape (H, W, 3), float32 in [0, 1].
            n_components: Number of principal components to retain.

        Returns:
            Reconstructed frame, same shape, clipped to [0, 1].
        """
        if not self.fitted:
            raise RuntimeError("PCA must be fitted before compression")

        n_components = min(n_components, self.n_components)

        frame_flat = frame.reshape(1, -1)

        # Direct sliced projection (standard PCA truncation)
        components_k = self.pca.components_[:n_components]        # (k, n_features)
        coefficients = (frame_flat - self.pca.mean_) @ components_k.T  # (1, k)
        reconstructed_flat = coefficients @ components_k + self.pca.mean_  # (1, n_features)

        return np.clip(reconstructed_flat.reshape(self.frame_shape), 0, 1)
