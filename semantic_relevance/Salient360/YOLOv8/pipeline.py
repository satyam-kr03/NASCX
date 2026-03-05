#!/usr/bin/env python3
"""
End-to-end pipeline: equirectangular 360° video → object saliency maps.

Usage examples:

  # Process a single video (default settings — 18 tangent patches, yolov8n)
  python pipeline.py --video /path/to/video.mp4

  # Process all Salient360! videos
  python pipeline.py --all

  # Process a single frame (image file)
  python pipeline.py --image /path/to/equirectangular.jpg

  # Adjust detection confidence & blur
  python pipeline.py --video /path/to/video.mp4 --conf 0.30 --blur-sigma 30

  # Use a larger YOLO model for better accuracy
  python pipeline.py --video /path/to/video.mp4 --weights yolov8s.pt

  # Run on CPU
  python pipeline.py --video /path/to/video.mp4 --device cpu

  # Sample every N-th frame (faster processing)
  python pipeline.py --video /path/to/video.mp4 --sample-every 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO

from config import PipelineConfig, DataConfig
from equi2pers import equirect_to_patches
from detect import detect_on_patches, cross_patch_nms, Detection
from saliency import (
    detections_to_saliency,
    save_saliency_map,
    save_saliency_raw,
    overlay_saliency,
)


def process_frame(frame: np.ndarray,
                  model: YOLO,
                  cfg: PipelineConfig) -> tuple[np.ndarray, List[Detection]]:
    """
    Full pipeline for a single equirectangular frame.

    Returns (saliency_map, detections).
    """
    erp_h, erp_w = frame.shape[:2]

    # 1. Extract tangent patches
    patches = equirect_to_patches(
        equirect=frame,
        nrows=cfg.patches.nrows,
        num_cols=cfg.patches.num_cols,
        phi_centers_deg=cfg.patches.phi_centers,
        fov_deg=cfg.patches.fov,
        patch_size=cfg.patches.patch_size,
    )

    # 2. Run YOLO on each patch, reproject to equirectangular
    raw_dets = detect_on_patches(
        model=model,
        patches=patches,
        patch_size=cfg.patches.patch_size,
        erp_w=erp_w,
        erp_h=erp_h,
        conf=cfg.detection.conf_threshold,
        iou=cfg.detection.iou_threshold,
        imgsz=cfg.detection.imgsz,
        device=cfg.detection.device,
    )

    # 3. Cross-patch NMS
    dets = cross_patch_nms(
        raw_dets,
        erp_w=erp_w,
        iou_threshold=cfg.detection.cross_patch_iou_threshold,
    )

    # 4. Generate saliency map
    sal_map = detections_to_saliency(
        detections=dets,
        erp_w=erp_w,
        erp_h=erp_h,
        class_weights=cfg.saliency.class_weights,
        default_weight=cfg.saliency.default_class_weight,
        blur_sigma=cfg.saliency.blur_sigma,
    )

    return sal_map, dets


def process_image(image_path: str, model: YOLO, cfg: PipelineConfig,
                  output_dir: str) -> None:
    """Process a single equirectangular image."""
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Error: cannot read image {image_path}")
        return

    # Resize to expected equirectangular size
    ew, eh = cfg.equirect_size
    if frame.shape[:2] != (eh, ew):
        frame = cv2.resize(frame, (ew, eh))

    sal_map, dets = process_frame(frame, model, cfg)

    stem = Path(image_path).stem
    os.makedirs(output_dir, exist_ok=True)

    save_saliency_map(sal_map, os.path.join(output_dir, f"{stem}_saliency.png"))
    save_saliency_raw(sal_map, os.path.join(output_dir, f"{stem}_saliency_raw.png"))
    overlay = overlay_saliency(frame, sal_map, alpha=0.4)
    cv2.imwrite(os.path.join(output_dir, f"{stem}_overlay.png"), overlay)

    print(f"  {len(dets)} detections → {output_dir}/{stem}_saliency.png")


def process_video(video_path: str, model: YOLO, cfg: PipelineConfig,
                  output_dir: str, sample_every: int = 1,
                  save_overlay_video: bool = False) -> None:
    """
    Process all frames of an equirectangular video.

    Parameters
    ----------
    sample_every : int
        Process every N-th frame.  1 = every frame.
    save_overlay_video : bool
        If True, also write an overlay video with saliency heatmap.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: cannot open video {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_name = Path(video_path).stem

    sal_dir = os.path.join(output_dir, video_name, "salmaps")
    overlay_dir = os.path.join(output_dir, video_name, "overlays")
    os.makedirs(sal_dir, exist_ok=True)
    os.makedirs(overlay_dir, exist_ok=True)

    ew, eh = cfg.equirect_size

    # Optional overlay video writer
    vid_writer = None
    if save_overlay_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        overlay_vid_path = os.path.join(output_dir, video_name, f"{video_name}_overlay.mp4")
        vid_writer = cv2.VideoWriter(overlay_vid_path, fourcc, fps / sample_every, (ew, eh))

    frame_idx = 0
    processed = 0
    total_dets = 0
    t0 = time.time()

    pbar = tqdm(total=total_frames // sample_every, desc=video_name, unit="frame")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_every != 0:
            frame_idx += 1
            continue

        # Resize to standard equirectangular size
        if frame.shape[:2] != (eh, ew):
            frame = cv2.resize(frame, (ew, eh))

        sal_map, dets = process_frame(frame, model, cfg)
        total_dets += len(dets)

        # Save per-frame saliency
        fname = f"{frame_idx:06d}.png"
        save_saliency_raw(sal_map, os.path.join(sal_dir, fname))

        # Save overlay image (every frame)
        overlay_img = overlay_saliency(frame, sal_map, alpha=0.4)
        cv2.imwrite(os.path.join(overlay_dir, fname), overlay_img)

        if vid_writer is not None:
            vid_writer.write(overlay_img)

        processed += 1
        frame_idx += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    if vid_writer is not None:
        vid_writer.release()

    elapsed = time.time() - t0
    fps_proc = processed / elapsed if elapsed > 0 else 0
    print(f"  {video_name}: {processed} frames, {total_dets} total detections, "
          f"{fps_proc:.1f} frames/sec, output → {os.path.join(output_dir, video_name)}")


def main():
    parser = argparse.ArgumentParser(
        description="YOLOv8 object saliency pipeline for equirectangular 360° images/video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--video", type=str, help="Path to a single equirectangular video")
    input_group.add_argument("--image", type=str, help="Path to a single equirectangular image")
    input_group.add_argument("--all", action="store_true",
                             help="Process all videos in the Salient360! Stimuli folder")

    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: data/Salient360/yolo_saliency)")
    parser.add_argument("--weights", type=str, default=None,
                        help="YOLOv8 weights file (default: yolov8n.pt in this directory)")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Detection confidence threshold (default: 0.25)")
    parser.add_argument("--blur-sigma", type=float, default=20.0,
                        help="Gaussian blur sigma for saliency smoothing (default: 20.0)")
    parser.add_argument("--device", type=str, default="0",
                        help="Device: '0' for GPU 0, 'cpu' for CPU (default: '0')")
    parser.add_argument("--sample-every", type=int, default=1,
                        help="Process every N-th frame (default: 1 = all frames)")
    parser.add_argument("--save-overlay-video", action="store_true",
                        help="Also save an overlay video with saliency heatmap")
    parser.add_argument("--equirect-w", type=int, default=1920,
                        help="Equirectangular width (default: 1920)")
    parser.add_argument("--equirect-h", type=int, default=960,
                        help="Equirectangular height (default: 960)")
    parser.add_argument("--fov", type=float, default=90.0,
                        help="Tangent patch field of view in degrees (default: 90)")
    parser.add_argument("--nrows", type=int, default=4,
                        help="Number of latitude rows for tangent patches (default: 4)")
    parser.add_argument("--patch-size", type=int, default=640,
                        help="Tangent patch resolution (default: 640)")

    args = parser.parse_args()

    # Build configuration
    cfg = PipelineConfig()
    cfg.equirect_size = (args.equirect_w, args.equirect_h)
    cfg.patches.fov = args.fov
    cfg.patches.patch_size = (args.patch_size, args.patch_size)
    cfg.detection.conf_threshold = args.conf
    cfg.detection.device = args.device
    cfg.saliency.blur_sigma = args.blur_sigma

    # Handle nrows
    if args.nrows != cfg.patches.nrows:
        nrows_layouts = {
            3: ([3, 4, 3], [-60, 0, 60]),
            4: ([3, 6, 6, 3], [-67.5, -22.5, 22.5, 67.5]),
            5: ([3, 6, 8, 6, 3], [-72.2, -36.1, 0, 36.1, 72.2]),
            6: ([3, 8, 12, 12, 8, 3], [-75.2, -45.93, -15.72, 15.72, 45.93, 75.2]),
        }
        if args.nrows not in nrows_layouts:
            print(f"Error: nrows={args.nrows} not supported. Use 3, 4, 5, or 6.")
            sys.exit(1)
        cfg.patches.nrows = args.nrows
        cfg.patches.num_cols, cfg.patches.phi_centers = nrows_layouts[args.nrows]

    if args.weights:
        cfg.detection.weights = args.weights

    output_dir = args.output_dir or cfg.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Load model
    print(f"Loading YOLOv8 weights: {cfg.detection.weights}")
    model = YOLO(cfg.detection.weights)
    print(f"Patch layout: {cfg.patches.nrows} rows × {cfg.patches.num_cols} = "
          f"{sum(cfg.patches.num_cols)} patches, FoV={cfg.patches.fov}°, "
          f"patch_size={cfg.patches.patch_size}")

    if args.image:
        print(f"Processing image: {args.image}")
        process_image(args.image, model, cfg, output_dir)

    elif args.video:
        print(f"Processing video: {args.video}")
        process_video(args.video, model, cfg, output_dir,
                      sample_every=args.sample_every,
                      save_overlay_video=args.save_overlay_video)

    elif args.all:
        stimuli_dir = os.path.join(cfg.data_root, "Stimuli")
        videos = sorted([
            f for f in os.listdir(stimuli_dir)
            if f.endswith(".mp4")
        ])
        print(f"Found {len(videos)} videos in {stimuli_dir}")
        for vf in videos:
            video_path = os.path.join(stimuli_dir, vf)
            print(f"\nProcessing: {vf}")
            process_video(video_path, model, cfg, output_dir,
                          sample_every=args.sample_every,
                          save_overlay_video=args.save_overlay_video)

    print("\nDone.")


if __name__ == "__main__":
    main()
