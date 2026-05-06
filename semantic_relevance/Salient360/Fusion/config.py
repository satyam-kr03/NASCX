"""
Centralised configuration for the fusion pipeline.

All tuneable parameters are defined as dataclasses so they can be overridden
from the CLI while keeping sensible defaults in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ── Absolute paths ──────────────────────────────────────────────────────────

PROJECT_ROOT = "/home/teaching/Projects/NASCX"
DATA_ROOT = os.path.join(PROJECT_ROOT, "data", "Salient360")

# Inputs
STIMULI_DIR = os.path.join(DATA_ROOT, "Stimuli")
GT_SALMAP_DIR = os.path.join(DATA_ROOT, "processed", "salmaps")
GT_FIXMAP_DIR = os.path.join(DATA_ROOT, "processed", "fixmaps")
GAZE_SALMAP_DIR = os.path.join(DATA_ROOT, "salvit360_saliency")
OBJ_SALMAP_DIR = os.path.join(DATA_ROOT, "yolo_saliency")

# Outputs
CHECKPOINT_DIR = os.path.join(DATA_ROOT, "fusion_checkpoints")
FUSED_OUTPUT_DIR = os.path.join(DATA_ROOT, "fused_saliency")


@dataclass
class DataConfig:
    """Paths and resolution settings for the fusion dataset."""

    gt_salmap_dir: str = GT_SALMAP_DIR
    gt_fixmap_dir: str = GT_FIXMAP_DIR
    gaze_salmap_dir: str = GAZE_SALMAP_DIR
    obj_salmap_dir: str = OBJ_SALMAP_DIR

    # Common working resolution (matches GT saliency maps)
    height: int = 480
    width: int = 960

    # Train / val split ratio (fraction used for training)
    train_ratio: float = 0.75

    # Restrict to these videos (None = use all available)
    video_names: Optional[List[str]] = None


@dataclass
class ModelConfig:
    """Architecture settings for the fusion model."""

    # Model variant: "conv1x1" | "mlp" | "conv3x3"
    variant: str = "conv1x1"

    # Number of input channels (gaze + object)
    in_channels: int = 2

    # Hidden layer width (for mlp and deeper conv variants)
    hidden_channels: int = 16

    # Number of hidden layers
    n_hidden: int = 2

    # Dropout rate (between hidden layers)
    dropout: float = 0.0


@dataclass
class LossConfig:
    """Loss function weights."""

    # KL divergence — useful but can cause output collapse on sparse maps
    # if weighted too heavily; keep moderate
    kl_weight: float = 0.1

    # Primary loss — CC is scale-invariant and directly rewards correct
    # spatial structure without collapsing to near-constant output
    cc_weight: float = 1.0

    # NSS — rewards high predicted values at actual fixation points;
    # prevents the model from going flat
    nss_weight: float = 0.5

    # Smoothness regularisation on fused map
    smoothness_weight: float = 0.0


@dataclass
class TrainConfig:
    """Training hyper-parameters."""

    batch_size: int = 4
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    n_epochs: int = 50
    patience: int = 10          # early stopping patience (0 = disabled)
    device: str = "cuda"        # "cuda" or "cpu"
    seed: int = 42
    num_workers: int = 0        # dataloader workers
    checkpoint_dir: str = CHECKPOINT_DIR
    log_every: int = 5          # print loss every N batches

    # Learning-rate scheduler
    scheduler: str = "cosine"   # "cosine" | "step" | "none"
    step_size: int = 20         # for StepLR
    gamma: float = 0.5          # for StepLR


@dataclass
class PipelineConfig:
    """Top-level config aggregating all sub-configs."""

    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    output_dir: str = FUSED_OUTPUT_DIR
