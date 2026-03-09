# pca/evaluate.py
#
# Streaming evaluation of PCA compression at various component counts.
# Processes one test frame at a time so that total memory stays bounded.

import logging
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np

from . import DEFAULT_COMPONENTS, DEFAULT_IMG_SIZE
from .models import PCACompressor


def evaluate_compression(
    compressor: PCACompressor,
    video_path: Path,
    test_indices: Set[int],
    encoded_sizes: List[Dict],
    components_list: List[int] = DEFAULT_COMPONENTS,
    img_size: int = DEFAULT_IMG_SIZE,
    total_frames: int = 0,
) -> List[Dict[str, Any]]:
    """
    Evaluate PCA compression at different component counts by streaming
    test frames from disk.

    For every test frame *and* every requested component count, one result
    row is emitted.  An additional row per frame with ``components == 0``
    records the uncompressed baselines (encoded bitstream size and raw
    pixel size).

    Memory note
    -----------
    Only **one frame** is in memory at a time (plus the PCA model itself).
    The encoded-size list is tiny (a few hundred KB for ~7 000 frames).

    Parameters
    ----------
    compressor : PCACompressor
        Already-fitted PCA model.
    video_path : Path
        Path to the source video (decoded on the fly).
    test_indices : set[int]
        Which frame indices belong to the test set.
    encoded_sizes : list[dict]
        Per-frame ``{"pkt_size": int, "pict_type": str}`` from ffprobe,
        aligned by decode order (index 0 = first frame).
    components_list : list[int]
        Component counts to evaluate.
    total_frames : int
        Total number of frames in the video.  Used to amortise the
        one-time PCA model cost (basis + mean) across all frames,
        since the model is shared for the entire video.

    Returns
    -------
    list[dict]
        One dict per (frame, component_count) combination.
    """
    from .data import stream_test_frames

    all_results: List[Dict[str, Any]] = []

    n_test = len(test_indices)
    # Use total video frames for amortisation (model is shared across all)
    n_amort = total_frames if total_frames > 0 else n_test
    H, W, C = compressor.frame_shape          # working resolution (img_size × img_size × 3)
    raw_size_bytes = H * W * C                # uint8: 1 byte / channel
    n_pixels = H * W * C                      # scalar count per frame

    # Pre-compute cumulative explained variance for each component count
    cumvar = np.cumsum(compressor.pca.explained_variance_ratio_)
    for n_comp in components_list:
        var_pct = cumvar[n_comp - 1] * 100
        logging.info(f"  {n_comp:4d} components → {var_pct:.2f}% variance explained")

    logging.info("Evaluating PCA compression at different component counts...")
    logging.info(f"  Test frames : {n_test}")
    logging.info(f"  Components  : {components_list}")
    logging.info(f"  Working res : {W}x{H}")
    logging.info("=" * 60)

    done = 0
    for frame_idx, frame_uint8 in stream_test_frames(video_path, test_indices, img_size):
        # Normalise to [0, 1] — single frame, tiny memory
        frame_f32 = frame_uint8.astype(np.float32) / 255.0

        # Encoded bitstream size for this frame (from ffprobe)
        if frame_idx < len(encoded_sizes):
            enc_info = encoded_sizes[frame_idx]
            enc_size = enc_info["pkt_size"]
            pict_type = enc_info["pict_type"]
        else:
            enc_size = 0
            pict_type = "?"

        # --- Uncompressed baseline row (components == 0) ---------------
        all_results.append({
            "frame": frame_idx,
            "components": 0,
            "mse": 0.0,
            "size_bytes": raw_size_bytes,
            "frame_complexity": enc_size,
            "raw_size_bytes": raw_size_bytes,
            "pict_type": pict_type,
        })

        # --- PCA-compressed rows ---------------------------------------
        for n_comp in components_list:
            reconstructed = compressor.compress_and_reconstruct(
                frame_f32, n_components=n_comp,
            )

            # MSE in pixel-value domain ([0, 255])
            mse = float(np.mean((reconstructed - frame_f32) ** 2)) * 255.0 * 255.0

            # Storage accounting (float32 = 4 bytes):
            #   per-frame  : n_comp coefficients
            #   one-time   : basis (n_comp × n_pixels) + mean (n_pixels)
            # Amortise one-time cost over entire video (all frames).
            coeffs_bytes = n_comp * 4
            model_bytes = (n_comp + 1) * n_pixels * 4
            pca_size_bytes = int(coeffs_bytes + model_bytes / n_amort)

            # Cumulative explained variance ratio for this component count
            expl_var = float(cumvar[n_comp - 1])

            all_results.append({
                "frame": frame_idx,
                "components": n_comp,
                "mse": mse,
                "size_bytes": pca_size_bytes,
                "frame_complexity": enc_size,
                "raw_size_bytes": raw_size_bytes,
                "pict_type": pict_type,
                "explained_variance": expl_var,
            })

        done += 1
        if done % 500 == 0 or done == n_test:
            logging.info(f"  Processed {done}/{n_test} test frames")

    logging.info("=" * 60)
    logging.info("Evaluation complete!")
    return all_results
