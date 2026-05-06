"""
Evaluation and comparison of individual vs. fused saliency maps.

Loads a trained fusion checkpoint and compares:
  1. H_gaze  alone  (SalViT360 prediction)
  2. H_obj   alone  (YOLOv8 object saliency)
  3. H_fused        (learned fusion)

against the Salient360! ground-truth fixation maps, producing a side-by-side
metrics table that validates the complementarity argument.
"""

from __future__ import annotations

import os
import json
from collections import defaultdict
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch

from config import PipelineConfig, ModelConfig, DataConfig
from dataset import discover_triplets, split_triplets, _load_map
from model import build_model
from losses import compute_all_metrics


def load_checkpoint(ckpt_path: str, device: torch.device):
    """Load a trained fusion model from checkpoint."""
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)

    model_cfg = ModelConfig(**ckpt["config"]["model"])
    model = build_model(model_cfg).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    print(f"Loaded checkpoint from epoch {ckpt.get('epoch', '?')}")
    if "val_metrics" in ckpt:
        print(f"  Checkpoint val metrics: {ckpt['val_metrics']}")

    return model, model_cfg


def evaluate_all(
    cfg: PipelineConfig,
    checkpoint_path: Optional[str] = None,
    split: str = "val",
) -> Dict[str, Dict[str, float]]:
    """
    Run full evaluation comparing gaze-only, object-only, and fused maps.

    Parameters
    ----------
    cfg : PipelineConfig
    checkpoint_path : path to trained fusion model (.pt)
    split : "val" or "all"

    Returns
    -------
    Dict mapping {"gaze": metrics, "object": metrics, "fused": metrics}
    """
    device = torch.device(cfg.train.device if torch.cuda.is_available() else "cpu")

    # Discover data
    triplets = discover_triplets(
        gt_dir=cfg.data.gt_salmap_dir,
        gaze_dir=cfg.data.gaze_salmap_dir,
        obj_dir=cfg.data.obj_salmap_dir,
        video_names=cfg.data.video_names,
    )

    if split == "val":
        _, triplets = split_triplets(triplets, cfg.data.train_ratio, cfg.train.seed)
    print(f"Evaluating on {len(triplets)} frames ({split} split)")

    # Load fusion model
    model = None
    if checkpoint_path and os.path.isfile(checkpoint_path):
        model, _ = load_checkpoint(checkpoint_path, device)
    else:
        print("WARNING: No checkpoint provided — skipping fused evaluation")

    # Collect metrics for each branch
    results = {
        "gaze": defaultdict(list),
        "object": defaultdict(list),
    }
    if model is not None:
        results["fused"] = defaultdict(list)

    for vname, gt_path, gaze_path, obj_path in triplets:
        h, w = cfg.data.height, cfg.data.width

        gt = _load_map(gt_path, h, w)
        gaze = _load_map(gaze_path, h, w)
        obj = _load_map(obj_path, h, w)

        # Fixation map
        fixmap = None
        if cfg.data.gt_fixmap_dir:
            frame_name = os.path.basename(gt_path)
            fix_path = os.path.join(cfg.data.gt_fixmap_dir, vname, frame_name)
            if os.path.isfile(fix_path):
                fixmap = _load_map(fix_path, h, w)
                fixmap = (fixmap > 0.5).astype(np.float32)

        # Evaluate gaze-only
        m_gaze = compute_all_metrics(gaze, gt, fixmap)
        for k, v in m_gaze.items():
            results["gaze"][k].append(v)

        # Evaluate object-only
        m_obj = compute_all_metrics(obj, gt, fixmap)
        for k, v in m_obj.items():
            results["object"][k].append(v)

        # Evaluate fused
        if model is not None:
            inp = torch.from_numpy(
                np.stack([gaze, obj], axis=0)[None, ...]
            ).float().to(device)

            with torch.no_grad():
                fused = model(inp).squeeze().cpu().numpy()

            # Normalise to [0, 1] — the model may have collapsed dynamic range
            fmin, fmax = fused.min(), fused.max()
            if fmax - fmin > 1e-6:
                fused = (fused - fmin) / (fmax - fmin)
            else:
                fused = np.zeros_like(fused)

            m_fused = compute_all_metrics(fused, gt, fixmap)
            for k, v in m_fused.items():
                results["fused"][k].append(v)

    # Average across all frames
    summary = {}
    for branch, metrics_lists in results.items():
        summary[branch] = {k: float(np.mean(v)) for k, v in metrics_lists.items()}

    return summary


def print_comparison_table(summary: Dict[str, Dict[str, float]]) -> str:
    """Pretty-print a comparison table and return it as a string."""
    branches = list(summary.keys())
    metric_names = list(summary[branches[0]].keys())

    # Determine which direction is "better" for each metric
    better_lower = {"KL"}  # lower is better
    # For all others (CC, NSS, SIM, AUC-J), higher is better

    header = f"{'Metric':<10}" + "".join(f"{b:>12}" for b in branches)
    sep = "-" * len(header)
    lines = [sep, header, sep]

    for m in metric_names:
        vals = [summary[b].get(m, float("nan")) for b in branches]
        row = f"{m:<10}"

        # Find the best value
        if m in better_lower:
            best_idx = int(np.nanargmin(vals))
        else:
            best_idx = int(np.nanargmax(vals))

        for i, v in enumerate(vals):
            marker = " *" if i == best_idx and len(branches) > 1 else "  "
            row += f"{v:>10.4f}{marker}"
        lines.append(row)

    lines.append(sep)
    lines.append("(* = best)")
    table = "\n".join(lines)
    print(table)
    return table


def save_fused_maps(
    cfg: PipelineConfig,
    checkpoint_path: str,
    output_dir: Optional[str] = None,
):
    """
    Generate and save fused saliency maps for all available frames.
    """
    device = torch.device(cfg.train.device if torch.cuda.is_available() else "cpu")
    model, _ = load_checkpoint(checkpoint_path, device)

    if output_dir is None:
        output_dir = cfg.output_dir
    os.makedirs(output_dir, exist_ok=True)

    triplets = discover_triplets(
        gt_dir=cfg.data.gt_salmap_dir,
        gaze_dir=cfg.data.gaze_salmap_dir,
        obj_dir=cfg.data.obj_salmap_dir,
        video_names=cfg.data.video_names,
    )

    print(f"Generating fused maps for {len(triplets)} frames → {output_dir}")

    for vname, gt_path, gaze_path, obj_path in triplets:
        h, w = cfg.data.height, cfg.data.width
        gaze = _load_map(gaze_path, h, w)
        obj = _load_map(obj_path, h, w)

        inp = torch.from_numpy(
            np.stack([gaze, obj], axis=0)[None, ...]
        ).float().to(device)

        with torch.no_grad():
            fused = model(inp).squeeze().cpu().numpy()

        # Normalise to [0, 1] per frame — the model output has correct
        # relative ordering but may have collapsed absolute range
        fmin, fmax = fused.min(), fused.max()
        if fmax - fmin > 1e-6:
            fused = (fused - fmin) / (fmax - fmin)
        else:
            fused = np.zeros_like(fused)

        # Save as 16-bit grayscale PNG
        vid_dir = os.path.join(output_dir, vname, "salmaps")
        os.makedirs(vid_dir, exist_ok=True)
        frame_name = os.path.basename(gt_path)
        out_path = os.path.join(vid_dir, frame_name)
        img16 = (fused * 65535).astype(np.uint16)
        cv2.imwrite(out_path, img16)

    print(f"Done. Saved {len(triplets)} fused saliency maps.")
