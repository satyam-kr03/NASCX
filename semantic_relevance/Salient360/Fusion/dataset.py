"""
Dataset for loading aligned triplets of saliency maps:
  (gaze_saliency, object_saliency, ground_truth_saliency)

Handles resolution normalisation and frame alignment between the three sources.
"""

from __future__ import annotations

import os
import glob
import random
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from config import DataConfig


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_map(path: str, target_h: int, target_w: int) -> np.ndarray:
    """
    Load a saliency map from disk, normalise to float32 in [0, 1],
    and resize to the target resolution.

    Supports:
      - 8-bit  grayscale PNG  (uint8,  0–255)
      - 16-bit grayscale PNG  (uint16, 0–65535)
      - 32-bit float TIFF / EXR
    """
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Cannot read saliency map: {path}")

    # If colour, convert to grayscale
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Normalise to [0, 1] float32
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255.0
    elif img.dtype == np.uint16:
        img = img.astype(np.float32) / 65535.0
    else:
        img = img.astype(np.float32)
        peak = img.max()
        if peak > 0:
            img /= peak

    # Resize if necessary
    if img.shape[0] != target_h or img.shape[1] != target_w:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    return img


def discover_triplets(
    gt_dir: str,
    gaze_dir: str,
    obj_dir: str,
    video_names: Optional[List[str]] = None,
) -> List[Tuple[str, str, str, str]]:
    """
    Scan directories and find frames where all three maps exist.

    Returns a list of (video_name, gt_path, gaze_path, obj_path) tuples.

    Directory layout expected:
        gt_dir/<video_name>/<frame>.png
        gaze_dir/<video_name>/salmaps/<frame>.png   (or <video_name>/<frame>.png)
        obj_dir/<video_name>/salmaps/<frame>.png     (or <video_name>/<frame>.png)
    """
    triplets: List[Tuple[str, str, str, str]] = []

    # Determine which videos to use
    if video_names is None:
        # Use videos that have GT saliency maps
        if not os.path.isdir(gt_dir):
            return triplets
        video_names = sorted([
            d for d in os.listdir(gt_dir)
            if os.path.isdir(os.path.join(gt_dir, d))
        ])

    for vname in video_names:
        gt_video_dir = os.path.join(gt_dir, vname)
        if not os.path.isdir(gt_video_dir):
            continue

        # Collect GT frame filenames
        gt_frames = {
            os.path.splitext(f)[0]: os.path.join(gt_video_dir, f)
            for f in os.listdir(gt_video_dir)
            if f.endswith(".png")
        }

        # Locate gaze (SalViT360) saliency maps for this video
        gaze_video_dir = os.path.join(gaze_dir, vname, "salmaps")
        if not os.path.isdir(gaze_video_dir):
            gaze_video_dir = os.path.join(gaze_dir, vname)
        if not os.path.isdir(gaze_video_dir):
            continue

        # Locate object (YOLOv8) saliency maps for this video
        obj_video_dir = os.path.join(obj_dir, vname, "salmaps")
        if not os.path.isdir(obj_video_dir):
            obj_video_dir = os.path.join(obj_dir, vname)
        if not os.path.isdir(obj_video_dir):
            continue

        # Match by frame name
        for frame_id, gt_path in gt_frames.items():
            gaze_path = os.path.join(gaze_video_dir, frame_id + ".png")
            obj_path = os.path.join(obj_video_dir, frame_id + ".png")

            if os.path.isfile(gaze_path) and os.path.isfile(obj_path):
                triplets.append((vname, gt_path, gaze_path, obj_path))

    return triplets


def split_triplets(
    triplets: List[Tuple[str, str, str, str]],
    train_ratio: float = 0.75,
    seed: int = 42,
) -> Tuple[List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]:
    """
    Split triplets into train / val sets, stratified by video.
    Within each video, the first `train_ratio` fraction of frames go to train
    (chronological split to avoid temporal leakage).
    """
    from collections import defaultdict

    by_video: Dict[str, List[Tuple[str, str, str, str]]] = defaultdict(list)
    for t in triplets:
        by_video[t[0]].append(t)

    train, val = [], []
    for vname in sorted(by_video.keys()):
        frames = sorted(by_video[vname], key=lambda t: t[1])  # sort by GT path
        split_idx = int(len(frames) * train_ratio)
        train.extend(frames[:split_idx])
        val.extend(frames[split_idx:])

    return train, val


