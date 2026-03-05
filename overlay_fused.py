"""Quick script to overlay fused saliency maps on original video frames."""

import cv2
import numpy as np
import os

VIDEO = "data/Salient360/Stimuli/3_PlanEnergyBioLab.mp4"
SAL_DIR = "data/Salient360/fused_saliency/3_PlanEnergyBioLab/salmaps"
OUT_DIR = "data/Salient360/fused_saliency/3_PlanEnergyBioLab/overlays"

FRAME_INDICES = [12, 16]  # 0-based frame numbers matching filenames 000012.png, 000016.png
ALPHA = 0.5

os.makedirs(OUT_DIR, exist_ok=True)

cap = cv2.VideoCapture(VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open video: {VIDEO}")

fps = cap.get(cv2.CAP_PROP_FPS)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {VIDEO}  ({total} frames @ {fps} fps)")

for idx in FRAME_INDICES:
    # Read saliency map
    sal_path = os.path.join(SAL_DIR, f"{idx:06d}.png")
    if not os.path.isfile(sal_path):
        print(f"  SKIP frame {idx}: saliency map not found ({sal_path})")
        continue

    # Seek to the target frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if not ret:
        print(f"  SKIP frame {idx}: could not read from video")
        continue

    # Load saliency map and normalise to [0,1] float
    sal_raw = cv2.imread(sal_path, cv2.IMREAD_UNCHANGED)
    if sal_raw.ndim == 3:
        sal_raw = cv2.cvtColor(sal_raw, cv2.COLOR_BGR2GRAY)
    sal_map = sal_raw.astype(np.float32) / sal_raw.max() if sal_raw.max() > 0 else sal_raw.astype(np.float32)

    # Build heatmap overlay
    vis = (sal_map * 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
    if heatmap.shape[:2] != frame.shape[:2]:
        heatmap = cv2.resize(heatmap, (frame.shape[1], frame.shape[0]))

    blended = cv2.addWeighted(frame, 1 - ALPHA, heatmap, ALPHA, 0)

    out_path = os.path.join(OUT_DIR, f"{idx:06d}.png")
    cv2.imwrite(out_path, blended)
    print(f"  Saved overlay: {out_path}")

cap.release()
print("Done.")
