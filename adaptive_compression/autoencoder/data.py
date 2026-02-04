# autoencoder/data.py

from pathlib import Path
from typing import List, Tuple

import av
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset

from . import DEFAULT_IMG_SIZE


def read_video_pyav(container: av.container.InputContainer, indices: List[int]) -> np.ndarray:
    """
    Read specific frames from a video container using PyAV.

    Args:
        container: PyAV input container
        indices: List of frame indices to read

    Returns:
        Numpy array of frames in RGB format
    """
    frames = []
    container.seek(0)
    start_index = indices[0]
    end_index = indices[-1]
    for i, frame in enumerate(container.decode(video=0)):
        if i > end_index:
            break
        if i >= start_index and i in indices:
            frames.append(frame)
    return np.stack([x.to_ndarray(format="rgb24") for x in frames])


class FrameDataset(Dataset):
    """Dataset for video frames."""

    def __init__(self, frames: np.ndarray, img_size: int = DEFAULT_IMG_SIZE) -> None:
        self.frames = frames
        self.img_size = img_size

    def __len__(self) -> int:
        return len(self.frames)

    def __getitem__(self, idx: int) -> torch.Tensor:
        frame = self.frames[idx]
        frame = torch.from_numpy(frame).float() / 255.0
        frame = frame.permute(2, 0, 1)
        frame = F.interpolate(frame.unsqueeze(0), size=(self.img_size, self.img_size),
                             mode='bilinear', align_corners=False).squeeze(0)
        return frame


def load_data(video_path: Path, train_ratio: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load and split video frames into train and test sets.

    Args:
        video_path: Path to the video file
        train_ratio: Ratio of frames to use for training

    Returns:
        Tuple of (train_frames, test_frames)
    """
    import logging
    try:
        container = av.open(str(video_path))
        total_frames = container.streams.video[0].frames
        logging.info(f"Video has {total_frames} frames, resolution: {container.streams.video[0].width}x{container.streams.video[0].height}")

        indices = list(range(total_frames))
        all_frames = read_video_pyav(container, indices)
        logging.info(f"Extracted {len(all_frames)} frames")

        # Split data
        indices_shuffled = np.random.permutation(len(all_frames))
        train_size = int(train_ratio * len(all_frames))
        train_indices = indices_shuffled[:train_size]
        test_indices = indices_shuffled[train_size:]

        frames_train = all_frames[train_indices]
        frames_test = all_frames[test_indices]

        logging.info(f"Train: {len(frames_train)}, Test: {len(frames_test)}")

        return frames_train, frames_test

    except Exception as e:
        logging.error(f"Error loading video data: {e}")
        raise