# ── PyTorch Dataset ─────────────────────────────────────────────────────────

class FusionDataset(Dataset):
    """
    PyTorch dataset that yields (input, target) pairs:
      input  : Tensor [2, H, W]  — channel 0 = gaze, channel 1 = object
      target : Tensor [1, H, W]  — GT saliency map
      fixmap : Tensor [1, H, W]  — GT fixation map (binary, for NSS)
    """

    def __init__(
        self,
        triplets: List[Tuple[str, str, str, str]],
        cfg: DataConfig,
        fixmap_dir: Optional[str] = None,
        augment: bool = False,
    ):
        self.triplets = triplets
        self.height = cfg.height
        self.width = cfg.width
        self.fixmap_dir = fixmap_dir
        self.augment = augment

    def __len__(self) -> int:
        return len(self.triplets)

    def __getitem__(self, idx: int):
        vname, gt_path, gaze_path, obj_path = self.triplets[idx]

        # Load and resize maps to common resolution
        gt = _load_map(gt_path, self.height, self.width)
        gaze = _load_map(gaze_path, self.height, self.width)
        obj = _load_map(obj_path, self.height, self.width)

        # Load fixation map if available (for NSS computation)
        fixmap = np.zeros_like(gt)
        if self.fixmap_dir is not None:
            frame_name = os.path.basename(gt_path)
            fix_path = os.path.join(self.fixmap_dir, vname, frame_name)
            if os.path.isfile(fix_path):
                fixmap = _load_map(fix_path, self.height, self.width)
                # Binarise (it should already be binary, but ensure)
                fixmap = (fixmap > 0.5).astype(np.float32)

        # Data augmentation: random horizontal flip (valid for equirectangular —
        # corresponds to a 180° yaw rotation of the sphere)
        if self.augment and random.random() > 0.5:
            gaze = np.ascontiguousarray(np.flip(gaze, axis=1))
            obj = np.ascontiguousarray(np.flip(obj, axis=1))
            gt = np.ascontiguousarray(np.flip(gt, axis=1))
            fixmap = np.ascontiguousarray(np.flip(fixmap, axis=1))

        # Stack into tensors
        inp = torch.from_numpy(np.stack([gaze, obj], axis=0))   # [2, H, W]
        target = torch.from_numpy(gt[None, ...])                 # [1, H, W]
        fix = torch.from_numpy(fixmap[None, ...])                # [1, H, W]

        return inp, target, fix


def build_dataloaders(
    cfg: DataConfig,
    train_cfg,
    seed: int = 42,
) -> Tuple[DataLoader, DataLoader, int]:
    """
    Discover triplets, split into train/val, and return DataLoaders.

    Returns (train_loader, val_loader, n_total_triplets).
    """
    triplets = discover_triplets(
        gt_dir=cfg.gt_salmap_dir,
        gaze_dir=cfg.gaze_salmap_dir,
        obj_dir=cfg.obj_salmap_dir,
        video_names=cfg.video_names,
    )

    if len(triplets) == 0:
        raise RuntimeError(
            f"No aligned triplets found.\n"
            f"  GT dir:   {cfg.gt_salmap_dir}\n"
            f"  Gaze dir: {cfg.gaze_salmap_dir}\n"
            f"  Obj dir:  {cfg.obj_salmap_dir}\n"
            "Run generate_inputs.py first to produce saliency maps."
        )

    train_triplets, val_triplets = split_triplets(
        triplets, cfg.train_ratio, seed
    )

    print(f"Dataset: {len(triplets)} total frames "
          f"({len(train_triplets)} train, {len(val_triplets)} val)")

    train_ds = FusionDataset(
        train_triplets, cfg,
        fixmap_dir=cfg.gt_fixmap_dir,
        augment=True,
    )
    val_ds = FusionDataset(
        val_triplets, cfg,
        fixmap_dir=cfg.gt_fixmap_dir,
        augment=False,
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=train_cfg.batch_size,
        shuffle=True,
        num_workers=train_cfg.num_workers,
        pin_memory=True,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=train_cfg.batch_size,
        shuffle=False,
        num_workers=train_cfg.num_workers,
        pin_memory=True,
        drop_last=False,
    )

    return train_loader, val_loader, len(triplets)
