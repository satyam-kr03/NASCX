# autoencoder/data.py
#
# Data layer for the autoencoder compression pipeline.
# Re-exports shared video I/O from pca.data and adds a PyTorch
# Dataset / DataLoader wrapper for mini-batch training.

from typing import Tuple

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

# Re-export shared I/O functions from the PCA data module.
# When executed via ``python -m adaptive_compression.ae`` from the workspace
# root the package hierarchy is adaptive_compression.pca, so we try the
# fully-qualified import first and fall back to the bare name for the case
# where the working directory is adaptive_compression/.
try:
    from adaptive_compression.pca.data import (   # noqa: F401
        get_video_info,
        get_encoded_frame_sizes,
        sample_training_frames,
        stream_test_frames,
    )
except ModuleNotFoundError:
    from pca.data import (                        # noqa: F401
        get_video_info,
        get_encoded_frame_sizes,
        sample_training_frames,
        stream_test_frames,
    )


# ---------------------------------------------------------------------------
# PyTorch Dataset wrapper
# ---------------------------------------------------------------------------

class FrameDataset(Dataset):
    """
    PyTorch Dataset wrapping an (N, H, W, 3) uint8 numpy array.

    Each ``__getitem__`` call normalises the frame to float32 in [0, 1]
    and transposes to channel-first format (3, H, W) as required by
    PyTorch convolutional layers.
    """

    def __init__(self, frames: np.ndarray) -> None:
        """
        Args:
            frames: (N, H, W, 3) uint8 numpy array of video frames.
        """
        super().__init__()
        self.frames = frames  # keep reference; avoid copying

    def __len__(self) -> int:
        return len(self.frames)

    def __getitem__(self, idx: int) -> torch.Tensor:
        frame = self.frames[idx].astype(np.float32) / 255.0   # [0, 1]
        frame = np.transpose(frame, (2, 0, 1))                # (3, H, W)
        return torch.from_numpy(frame)


# ---------------------------------------------------------------------------
# DataLoader factory
# ---------------------------------------------------------------------------

def get_dataloader(
    frames: np.ndarray,
    batch_size: int = 32,
    shuffle: bool = True,
    num_workers: int = 2,
) -> Tuple[FrameDataset, DataLoader]:
    """
    Construct a FrameDataset and a DataLoader for mini-batch training.

    Args:
        frames: (N, H, W, 3) uint8 numpy array.
        batch_size: Mini-batch size.
        shuffle: Whether to shuffle every epoch.
        num_workers: Worker processes for data prefetching.

    Returns:
        (dataset, dataloader) tuple.
    """
    dataset = FrameDataset(frames)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    return dataset, loader
