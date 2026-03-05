"""
Generate input saliency maps from both pipelines for fusion training.

This script runs:
  1. SalViT360 — gaze-based saliency (per-frame PNGs)
  2. YOLOv8   — object-based saliency (per-frame PNGs, if not already done)

Both outputs are saved alongside the existing GT saliency maps so the fusion
dataset can discover aligned triplets.

Usage:
    cd ~/Projects/NASCX/semantic_relevance/Salient360/Fusion
    conda activate mlc
    python generate_inputs.py --video 10_Cows
    python generate_inputs.py --all
"""

from __future__ import annotations

import argparse
import glob
import itertools
import os
import sys

import cv2
import numpy as np
import torch
import torchvision
import torchvision.transforms as tf
from tqdm import tqdm

from config import DATA_ROOT, STIMULI_DIR, GAZE_SALMAP_DIR, OBJ_SALMAP_DIR


# ── SalViT360 inference ────────────────────────────────────────────────────

SALVIT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "SalViT360"
)


def generate_gaze_saliency(
    video_path: str,
    output_dir: str,
    checkpoint: str | None = None,
    device: str = "cuda",
    sample_every: int = 1,
):
    """
    Run SalViT360 on a video and save per-frame saliency maps as PNGs.

    The model uses an 8-frame sliding window; each prediction corresponds
    to the last frame of the window.  Frames before index 7 are skipped.
    """
    import yaml
    from dotmap import DotMap

    sys.path.insert(0, SALVIT_DIR)
    from utils.setup import get_model, set_to_eval

    # Load config
    config_fn = os.path.join(SALVIT_DIR, "configs", "vst-eval-salient360.yml")
    config = DotMap(yaml.safe_load(open(config_fn, "r")))

    if checkpoint:
        config.network.resume = checkpoint

    dev = torch.device(device if torch.cuda.is_available() else "cpu")

    # Build model
    model = get_model(config).eval()
    set_to_eval(model)
    model = model.module.to(dev)

    # Read video
    print(f"  Reading {video_path} ...")
    video_obj = torchvision.io.VideoReader(video_path, "video")
    frames = [f["data"] for f in video_obj]
    n_frames = len(frames)
    print(f"  {n_frames} frames loaded")

    os.makedirs(output_dir, exist_ok=True)
    transform = tf.Normalize(
        mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
    )

    count = 0
    for st in tqdm(range(0, n_frames - 7, sample_every), desc="  SalViT360"):
        frame_idx = st + 7  # prediction corresponds to last frame of window

        clip = frames[st : st + 8]
        clip = transform(torch.stack(clip).float() / 255.0).unsqueeze(0)

        with torch.no_grad():
            pred = model.forward(clip.to(dev))
            pred = pred.squeeze(1).detach().cpu().numpy()[0]  # [H, W]

        # Normalise to [0, 1]
        pmin, pmax = pred.min(), pred.max()
        if pmax - pmin > 0:
            pred = (pred - pmin) / (pmax - pmin)
        else:
            pred = np.zeros_like(pred)

        # Save as 16-bit grayscale PNG (same convention as YOLOv8)
        out_path = os.path.join(output_dir, f"{frame_idx:06d}.png")
        img16 = (pred * 65535).astype(np.uint16)
        cv2.imwrite(out_path, img16)
        count += 1

    print(f"  Saved {count} gaze saliency maps → {output_dir}")

    # Clean up
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ── YOLOv8 inference ───────────────────────────────────────────────────────

YOLO_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "YOLOv8"
)


def generate_object_saliency(
    video_path: str,
    output_dir: str,
    device: str = "0",
    sample_every: int = 1,
):
    """
    Run the YOLOv8 pipeline on a video and save per-frame saliency maps.

    Delegates to the existing YOLOv8 pipeline.py.
    """
    import importlib.util
    from ultralytics import YOLO

    # Load YOLOv8 modules by explicit file path to avoid shadowing Fusion's config
    def _load_module(name, filepath):
        spec = importlib.util.spec_from_file_location(name, filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    yolo_config = _load_module("yolo_config", os.path.join(YOLO_DIR, "config.py"))
    yolo_cfg = yolo_config.PipelineConfig()
    yolo_cfg.detection.device = device

    # Load the YOLO model (required by process_video)
    model = YOLO(yolo_cfg.detection.weights)

    # We need the YOLOv8 pipeline's dependencies on sys.path for its own imports
    saved_path = sys.path.copy()
    sys.path.insert(0, YOLO_DIR)

    yolo_pipeline = _load_module("yolo_pipeline", os.path.join(YOLO_DIR, "pipeline.py"))

    yolo_pipeline.process_video(
        video_path=video_path,
        model=model,
        cfg=yolo_cfg,
        output_dir=output_dir,  # process_video creates <video_name>/salmaps/ inside
        sample_every=sample_every,
        save_overlay_video=False,
    )

    sys.path = saved_path
    print(f"  YOLO saliency maps → {output_dir}")


# ── Main ────────────────────────────────────────────────────────────────────

def get_video_list():
    """Return sorted list of (video_name, video_path) tuples."""
    if not os.path.isdir(STIMULI_DIR):
        return []
    videos = []
    for f in sorted(os.listdir(STIMULI_DIR)):
        if f.endswith(".mp4"):
            name = os.path.splitext(f)[0]
            videos.append((name, os.path.join(STIMULI_DIR, f)))
    return videos


def main():
    parser = argparse.ArgumentParser(
        description="Generate gaze + object saliency maps for fusion training"
    )
    parser.add_argument("--video", type=str, help="Process a single video by name (e.g. 10_Cows)")
    parser.add_argument("--all", action="store_true", help="Process all Salient360! videos")
    parser.add_argument("--gaze-only", action="store_true", help="Only generate gaze saliency")
    parser.add_argument("--obj-only", action="store_true", help="Only generate object saliency")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="SalViT360 checkpoint path (default: random weights)")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--sample-every", type=int, default=1,
                        help="Process every N-th frame")
    args = parser.parse_args()

    videos = get_video_list()
    if not videos:
        print(f"No videos found in {STIMULI_DIR}")
        return

    if args.video:
        videos = [(n, p) for n, p in videos if n == args.video]
        if not videos:
            print(f"Video '{args.video}' not found")
            return
    elif not args.all:
        parser.print_help()
        return

    do_gaze = not args.obj_only
    do_obj = not args.gaze_only

    for vname, vpath in videos:
        print(f"\n{'='*60}")
        print(f"Processing: {vname}")
        print(f"{'='*60}")

        if do_gaze:
            gaze_out = os.path.join(GAZE_SALMAP_DIR, vname, "salmaps")
            if os.path.isdir(gaze_out) and len(os.listdir(gaze_out)) > 0:
                print(f"  Gaze saliency already exists ({len(os.listdir(gaze_out))} maps), skipping")
            else:
                generate_gaze_saliency(
                    vpath, gaze_out,
                    checkpoint=args.checkpoint,
                    device=args.device,
                    sample_every=args.sample_every,
                )

        if do_obj:
            obj_out = os.path.join(OBJ_SALMAP_DIR, vname, "salmaps")
            if os.path.isdir(obj_out) and len(os.listdir(obj_out)) > 0:
                print(f"  Object saliency already exists ({len(os.listdir(obj_out))} maps), skipping")
            else:
                generate_object_saliency(
                    vpath, OBJ_SALMAP_DIR,
                    device=args.device.replace("cuda", "0"),
                    sample_every=args.sample_every,
                )

    print("\n✓ All done. Run 'python pipeline.py train' to train the fusion model.")


if __name__ == "__main__":
    main()
