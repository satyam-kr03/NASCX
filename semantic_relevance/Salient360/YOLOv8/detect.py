"""
YOLOv8 detection on tangent-plane patches with coordinate reprojection and
cross-patch non-maximum suppression.

Provides:
  - detect_on_patches(): run YOLO on each patch, reproject to equirectangular
  - cross_patch_nms(): merge duplicate detections from overlapping patches
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

from ultralytics import YOLO

from equi2pers import PatchInfo, patch_bbox_to_equirect


@dataclass
class Detection:
    """A single object detection in equirectangular coordinates."""
    x1: float          # left   (equirect pixels)
    y1: float          # top    (equirect pixels)
    x2: float          # right  (equirect pixels, may exceed erp_w for wrap)
    y2: float          # bottom (equirect pixels)
    confidence: float  # detection confidence [0, 1]
    class_id: int      # COCO class index
    class_name: str    # human-readable class name
    patch_idx: int     # which patch this detection came from


def detect_on_patches(model: YOLO,
                      patches: List[PatchInfo],
                      patch_size: Tuple[int, int],
                      erp_w: int,
                      erp_h: int,
                      conf: float = 0.25,
                      iou: float = 0.45,
                      imgsz: int = 640,
                      device: str = "0") -> List[Detection]:
    """
    Run YOLOv8 on every tangent-plane patch and reproject detections.

    Parameters
    ----------
    model : ultralytics.YOLO
        Loaded YOLOv8 model.
    patches : list of PatchInfo
        Patches extracted by equi2pers.equirect_to_patches().
    patch_size : (width, height)
        Pixel dimensions of each patch.
    erp_w, erp_h : int
        Equirectangular image dimensions.
    conf, iou, imgsz, device :
        Standard YOLO inference parameters.

    Returns
    -------
    List[Detection]
        All detections across all patches, coordinates in equirect space.
        Duplicates from overlapping patches are NOT yet removed — call
        cross_patch_nms() afterwards.
    """
    all_detections: List[Detection] = []

    # Batch images for inference
    images = [p.image for p in patches]

    results = model.predict(
        source=images,
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        device=device,
        verbose=False,
    )

    for patch_info, result in zip(patches, results):
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for i in range(len(boxes)):
            # Patch-local bounding box (xyxy in patch pixel coords)
            bx1, by1, bx2, by2 = boxes.xyxy[i].cpu().numpy()
            conf_score = float(boxes.conf[i].cpu())
            cls_id = int(boxes.cls[i].cpu())
            cls_name = result.names[cls_id]

            # Reproject to equirectangular space
            ex1, ey1, ex2, ey2 = patch_bbox_to_equirect(
                bx1, by1, bx2, by2,
                patch_info, patch_size,
                erp_w, erp_h,
            )

            all_detections.append(Detection(
                x1=ex1, y1=ey1, x2=ex2, y2=ey2,
                confidence=conf_score,
                class_id=cls_id,
                class_name=cls_name,
                patch_idx=patch_info.index,
            ))

    return all_detections


def _iou_equirect(a: Detection, b: Detection, erp_w: int) -> float:
    """
    Compute IoU between two detections in equirectangular space,
    handling 360° wrap-around.
    """
    def _overlap_1d(a1, a2, b1, b2, wrap_w=None):
        """Overlap length in 1D, optionally with wrap-around."""
        if wrap_w is not None:
            # Normalise: make sure a2 >= a1 and b2 >= b1
            if a2 < a1:
                a2 += wrap_w
            if b2 < b1:
                b2 += wrap_w

            # Try both the original and a shifted version
            best = 0
            for shift in [0, wrap_w]:
                sa1, sa2 = a1 + shift, a2 + shift
                overlap = max(0, min(sa2, b2) - max(sa1, b1))
                best = max(best, overlap)
                sb1, sb2 = b1 + shift, b2 + shift
                overlap = max(0, min(a2, sb2) - max(a1, sb1))
                best = max(best, overlap)
            return best
        else:
            return max(0, min(a2, b2) - max(a1, b1))

    # Widths (handling wrap)
    aw = a.x2 - a.x1 if a.x2 >= a.x1 else (a.x2 + erp_w - a.x1)
    bw = b.x2 - b.x1 if b.x2 >= b.x1 else (b.x2 + erp_w - b.x1)
    ah = a.y2 - a.y1
    bh = b.y2 - b.y1

    if aw <= 0 or bw <= 0 or ah <= 0 or bh <= 0:
        return 0.0

    x_overlap = _overlap_1d(a.x1, a.x2, b.x1, b.x2, wrap_w=erp_w)
    y_overlap = _overlap_1d(a.y1, a.y2, b.y1, b.y2)

    inter = x_overlap * y_overlap
    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def cross_patch_nms(detections: List[Detection],
                    erp_w: int,
                    iou_threshold: float = 0.5) -> List[Detection]:
    """
    Non-maximum suppression across patches in equirectangular space.

    Merges duplicate detections that arise because adjacent patches overlap.
    Only suppresses detections of the *same class*.

    Parameters
    ----------
    detections : list of Detection
    erp_w : int
        Width of the equirectangular image (for wrap-around IoU).
    iou_threshold : float
        IoU threshold above which a lower-confidence detection is suppressed.

    Returns
    -------
    List[Detection]
        Filtered detections (duplicates removed).
    """
    if len(detections) == 0:
        return []

    # Group by class
    classes = set(d.class_id for d in detections)
    kept: List[Detection] = []

    for cls_id in classes:
        cls_dets = [d for d in detections if d.class_id == cls_id]
        # Sort by confidence descending
        cls_dets.sort(key=lambda d: d.confidence, reverse=True)

        suppressed = [False] * len(cls_dets)
        for i in range(len(cls_dets)):
            if suppressed[i]:
                continue
            for j in range(i + 1, len(cls_dets)):
                if suppressed[j]:
                    continue
                if _iou_equirect(cls_dets[i], cls_dets[j], erp_w) > iou_threshold:
                    suppressed[j] = True

        kept.extend(d for d, s in zip(cls_dets, suppressed) if not s)

    return kept
