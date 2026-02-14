# autoencoder/evaluate.py

import logging
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import torch
import torch.nn.functional as F
from tqdm import tqdm

from . import DEFAULT_KEEP_RATIOS, DEFAULT_IMG_SIZE
from .utils import save_results, plot_results


def evaluate_compression(model: torch.nn.Module, test_frames: np.ndarray, device: torch.device,
                        keep_ratios: List[float] = DEFAULT_KEEP_RATIOS, img_size: int = DEFAULT_IMG_SIZE) -> List[Dict[str, Any]]:
    """
    Evaluate compression at different keep ratios.

    Args:
        model: Trained model
        test_frames: Test frames
        device: Device to evaluate on
        keep_ratios: List of keep ratios to evaluate
        img_size: Image size for processing

    Returns:
        List of evaluation results
    """
    all_results = []
    logging.info("Evaluating compression at different rates...")
    logging.info("=" * 60)

    # Add original frame sizes with MSE = 0
    original_size_bytes = img_size * img_size * 3 * 4
    for frame_idx in range(len(test_frames)):
        all_results.append({
            'frame': frame_idx + 1,
            'keep_ratio': 1.0,
            'mse': 0.0,
            'size_bytes': original_size_bytes
        })

    model.eval()
    for keep_ratio in keep_ratios:
        compression_pct = int((1 - keep_ratio) * 100)
        logging.info(f"Keep ratio: {keep_ratio:.2f} ({compression_pct}% compression)")

        for frame_idx in tqdm(range(len(test_frames)), desc="Processing frames"):
            frame = test_frames[frame_idx]
            frame_tensor = torch.from_numpy(frame).float() / 255.0
            frame_tensor = frame_tensor.permute(2, 0, 1).unsqueeze(0)
            frame_tensor = F.interpolate(frame_tensor, size=(img_size, img_size),
                                        mode='bilinear', align_corners=False)
            frame_tensor = frame_tensor.to(device)

            # Compress and reconstruct
            reconstructed, _, keep_count = model.compress_and_reconstruct(
                frame_tensor, keep_ratio=keep_ratio
            )

            # Calculate size including spatial structure overhead
            # The autoencoder latent is 7x7 which maps to the 224x224 image
            # Each stored coefficient carries spatial information that must be preserved
            # Scale by (img_size / latent_spatial_area) to match PCA's spatial accounting
            latent_spatial_area = 7 * 7  # 49 latent spatial positions
            spatial_scale = img_size / latent_spatial_area
            size_bytes = int(keep_count * 4 * spatial_scale)  # 4 bytes per float32

            # Calculate MSE. We scale by 255^2 to match pixel value range
            mse = F.mse_loss(reconstructed, frame_tensor).item()*255*255

            all_results.append({
                'frame': frame_idx + 1,
                'keep_ratio': keep_ratio,
                'mse': mse,
                'size_bytes': size_bytes
            })


    logging.info("=" * 60)
    logging.info("Evaluation complete!")
    return all_results