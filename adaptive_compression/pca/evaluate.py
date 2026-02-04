# pca/evaluate.py

import logging
from typing import List, Dict, Any

import numpy as np
import torch
import torch.nn.functional as F

from . import DEFAULT_COMPONENTS, DEFAULT_IMG_SIZE
from .models import PCACompressor


def evaluate_compression(compressor: PCACompressor, test_frames: np.ndarray,
                        components_list: List[int] = DEFAULT_COMPONENTS,
                        img_size: int = DEFAULT_IMG_SIZE) -> List[Dict[str, Any]]:
    """
    Evaluate PCA compression at different component counts.

    Args:
        compressor: Fitted PCACompressor
        test_frames: Test frames
        components_list: List of component counts to evaluate
        img_size: Image size for processing

    Returns:
        List of evaluation results
    """
    all_results = []
    logging.info("Evaluating PCA compression at different component counts...")
    logging.info("=" * 60)

    for n_components in components_list:
        logging.info(f"Components: {n_components}")

        for frame_idx in range(len(test_frames)):
            frame = test_frames[frame_idx]
            
            # Normalize and resize frame
            frame_tensor = torch.from_numpy(frame).float() / 255.0
            frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            frame_tensor = F.interpolate(frame_tensor, size=(img_size, img_size),
                                        mode='bilinear', align_corners=False)
            frame_np = frame_tensor.squeeze(0).permute(1, 2, 0).numpy()
            
            # Compress and reconstruct
            reconstructed, size_bytes = compressor.compress_and_reconstruct(
                frame_np, n_components=n_components
            )

            # Calculate MSE (scaled to 0-255 range to match autoencoder)
            mse = np.mean((reconstructed - frame_np) ** 2) * 255 * 255

            all_results.append({
                'frame': frame_idx + 1,
                'components': n_components,
                'mse': mse,
                'size_bytes': size_bytes
            })

    logging.info("=" * 60)
    logging.info("Evaluation complete!")
    return all_results
