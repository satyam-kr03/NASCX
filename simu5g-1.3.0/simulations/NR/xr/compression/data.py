# compression/data.py
#
# Streaming video frame loading for memory-efficient PCA compression.
# Frames are decoded lazily from disk, resized to a working resolution,
# and yielded one at a time so that only a small batch resides in memory.

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

import av
import cv2
import numpy as np

from constants import DEFAULT_IMG_SIZE, RANDOM_SEED


# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------

def get_video_info(video_path: Path) -> Tuple[int, int, int]:
    """
    Return (total_frames, height, width) for the given video.

    Uses ffprobe to get a reliable frame count (the container metadata
    field ``nb_frames`` is often absent for mp4/mkv downloaded via yt-dlp).
    Falls back to full decode if ffprobe is unavailable.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-count_frames",
                "-show_entries", "stream=nb_read_frames,height,width",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True, text=True, check=True, timeout=600,
        )
        info = json.loads(result.stdout)
        stream = info["streams"][0]
        total_frames = int(stream["nb_read_frames"])
        height = int(stream["height"])
        width = int(stream["width"])
        return total_frames, height, width

    except (subprocess.CalledProcessError, FileNotFoundError, KeyError) as exc:
        logging.warning(f"ffprobe frame-count failed ({exc}); falling back to PyAV decode")
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        height, width = stream.height, stream.width
        container.seek(0)
        total = sum(1 for _ in container.decode(video=0))
        container.close()
        return total, height, width


# ---------------------------------------------------------------------------
# Per-frame encoded bitstream sizes (from ffprobe)
# ---------------------------------------------------------------------------

def get_encoded_frame_sizes(video_path: Path) -> List[Dict]:
    """
    Extract per-frame encoded packet sizes and picture types using ffprobe.

    Returns a list of dicts, one per decoded frame in display order::

        [{"pkt_size": 35912, "pict_type": "I"}, ...]

    This gives meaningful per-frame size variation (I vs P vs B frames)
    that reflects frame complexity in the original codec.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "frame=pkt_size,pict_type",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True, text=True, check=True, timeout=600,
    )
    data = json.loads(result.stdout)
    frames = []
    for f in data.get("frames", []):
        frames.append({
            "pkt_size": int(f["pkt_size"]),
            "pict_type": f.get("pict_type", "?"),
        })
    return frames


# ---------------------------------------------------------------------------
# Resize helper
# ---------------------------------------------------------------------------

def _resize_frame(frame: np.ndarray, img_size: int) -> np.ndarray:
    """
    Resize a frame to (img_size, img_size) using bilinear interpolation.

    Args:
        frame: (H, W, 3) uint8 numpy array.
        img_size: Target square size.

    Returns:
        (img_size, img_size, 3) uint8 numpy array.
    """
    return cv2.resize(frame, (img_size, img_size), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------------------
# Streaming frame generators
# ---------------------------------------------------------------------------

def _decode_frames(
    video_path: Path,
    wanted_indices: Optional[Set[int]] = None,
    img_size: int = DEFAULT_IMG_SIZE,
) -> Generator[Tuple[int, np.ndarray], None, None]:
    """
    Yield ``(frame_index, frame_rgb_uint8)`` tuples by decoding the video.

    Each frame is resized to ``(img_size, img_size)`` before yielding.
    If *wanted_indices* is given, only frames whose index is in the set
    are yielded; all others are skipped (but still decoded because video
    codecs require sequential access).
    """
    container = av.open(str(video_path))
    container.seek(0)
    try:
        for i, frame in enumerate(container.decode(video=0)):
            if wanted_indices is not None and i not in wanted_indices:
                continue
            rgb = frame.to_ndarray(format="rgb24")
            resized = _resize_frame(rgb, img_size)
            yield i, resized
    finally:
        container.close()


def sample_training_frames(
    video_path: Path,
    total_frames: int,
    train_ratio: float,
    img_size: int = DEFAULT_IMG_SIZE,
    seed: int = RANDOM_SEED,
) -> Tuple[np.ndarray, Set[int], Set[int]]:
    """
    Decode and return the training-subset frames as a single numpy array.

    Frames are resized to ``(img_size, img_size)`` and selected via a
    random permutation split.

    Returns
    -------
    train_frames : np.ndarray
        Shape ``(n_train, img_size, img_size, 3)`` uint8.
    train_indices : set[int]
        Frame indices used for training.
    test_indices : set[int]
        Frame indices reserved for testing.
    """
    rng = np.random.RandomState(seed)
    perm = rng.permutation(total_frames)
    train_size = int(train_ratio * total_frames)
    if train_size == 0:
        raise ValueError(
            f"train_ratio={train_ratio} yields 0 training frames from "
            f"{total_frames} total frames.  Increase train_ratio or use a "
            "longer video."
        )
    train_idx_set = set(perm[:train_size].tolist())
    test_idx_set = set(perm[train_size:].tolist())

    if not test_idx_set:
        logging.warning(
            "No test frames after split (all frames used for training).  "
            "Falling back to evaluating on the training set."
        )
        test_idx_set = train_idx_set.copy()

    logging.info(f"Collecting {len(train_idx_set)} training frames (streaming, {img_size}x{img_size})...")
    train_frames: List[np.ndarray] = []
    for _, frame in _decode_frames(video_path, train_idx_set, img_size):
        train_frames.append(frame)

    train_array = np.stack(train_frames)
    logging.info(f"Train: {len(train_idx_set)}, Test: {len(test_idx_set)}")
    return train_array, train_idx_set, test_idx_set


def stream_test_frames(
    video_path: Path,
    test_indices: Set[int],
    img_size: int = DEFAULT_IMG_SIZE,
) -> Generator[Tuple[int, np.ndarray], None, None]:
    """
    Yield ``(frame_index, frame_rgb_uint8)`` for every test-set frame.

    Frames are resized to ``(img_size, img_size)``.
    Only one frame is in memory at a time.
    """
    yield from _decode_frames(video_path, test_indices, img_size)
