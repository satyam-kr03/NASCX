# YOLOv8 Object Saliency Pipeline — Setup & Usage Guide

This guide documents the YOLOv8-based object saliency pipeline for generating object-level saliency maps from equirectangular 360° video, directly comparable to the gaze-based saliency maps produced by [SalViT360](../SalViT360/SETUP_GUIDE.md).

## Table of Contents

- [Overview](#overview)
- [The Core Problem](#the-core-problem)
- [Pipeline Architecture](#pipeline-architecture)
  - [Step 1 — Tangent Plane Projection](#step-1--tangent-plane-projection)
  - [Step 2 — Object Detection](#step-2--object-detection)
  - [Step 3 — Coordinate Reprojection & NMS](#step-3--coordinate-reprojection--nms)
  - [Step 4 — Saliency Map Generation](#step-4--saliency-map-generation)
- [Environment Setup](#environment-setup)
- [File Structure](#file-structure)
- [Configuration](#configuration)
  - [Patch Layout](#patch-layout)
  - [Detection Settings](#detection-settings)
  - [Saliency Weights](#saliency-weights)
- [Usage](#usage)
  - [Process a Single Video](#process-a-single-video)
  - [Process All Salient360! Videos](#process-all-salient360-videos)
  - [Process a Single Image](#process-a-single-image)
  - [CLI Options Reference](#cli-options-reference)
- [Output Structure](#output-structure)
- [Verified Results](#verified-results)
- [Comparison with SalViT360](#comparison-with-salvit360)
- [Notes & Caveats](#notes--caveats)
- [References](#references)

---

## Overview

This pipeline generates **object-level saliency maps** from equirectangular 360° video using YOLOv8 object detection. The output is a per-frame heatmap in equirectangular space (960×1920) that highlights where semantically salient objects (people, animals, vehicles, etc.) are located, weighted by detection confidence and class importance.

- **Input**: Equirectangular 360° video frames (resized to 1920×960)
- **Output**: Per-frame saliency maps (960×1920), float values in [0, 1]
- **Detection model**: YOLOv8n (nano) — 80 COCO classes
- **Projection**: 18 tangent-plane patches covering the sphere
- **Speed**: ~1 frame/sec on GPU (18 patches × YOLO inference + NMS)

---

## The Core Problem

YOLOv8 is trained on standard flat 2D (perspective) images. Feeding it a raw equirectangular frame directly causes problems:

- Objects near the poles appear heavily stretched and distorted
- The detector fails on or misclassifies distorted objects
- Bounding boxes in equirectangular space are geometrically meaningless near high latitudes

**The solution**: never feed the raw equirectangular frame to YOLO. Instead, project it onto multiple tangent planes (gnomonic projections) where each patch looks like a normal perspective image with minimal distortion.

---

## Pipeline Architecture

```
┌─────────────────────┐
│ Equirectangular     │
│ Frame (1920×960)    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 1. Tangent Plane    │    18 patches (640×640 each)
│    Projection       │    4 rows × [3,6,6,3]
│    (equi2pers.py)   │    90° FoV per patch
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 2. YOLOv8 Detect    │    Run on each patch independently
│    (detect.py)      │    Standard perspective images → YOLO works natively
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 3. Reproject +      │    Convert patch-local bboxes → equirectangular coords
│    Cross-Patch NMS  │    Remove duplicates from overlapping patches
│    (detect.py)      │    Handles 360° wrap-around
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 4. Saliency Map     │    confidence × class_weight → Gaussian blur → [0,1]
│    (saliency.py)    │    Same format as SalViT360 gaze maps
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Output: saliency    │    960×1920 heatmap, per frame
│ map (PNG, float)    │    + optional colour overlay
└─────────────────────┘
```

### Step 1 — Tangent Plane Projection

**File**: `equi2pers.py`

The equirectangular frame is carved into **18 overlapping tangent-plane patches** arranged in 4 latitude bands:

| Row | Latitude φ | # Patches | Longitude spacing |
|-----|-----------|-----------|------------------|
| 1 (top)    | +67.5° | 3 | 120° apart |
| 2 (upper)  | +22.5° | 6 | 60° apart  |
| 3 (lower)  | −22.5° | 6 | 60° apart  |
| 4 (bottom) | −67.5° | 3 | 120° apart |

Each patch is a **90° FoV** gnomonic (perspective) projection at **640×640** resolution. The projection uses the standard **inverse gnomonic mapping**:

$$\phi = \arcsin\!\left(\cos c \,\sin\phi_0 + \frac{v \sin c \,\cos\phi_0}{\rho}\right)$$

$$\lambda = \lambda_0 + \arctan\!\left(\frac{u \sin c}{\rho \cos\phi_0 \cos c - v \sin\phi_0 \sin c}\right)$$

where $(\lambda_0, \phi_0)$ is the patch centre, $(u, v)$ are tangent-plane pixel coordinates, and $\rho = \sqrt{u^2 + v^2}$.

This is the same projection family used by SalViT360 (see `model/utils/projection.py`), reimplemented here in pure NumPy + OpenCV without PyTorch dependencies.

### Step 2 — Object Detection

**File**: `detect.py`

YOLOv8 runs on all 18 patches in a single batched `model.predict()` call. Each patch is a standard perspective image, so YOLO performs exactly as it was trained — no domain gap.

### Step 3 — Coordinate Reprojection & NMS

**File**: `detect.py`

Bounding boxes in patch pixel coordinates are reprojected to equirectangular pixel coordinates:

1. **Edge sampling**: 16 points are sampled along each edge of the bounding box
2. **Gnomonic → spherical**: each point is mapped through the inverse gnomonic formula to get (lon, lat)
3. **Spherical → equirectangular pixels**: (lon, lat) → (x, y) in the output image
4. **Bounding rectangle**: the min/max of all projected points gives the equirectangular bbox

Edge sampling (rather than just projecting corners) is necessary because the gnomonic mapping is non-linear — straight lines in the patch become curves in equirectangular space.

**Cross-patch NMS** then removes duplicate detections from overlapping patches:
- Class-aware: only suppresses detections of the same class
- Handles 360° wrap-around in IoU computation
- Default IoU threshold: 0.5

### Step 4 — Saliency Map Generation

**File**: `saliency.py`

Detections are converted to a continuous saliency heatmap:

1. Each bounding box region is filled with value = `confidence × class_weight`
2. Overlapping boxes take the **maximum** (not sum) to keep saliency bounded
3. **Gaussian blur** (σ = 20 px) smooths hard box edges into a continuous heatmap
4. The map is **normalised** to [0, 1]

360° wrap-around is handled: boxes that cross the left/right seam are rendered correctly on both sides.

---

## Environment Setup

All commands use the existing `mlc` conda environment (same as SalViT360).

```bash
conda activate mlc
```

### Dependencies

The pipeline uses packages already installed in `mlc`:

| Package | Version | Purpose |
|---------|---------|---------|
| `ultralytics` | — | YOLOv8 inference |
| `opencv-python` | 4.12.0 | Image I/O, remapping, blurring |
| `numpy` | 2.2.6 | Array operations, projection math |
| `tqdm` | — | Progress bars |

No additional packages need to be installed.

---

## File Structure

```
semantic_relevance/Salient360/YOLOv8/
├── config.py          # Centralised configuration (dataclasses)
├── equi2pers.py       # Equirectangular ↔ tangent-plane projection
├── detect.py          # YOLOv8 detection + reprojection + cross-patch NMS
├── saliency.py        # Object saliency map generation + visualisation
├── pipeline.py        # End-to-end CLI for images and videos
├── example_script.py  # Original Ultralytics boilerplate (reference only)
├── yolov8n.pt         # Pretrained YOLOv8-nano weights (COCO, 80 classes)
└── SETUP_GUIDE.md     # This file
```

### Module roles

| Module | Key functions / classes | Role |
|--------|------------------------|------|
| `config.py` | `PatchConfig`, `DetectionConfig`, `SaliencyConfig`, `PipelineConfig` | All tuneable parameters as dataclasses |
| `equi2pers.py` | `PatchInfo`, `equirect_to_patches()`, `patch_bbox_to_equirect()` | Forward projection (extract patches) and inverse projection (reproject coords) |
| `detect.py` | `Detection`, `detect_on_patches()`, `cross_patch_nms()` | Run YOLO, collect detections, merge duplicates |
| `saliency.py` | `detections_to_saliency()`, `save_saliency_map()`, `overlay_saliency()` | Build heatmap, save / visualise |
| `pipeline.py` | `process_frame()`, `process_video()`, `process_image()`, `main()` | CLI entry point, orchestrates everything |

---

## Configuration

All settings are defined as Python dataclasses in `config.py`. Defaults can be overridden via CLI arguments.

### Patch Layout

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fov` | 90° | Field of view per patch |
| `nrows` | 4 | Number of latitude rows |
| `num_cols` | [3, 6, 6, 3] | Patches per row (total = 18) |
| `phi_centers` | [−67.5, −22.5, 22.5, 67.5] | Latitude centre of each row (degrees) |
| `patch_size` | (640, 640) | Resolution per patch |

Alternative layouts:

| `nrows` | Layout | Total patches |
|---------|--------|---------------|
| 3 | [3, 4, 3] at [−60°, 0°, 60°] | 10 |
| **4** | **[3, 6, 6, 3] at [−67.5°, −22.5°, 22.5°, 67.5°]** | **18** (default) |
| 5 | [3, 6, 8, 6, 3] at [−72.2°, −36.1°, 0°, 36.1°, 72.2°] | 26 |
| 6 | [3, 8, 12, 12, 8, 3] at [−75.2°, −45.93°, −15.72°, 15.72°, 45.93°, 75.2°] | 46 |

### Detection Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `weights` | `yolov8n.pt` | YOLOv8 model weights |
| `conf_threshold` | 0.25 | Minimum detection confidence |
| `iou_threshold` | 0.45 | NMS IoU threshold within a patch |
| `cross_patch_iou_threshold` | 0.50 | NMS IoU threshold across patches |
| `device` | `"0"` | GPU index or `"cpu"` |
| `imgsz` | 640 | YOLO input resolution |

### Saliency Weights

Objects that are known to attract gaze in VR receive higher saliency weights:

| COCO class | ID | Weight | Rationale |
|------------|----|--------|-----------|
| **person** | 0 | **3.0** | Universally fixated in VR studies |
| cat | 15 | 2.0 | Animate, attracts attention |
| dog | 16 | 2.0 | Animate, attracts attention |
| car, bus, truck, etc. | 2,5,7 | 1.5 | Large moving objects |
| cow, horse, sheep | 19,17,18 | 1.5 | Animals |
| bird | 14 | 1.2 | Small, less dominant |
| backpack, handbag | 24, 26 | 1.2 | Proxy for human presence |
| *all other classes* | — | 1.0 | Default |

These weights are applied multiplicatively: `saliency_value = confidence × class_weight`. Adjust in `config.py` as needed.

---

## Usage

All commands assume:

```bash
cd ~/Projects/NASCX/semantic_relevance/Salient360/YOLOv8
conda activate mlc
```

### Process a Single Video

```bash
python pipeline.py --video /home/teaching/Projects/NASCX/data/Salient360/Stimuli/16_Turtle.mp4
```

Output: per-frame saliency maps and overlays in `data/Salient360/yolo_saliency/16_Turtle/`.

### Process All Salient360! Videos

```bash
# Every frame (slow but complete)
python pipeline.py --all

# Every 5th frame (5× faster)
python pipeline.py --all --sample-every 5

# Also save an overlay video
python pipeline.py --all --sample-every 5 --save-overlay-video
```

### Process a Single Image

```bash
python pipeline.py --image /path/to/equirectangular.jpg
```

### CLI Options Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--video PATH` | — | Process a single equirectangular video |
| `--image PATH` | — | Process a single equirectangular image |
| `--all` | — | Process all videos in `data/Salient360/Stimuli/` |
| `--output-dir DIR` | `data/Salient360/yolo_saliency` | Output directory |
| `--weights FILE` | `yolov8n.pt` | YOLOv8 weights (e.g. `yolov8s.pt` for better accuracy) |
| `--conf FLOAT` | 0.25 | Detection confidence threshold |
| `--blur-sigma FLOAT` | 20.0 | Gaussian blur sigma for saliency smoothing |
| `--device STR` | `"0"` | `"0"` = GPU 0, `"cpu"` = CPU |
| `--sample-every INT` | 1 | Process every N-th frame |
| `--save-overlay-video` | off | Also write an MP4 with saliency overlay |
| `--equirect-w INT` | 1920 | Equirectangular frame width |
| `--equirect-h INT` | 960 | Equirectangular frame height |
| `--fov FLOAT` | 90.0 | Patch field of view (degrees) |
| `--nrows INT` | 4 | Number of latitude rows (3, 4, 5, or 6) |
| `--patch-size INT` | 640 | Patch resolution |

---

## Output Structure

```
data/Salient360/yolo_saliency/
├── test/                           # Quick test output (single frame)
│   ├── test_saliency.png           # Colour-mapped saliency (JET)
│   └── test_overlay.png            # Saliency overlaid on frame
└── 16_Turtle/                      # Per-video directory
    ├── salmaps/                    # Raw saliency maps (16-bit grayscale PNG)
    │   ├── 000000.png
    │   ├── 000001.png
    │   └── ...                     # One per processed frame
    └── overlays/                   # Saliency overlaid on video frames
        ├── 000000.png
        ├── 000001.png
        └── ...
```

- **`salmaps/`** — 16-bit grayscale PNGs (0–65535 mapped from 0.0–1.0). These are the primary output for downstream analysis, directly comparable to SalViT360 saliency maps.
- **`overlays/`** — Colour-coded saliency heatmap blended on top of the original frame (α = 0.4) for visual inspection.

---

## Verified Results

### Quick test (single frame from `10_Cows.mp4`)

| Metric | Value |
|--------|-------|
| Patches extracted | 18 (in 0.5s) |
| YOLO inference | 1.14s (all 18 patches) |
| Raw detections | 3 |
| After cross-patch NMS | 3 |
| Saliency map range | [0.0, 1.0] |

### Full video (`16_Turtle.mp4`)

| Metric | Value |
|--------|-------|
| Total frames processed | 600 |
| Output saliency maps | 600 |
| Output overlay frames | 600 |

---

## Comparison with SalViT360

| Aspect | SalViT360 (gaze-based) | YOLOv8 (object-based) |
|--------|----------------------|---------------------|
| **What it predicts** | Where humans look (gaze fixation) | Where objects are (semantic content) |
| **Model** | Vision Transformer + ResNet-18 (~38M params) | YOLOv8-nano (~3.2M params) |
| **Input** | 8-frame video clips (temporal) | Individual frames (no temporal info) |
| **Training** | Trained on gaze fixation data | Pretrained on COCO (no 360° training) |
| **Projection** | 18 tangent patches (224×224, built into model) | 18 tangent patches (640×640, preprocessing) |
| **Output format** | Saliency map (480×960) | Saliency map (960×1920) |
| **Output range** | [0, 1] float | [0, 1] float |
| **Key insight** | Captures bottom-up + top-down attention | Captures semantic object locations |

Both pipelines produce equirectangular saliency maps that can be directly compared, subtracted, or fused for analysis.

---

## Notes & Caveats

1. **YOLOv8 model variants** — `yolov8n.pt` (nano) is fast but may miss small or unusual objects. For better accuracy at the cost of speed, use `yolov8s.pt` (small) or `yolov8m.pt` (medium):
   ```bash
   python pipeline.py --video input.mp4 --weights yolov8s.pt
   ```
   These will be auto-downloaded by Ultralytics on first use.

2. **No face detection** — COCO does not include a "face" class. The `person` class (weighted 3×) is the closest proxy. For explicit face detection, consider adding a secondary face detector or using a YOLO model fine-tuned on face data.

3. **Polar regions** — The top and bottom rows (±67.5°) have only 3 patches each. Objects near the poles may receive less coverage. Increase to `--nrows 5` (26 patches) or `--nrows 6` (46 patches) for denser polar coverage at the cost of slower processing.

4. **Frame-level independence** — Unlike SalViT360 which uses 8-frame temporal windows, this pipeline treats each frame independently. Temporal smoothing of saliency maps across frames could be added as a post-processing step if needed.

5. **360° seam handling** — The pipeline correctly handles bounding boxes that wrap around the left/right boundary of the equirectangular image (the 0°/360° seam).

6. **GPU memory** — With 18 patches of 640×640, the batched YOLO inference uses ~2–3 GB VRAM. This is well within the capacity of most GPUs.

7. **Saliency map resolution** — Output is 960×1920 to match the equirectangular frame. Resize as needed for comparison with other saliency map formats (e.g. SalViT360 outputs at 480×960).

---

## References

- **YOLOv8**: [Ultralytics YOLOv8](https://docs.ultralytics.com/) — Jocher et al., 2023
- **Gnomonic projection**: [Mathworld — Gnomonic Projection](https://mathworld.wolfram.com/GnomonicProjection.html)
- **SalViT360**: [Spherical Vision Transformer for 360° Video Saliency Prediction](https://arxiv.org/abs/2308.13004) (BMVC 2023)
- **Salient360!**: [Salient360! dataset](http://salient360.ls2n.fr/) — David et al., MMSys 2018
- **COCO classes**: [COCO dataset — 80 object categories](https://cocodataset.org/#explore)
