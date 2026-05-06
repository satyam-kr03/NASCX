"""
Object saliency map generation from YOLOv8 detections.

Converts a list of Detection objects (in equirectangular coordinates) into a
continuous saliency heatmap that is directly comparable to gaze-based saliency
maps produced by SalViT360.
"""

from __future__ import annotations

import math
import numpy as np
import cv2
from typing import Dict, List, Tuple

from detect import Detection


def detections_to_saliency(detections: List[Detection],
                           erp_w: int,
                           erp_h: int,
                           class_weights: Dict[int, float] | None = None,
                           default_weight: float = 1.0,
                           blur_sigma: float = 20.0) -> np.ndarray:
    """
    Build an object-level saliency map from equirectangular detections.

    Steps:
      1. For each detection, fill its bounding box with a value equal to
         confidence × class_weight.
      2. Where boxes overlap, take the maximum value (not sum) so saliency
         stays bounded.
      3. Apply Gaussian blur to smooth the hard box edges into a continuous heatmap.
      4. Normalise to [0, 1].

    Parameters
    ----------
    detections : list of Detection
        Post-NMS detections in equirectangular pixel coordinates.
    erp_w, erp_h : int
        Equirectangular image dimensions.
    class_weights : dict
        Mapping from COCO class_id → weight multiplier.
    default_weight : float
        Weight for classes not in class_weights.
    blur_sigma : float
        Standard deviation of the Gaussian blur (pixels).

    Returns
    -------
    np.ndarray of shape (erp_h, erp_w), float32, values in [0, 1].
    """
    if class_weights is None:
        class_weights = {}

    sal_map = np.zeros((erp_h, erp_w), dtype=np.float32)

    for det in detections:
        w = class_weights.get(det.class_id, default_weight)
        value = det.confidence * w

        # Clamp y coordinates
        iy1 = max(0, int(round(det.y1)))
        iy2 = min(erp_h, int(round(det.y2)))
        if iy2 <= iy1:
            continue

        # Handle 360° wrap-around on x
        ix1 = int(round(det.x1)) % erp_w
        ix2 = int(round(det.x2))

        if ix2 > erp_w:
            # Box wraps around the seam
            ix2_wrapped = ix2 % erp_w
            # Fill the right portion: ix1 → erp_w
            sal_map[iy1:iy2, ix1:erp_w] = np.maximum(
                sal_map[iy1:iy2, ix1:erp_w], value
            )
            # Fill the left portion: 0 → ix2_wrapped
            if ix2_wrapped > 0:
                sal_map[iy1:iy2, 0:ix2_wrapped] = np.maximum(
                    sal_map[iy1:iy2, 0:ix2_wrapped], value
                )
        else:
            ix2 = min(erp_w, ix2)
            if ix2 > ix1:
                sal_map[iy1:iy2, ix1:ix2] = np.maximum(
                    sal_map[iy1:iy2, ix1:ix2], value
                )

    # Gaussian blur to create smooth heatmap
    if blur_sigma > 0 and sal_map.max() > 0:
        # Kernel size must be odd; use 6σ rounded up to the next odd integer
        ksize = int(math.ceil(blur_sigma * 6)) | 1
        sal_map = cv2.GaussianBlur(sal_map, (ksize, ksize), blur_sigma)

    # Normalise to [0, 1]
    peak = sal_map.max()
    if peak > 0:
        sal_map /= peak

    return sal_map


def save_saliency_map(sal_map: np.ndarray, path: str,
                      colormap: int = cv2.COLORMAP_JET) -> None:
    """Save a saliency map as a colour-mapped PNG."""
    vis = (sal_map * 255).astype(np.uint8)
    colour = cv2.applyColorMap(vis, colormap)
    cv2.imwrite(path, colour)


def save_saliency_raw(sal_map: np.ndarray, path: str) -> None:
    """Save saliency map as a single-channel 16-bit grayscale PNG (lossless)."""
    vis = (sal_map * 65535).astype(np.uint16)
    cv2.imwrite(path, vis)


def overlay_saliency(frame: np.ndarray, sal_map: np.ndarray,
                     alpha: float = 0.5,
                     colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
    """Return a blended overlay of the saliency map on top of the frame."""
    vis = (sal_map * 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(vis, colormap)
    if heatmap.shape[:2] != frame.shape[:2]:
        heatmap = cv2.resize(heatmap, (frame.shape[1], frame.shape[0]))
    blended = cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
    return blended
