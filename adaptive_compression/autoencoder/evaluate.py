# autoencoder/evaluate.py
#
# Streaming evaluation of autoencoder compression at various latent
# dimensions.  Processes one test frame at a time so that total memory
# stays bounded (plus the model weights on device).

import logging
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np

from . import DEFAULT_LATENT_DIMS, DEFAULT_IMG_SIZE
from .models import AutoencoderCompressor


def evaluate_compression(
    compressor: AutoencoderCompressor,
    video_path: Path,
    test_indices: Set[int],
    encoded_sizes: List[Dict],
    latent_dims: List[int] = DEFAULT_LATENT_DIMS,
    img_size: int = DEFAULT_IMG_SIZE,
    total_frames: int = 0,
) -> List[Dict[str, Any]]:
    """
    Evaluate autoencoder compression at different latent dimensions by
    streaming test frames from disk.

    For every test frame *and* every requested latent dimension, one result
    row is emitted.  An additional row per frame with ``latent_dim=0``
    records the uncompressed baseline (raw pixel size).

    Memory note
    -----------
    Only **one frame** is in memory at a time (plus the model weights on
    device).  The encoded-size list is tiny.

    Parameters
    ----------
    compressor : AutoencoderCompressor
        Manager holding all trained models.
    video_path : Path
        Path to the source video (decoded on the fly).
    test_indices : set[int]
        Which frame indices belong to the test set.
    encoded_sizes : list[dict]
        Per-frame ``{"pkt_size": int, "pict_type": str}`` from ffprobe,
        aligned by decode order (index 0 = first frame).
    latent_dims : list[int]
        Latent dimensions to evaluate.
    img_size : int
        Working resolution (square).
    total_frames : int
        Total number of frames in the video.  Used to amortise the
        one-time model weight cost across all frames.

    Returns
    -------
    list[dict]
        One dict per (frame, latent_dim) combination.
    """
    from .data import stream_test_frames

    all_results: List[Dict[str, Any]] = []

    n_test = len(test_indices)
    # Use total video frames for amortisation (model is shared across all)
    n_amort = total_frames if total_frames > 0 else n_test
    H = W = img_size
    C = 3
    raw_size_bytes = H * W * C  # uint8: 1 byte / channel

    logging.info("Evaluating autoencoder compression at different latent dimensions...")
    logging.info(f"  Test frames  : {n_test}")
    logging.info(f"  Latent dims  : {latent_dims}")
    logging.info(f"  Working res  : {W}x{H}")
    logging.info("=" * 60)

    done = 0
    for frame_idx, frame_uint8 in stream_test_frames(video_path, test_indices, img_size):
        # Normalise to [0, 1] – single frame, tiny memory
        frame_f32 = frame_uint8.astype(np.float32) / 255.0

        # Encoded bitstream size for this frame (from ffprobe)
        if frame_idx < len(encoded_sizes):
            enc_info = encoded_sizes[frame_idx]
            enc_size = enc_info["pkt_size"]
            pict_type = enc_info["pict_type"]
        else:
            enc_size = 0
            pict_type = "?"

        # --- Uncompressed baseline row (latent_dim == 0) ---------------
        all_results.append({
            "frame": frame_idx,
            "latent_dim": 0,
            "mse": 0.0,
            "ae_size_bytes": raw_size_bytes,
            "encoded_size_bytes": enc_size,
            "raw_size_bytes": raw_size_bytes,
            "pict_type": pict_type,
        })

        # --- Autoencoder-compressed rows --------------------------------
        for dim in latent_dims:
            reconstructed = compressor.compress_and_reconstruct(
                frame_f32, latent_dim=dim,
            )

            # MSE in pixel-value domain ([0, 255])
            mse = float(np.mean((reconstructed - frame_f32) ** 2)) * (255.0 ** 2)

            # Size accounting (float32 = 4 bytes):
            #   per-frame : latent vector = dim × 4
            #   one-time  : model params × 4  (amortised over all frames)
            latent_bytes = dim * 4
            n_params = compressor.get_num_params(dim)
            model_bytes = n_params * 4
            ae_size_bytes = int(latent_bytes + model_bytes / n_amort)

            all_results.append({
                "frame": frame_idx,
                "latent_dim": dim,
                "mse": mse,
                "ae_size_bytes": ae_size_bytes,
                "encoded_size_bytes": enc_size,
                "raw_size_bytes": raw_size_bytes,
                "pict_type": pict_type,
            })

        done += 1
        if done % 500 == 0 or done == n_test:
            logging.info(f"  Processed {done}/{n_test} test frames")

    logging.info("=" * 60)
    logging.info("Evaluation complete!")
    return all_results
