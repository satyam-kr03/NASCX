"""
Configuration for the YOLOv8 equirectangular object saliency pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from pathlib import Path


@dataclass
class PatchConfig:
    """Tangent (gnomonic) projection patch layout."""

    # Field of view per patch in degrees
    fov: float = 90.0

    # Number of latitude rows and patches-per-row.
    # Default: 4 rows → [3, 6, 6, 3] = 18 patches covering the sphere.
    nrows: int = 4
    num_cols: List[int] = field(default_factory=lambda: [3, 6, 6, 3])
    phi_centers: List[float] = field(default_factory=lambda: [-67.5, -22.5, 22.5, 67.5])

    # Resolution of each extracted perspective patch (width, height)
    patch_size: Tuple[int, int] = (640, 640)


@dataclass
class DetectionConfig:
    """YOLOv8 detection settings."""

    # Path to YOLOv8 weights
    weights: str = str(
        Path(__file__).parent / "yolov8n.pt"
    )

    # Confidence threshold for detections
    conf_threshold: float = 0.25

    # IoU threshold for NMS within a single patch
    iou_threshold: float = 0.45

    # IoU threshold for cross-patch NMS (merging overlapping detections)
    cross_patch_iou_threshold: float = 0.5

    # Device: "cuda", "cpu", or device index
    device: str = "0"

    # Input image size for YOLO inference
    imgsz: int = 640


@dataclass
class SaliencyConfig:
    """Object saliency map generation settings."""

    # Output saliency map size (width, height) — matches equirectangular frame
    output_size: Tuple[int, int] = (1920, 960)

    # Gaussian blur sigma (in pixels) applied to the raw box saliency
    blur_sigma: float = 20.0

    # Per-class saliency weight multipliers (COCO class IDs).
    # person=0, face categories aren't in COCO but we weight person highly.
    class_weights: dict = field(default_factory=lambda: {
        0: 3.0,   # person — universally salient in VR
        # Other salient classes get moderate boosts
        1: 1.5,   # bicycle
        2: 1.5,   # car
        3: 1.5,   # motorcycle
        5: 1.5,   # bus
        7: 1.5,   # truck
        14: 1.2,  # bird
        15: 2.0,  # cat
        16: 2.0,  # dog
        17: 1.5,  # horse
        18: 1.5,  # sheep
        19: 1.5,  # cow
        24: 1.2,  # backpack (proxy for humans)
        26: 1.2,  # handbag
    })

    # Default weight for classes not in the dict above
    default_class_weight: float = 1.0


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""

    patches: PatchConfig = field(default_factory=PatchConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    saliency: SaliencyConfig = field(default_factory=SaliencyConfig)

    # Input equirectangular frame size (width, height)
    equirect_size: Tuple[int, int] = (1920, 960)

    # Paths
    data_root: str = "/home/teaching/Projects/NASCX/data/Salient360"
    output_dir: str = "/home/teaching/Projects/NASCX/data/Salient360/yolo_saliency"
