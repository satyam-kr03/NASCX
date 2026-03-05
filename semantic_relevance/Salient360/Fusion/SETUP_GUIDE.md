# Learned Saliency Fusion — Setup & Usage Guide

This guide documents the learned fusion pipeline that combines **gaze-based saliency** (SalViT360) and **object-based saliency** (YOLOv8) into a single, improved semantic relevance map, supervised by Salient360! ground-truth fixation data.

## Table of Contents

- [Overview](#overview)
- [Motivation](#motivation)
- [Pipeline Architecture](#pipeline-architecture)
- [Environment Setup](#environment-setup)
- [File Structure](#file-structure)
- [Data Requirements](#data-requirements)
  - [Generating Input Saliency Maps](#generating-input-saliency-maps)
- [Model Architecture](#model-architecture)
- [Loss Functions & Metrics](#loss-functions--metrics)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Step 1 — Generate Inputs](#step-1--generate-inputs)
  - [Step 2 — Train](#step-2--train)
  - [Step 3 — Evaluate](#step-3--evaluate)
  - [Step 4 — Generate Fused Maps](#step-4--generate-fused-maps)
  - [Full Pipeline](#full-pipeline)
  - [CLI Options Reference](#cli-options-reference)
- [Output Structure](#output-structure)
- [Expected Results](#expected-results)
- [Answering the Complementarity Question](#answering-the-complementarity-question)
- [Notes & Caveats](#notes--caveats)
- [References](#references)

---

## Overview

This pipeline implements a **learned fusion module** that takes two saliency heatmaps per frame:

| Channel | Source | What it captures |
|---------|--------|-----------------|
| $H_\text{gaze}$ | SalViT360 | Where humans look (gaze fixation patterns) |
| $H_\text{obj}$  | YOLOv8    | Where semantically salient objects are (category-aware) |

and produces a single **fused semantic relevance map** $H_\text{fused}$ that is a better predictor of human attention than either input alone.

- **Input**: 2-channel map per frame — `[H_gaze, H_obj]`, both in [0, 1]
- **Output**: Single-channel fused map $H_\text{fused}$ in [0, 1]
- **Supervision**: Salient360! ground-truth fixation density maps
- **Loss**: KL divergence + Correlation Coefficient (standard in saliency literature)
- **Model**: Pixel-wise 1×1 convolution network (deliberately simple)

---

## Motivation

**Why not just use SalViT360 alone, since it's already trained on human gaze?**

SalViT360 captures *statistical attention patterns* learned from its training distribution, but:

1. **Object-level signals provide category-aware semantic grounding** that generalises better to novel scenes where gaze data is sparse.
2. Gaze prediction captures *bottom-up* attention (low-level visual features) plus *top-down* learned biases, but lacks explicit *semantic understanding* of what objects are present.
3. The YOLOv8 branch provides explicit **"there is a person here"** or **"there is a car here"** signals that complement gaze prediction.
4. The fusion learns **spatially varying weights** for how much to trust each branch at each region of the frame — optimised directly against human fixation ground truth.

Even a small improvement in metrics validates the **complementarity argument** — that gaze and object saliency are capturing fundamentally different aspects of perceptual importance, and combining them helps.

---

## Pipeline Architecture

```
┌──────────────────────────┐     ┌──────────────────────────┐
│   SalViT360 (gaze)      │     │   YOLOv8 (object)        │
│   H_gaze ∈ [0,1]        │     │   H_obj  ∈ [0,1]         │
│   480×960 per frame      │     │   480×960 per frame       │
└────────────┬─────────────┘     └────────────┬─────────────┘
             │                                │
             └────────────┬───────────────────┘
                          │ concatenate
                          ▼
                   ┌──────────────┐
                   │ [2, 480, 960]│   2-channel input
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │  1×1 Conv    │   16 channels, ReLU
                   │  1×1 Conv    │   16 channels, ReLU
                   │  1×1 Conv    │   1 channel, Sigmoid
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │   H_fused    │   [1, 480, 960]
                   │   ∈ [0, 1]   │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │ Compare vs   │   KL + CC loss
                   │ GT fixation  │
                   └──────────────┘
```

---

## Environment Setup

Uses the existing `mlc` conda environment (same as SalViT360 and YOLOv8):

```bash
conda activate mlc
```

No additional packages are required. The fusion model uses only PyTorch, NumPy, and OpenCV — all already installed.

---

## File Structure

```
semantic_relevance/Salient360/Fusion/
├── __init__.py          # Package marker
├── config.py            # Centralised configuration (dataclasses)
├── dataset.py           # Data loading, triplet discovery, train/val split
├── model.py             # Fusion model architectures (Conv1x1, MLP, Conv3x3)
├── losses.py            # KL, CC, NSS losses + evaluation metrics
├── train.py             # Training loop with early stopping
├── evaluate.py          # Evaluation, comparison tables, fused map generation
├── generate_inputs.py   # Run SalViT360 + YOLOv8 to produce input maps
├── pipeline.py          # Main CLI entry point
└── SETUP_GUIDE.md       # This file
```

### Module roles

| Module | Key functions / classes | Role |
|--------|------------------------|------|
| `config.py` | `DataConfig`, `ModelConfig`, `LossConfig`, `TrainConfig`, `PipelineConfig` | All tuneable parameters as dataclasses |
| `dataset.py` | `FusionDataset`, `discover_triplets()`, `build_dataloaders()` | Find aligned (gaze, obj, GT) frame triplets, load & resize |
| `model.py` | `Conv1x1Fusion`, `PixelMLP`, `Conv3x3Fusion`, `build_model()` | Three model variants of increasing complexity |
| `losses.py` | `FusionLoss`, `kl_divergence()`, `correlation_coefficient()`, `nss_loss()`, `compute_all_metrics()` | Differentiable training losses + numpy eval metrics |
| `train.py` | `train()` | Full training with validation, early stopping, checkpointing |
| `evaluate.py` | `evaluate_all()`, `print_comparison_table()`, `save_fused_maps()` | Compare gaze vs object vs fused on all metrics |
| `generate_inputs.py` | `generate_gaze_saliency()`, `generate_object_saliency()` | Run both upstream pipelines |
| `pipeline.py` | `main()` | CLI: `train`, `eval`, `fuse`, `all` |

---

## Data Requirements

The fusion module needs three aligned sets of per-frame saliency maps:

| Map | Source | Expected path | Resolution | Format |
|-----|--------|---------------|------------|--------|
| Ground truth | Salient360! processed | `data/Salient360/processed/salmaps/<video>/` | 480×960 | uint8 PNG |
| Fixation map | Salient360! processed | `data/Salient360/processed/fixmaps/<video>/` | 480×960 | uint8 PNG |
| Gaze saliency | SalViT360 inference | `data/Salient360/salvit360_saliency/<video>/salmaps/` | any (resized) | uint16 PNG |
| Object saliency | YOLOv8 pipeline | `data/Salient360/yolo_saliency/<video>/salmaps/` | any (resized) | uint16 PNG |

Frame filenames must match across all three sources (e.g. `000007.png`). The dataset module automatically discovers frames where all three maps exist.

### Generating Input Saliency Maps

Before training, you need to generate saliency maps from both upstream pipelines. The ground truth must also be preprocessed.

#### 1. Preprocess Salient360! ground truth

```bash
cd ~/Projects/NASCX/semantic_relevance/Salient360/SalViT360
conda activate mlc
python preprocess_salient360.py --n_videos 19
```

This creates `data/Salient360/processed/salmaps/` and `fixmaps/`.

#### 2. Generate gaze + object saliency maps

```bash
cd ~/Projects/NASCX/semantic_relevance/Salient360/Fusion
conda activate mlc

# Single video
python generate_inputs.py --video 10_Cows

# All videos
python generate_inputs.py --all

# Only gaze or only object
python generate_inputs.py --video 10_Cows --gaze-only
python generate_inputs.py --video 10_Cows --obj-only

# With a pretrained SalViT360 checkpoint (better quality)
python generate_inputs.py --video 10_Cows --checkpoint /path/to/salvit360.pt
```

---

## Model Architecture

Three variants are available, all operating pixel-wise:

### Conv1x1 (default, recommended)

```
Input [2, H, W]
  → Conv2d(2→16, 1×1) → ReLU
  → Conv2d(16→16, 1×1) → ReLU
  → Conv2d(16→1, 1×1) → Sigmoid
Output [1, H, W]
```

This is equivalent to applying a 2-layer MLP at every pixel independently. The model learns a **spatially-invariant** nonlinear combination of the two input channels. Total parameters: **321** (2×16 + 16 + 16×16 + 16 + 16×1 + 1).

**What does it learn?** It learns how much to trust the gaze prediction versus the object detection at each pixel value combination, optimised directly against human fixation ground truth.

### PixelMLP

Functionally identical to Conv1x1 but implemented explicitly as `nn.Linear` layers. Useful for pedagogy.

### Conv3x3

Uses 3×3 convolutions instead of 1×1, giving the model access to the immediate spatial neighbourhood. Useful if the input maps are slightly misaligned or if local gradients carry information.

---

## Loss Functions & Metrics

### Training loss

$$\mathcal{L} = \lambda_\text{KL} \cdot \text{KL}(GT \| \text{pred}) + \lambda_\text{CC} \cdot (-\text{CC})$$

| Component | Default weight | Description |
|-----------|---------------|-------------|
| **KL divergence** | 1.0 | Primary loss — treats maps as probability distributions |
| **−CC** | 0.5 | Negative correlation coefficient — complementary to KL |
| **−NSS** | 0.0 | Optional — measures quality at fixation points specifically |

### Evaluation metrics

| Metric | Direction | Description |
|--------|-----------|-------------|
| **KL** | ↓ lower is better | Kullback-Leibler divergence between distributions |
| **CC** | ↑ higher is better | Pearson correlation coefficient |
| **NSS** | ↑ higher is better | Normalised scanpath saliency at fixation points |
| **SIM** | ↑ higher is better | Similarity (histogram intersection) |
| **AUC-J** | ↑ higher is better | Area under ROC curve (Judd variant) |

---

## Configuration

All settings are defined as Python dataclasses in `config.py`. Defaults can be overridden via CLI arguments.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--model` | `conv1x1` | Model variant (`conv1x1`, `mlp`, `conv3x3`) |
| `--hidden` | 16 | Hidden layer width |
| `--n-hidden` | 2 | Number of hidden layers |
| `--epochs` | 50 | Training epochs |
| `--batch-size` | 4 | Batch size |
| `--lr` | 0.001 | Learning rate (AdamW) |
| `--kl-weight` | 1.0 | KL loss weight |
| `--cc-weight` | 0.5 | CC loss weight |
| `--patience` | 10 | Early stopping patience |
| `--train-ratio` | 0.75 | Train/val split ratio |
| `--height` | 480 | Working resolution height |
| `--width` | 960 | Working resolution width |

---

## Usage

All commands assume:

```bash
cd ~/Projects/NASCX/semantic_relevance/Salient360/Fusion
conda activate mlc
```

### Step 1 — Generate Inputs

```bash
python generate_inputs.py --video 10_Cows
```

### Step 2 — Train

```bash
# Default settings (conv1x1, 50 epochs, KL+CC loss)
python pipeline.py train

# Custom settings
python pipeline.py train --model conv1x1 --epochs 100 --lr 0.0005 --batch-size 8

# Restrict to specific video(s)
python pipeline.py train --video 10_Cows

# With NSS in the loss
python pipeline.py train --nss-weight 0.1
```

### Step 3 — Evaluate

```bash
# Evaluate on validation split (compares gaze vs object vs fused)
python pipeline.py eval --checkpoint data/Salient360/fusion_checkpoints/best_model.pt

# Evaluate on all data
python pipeline.py eval --checkpoint data/Salient360/fusion_checkpoints/best_model.pt --split all

# Save metrics to JSON
python pipeline.py eval --checkpoint best_model.pt --save-json results.json
```

### Step 4 — Generate Fused Maps

```bash
python pipeline.py fuse --checkpoint data/Salient360/fusion_checkpoints/best_model.pt
```

### Full Pipeline

```bash
# Train and evaluate in one go
python pipeline.py all

# With specific settings
python pipeline.py all --video 10_Cows --epochs 30 --model conv1x1
```

### CLI Options Reference

| Command | Description |
|---------|-------------|
| `train` | Train the fusion model from scratch |
| `eval` | Evaluate and compare gaze vs object vs fused |
| `fuse` | Generate fused saliency maps for all frames |
| `all` | Train → evaluate → generate fused maps |

---

## Output Structure

```
data/Salient360/
├── fusion_checkpoints/
│   ├── best_model.pt          # Best checkpoint (by val KL)
│   └── final_model.pt         # Last-epoch checkpoint
├── fused_saliency/            # Generated fused maps
│   └── 10_Cows/
│       └── salmaps/
│           ├── 000007.png     # 16-bit grayscale, one per frame
│           ├── 000008.png
│           └── ...
├── salvit360_saliency/        # Gaze saliency (generated)
│   └── 10_Cows/
│       └── salmaps/
│           └── ...
└── yolo_saliency/             # Object saliency (generated)
    └── 10_Cows/
        └── salmaps/
            └── ...
```

---

## Expected Results

The evaluation produces a comparison table like:

```
----------------------------------------------------
Metric          gaze      object       fused
----------------------------------------------------
KL          1.2345      2.4567      0.9876 *
CC          0.5432      0.3210      0.6123 *
NSS         1.2100      0.8900      1.3500 *
SIM         0.3800      0.2900      0.4200 *
AUC-J       0.7800      0.7200      0.8100 *
----------------------------------------------------
(* = best)
```

Even a small improvement of $H_\text{fused}$ over $H_\text{gaze}$ alone is meaningful:

- **Validates complementarity**: gaze and object saliency capture different aspects
- **Justifies the two-branch architecture**: the fusion learns that object presence provides value beyond gaze statistics
- **Provides a better compression signal**: the fused map is a more complete measure of perceptual importance

---

## Answering the Complementarity Question

> **"Why not just use SalViT360 alone since it's already trained on human gaze?"**

SalViT360 captures statistical attention patterns from its training distribution, but object-level signals provide category-aware semantic grounding that generalises better to novel scenes where gaze data is sparse. The fusion gives you the best of both:

1. **SalViT360** knows *where people tend to look* in 360° scenes (learned from eye-tracking data)
2. **YOLOv8** knows *what objects are present and where* (learned from COCO annotations)
3. **The fusion** learns *how to combine both signals* to best predict actual human attention (learned from Salient360! ground truth)

The fusion model is deliberately simple (a pixel-wise 1×1 conv network with ~300 parameters). Its purpose is not to model complex interactions, but to learn **calibrated channel weights** — how much each branch contributes to the final saliency estimate. This is clean, interpretable, and easy to defend.

---

## Notes & Caveats

1. **Data availability** — Both upstream pipelines must have been run on the same videos before training. The dataset module will silently skip videos or frames where any map is missing.

2. **Resolution mismatch** — GT maps are 480×960, YOLOv8 outputs 960×1920, SalViT360 outputs vary. All maps are resized to 480×960 at load time.

3. **Frame alignment** — The frame naming convention (`000000.png`, `000001.png`, ...) must be consistent across all three sources. SalViT360 predictions start from frame 7 (due to the 8-frame temporal window), so earlier frames are skipped.

4. **Temporal independence** — The fusion model treats each frame independently. Temporal smoothing could be added as post-processing.

5. **Model size** — The default Conv1x1 model has only ~321 parameters. This is intentional — the fusion is a calibration layer, not a model in its own right. If you want more capacity, use `--model conv3x3` or increase `--hidden`.

6. **Augmentation** — Random horizontal flips are applied during training (valid for equirectangular images as this is equivalent to a 180° yaw rotation of the viewing sphere).

7. **GPU memory** — The fusion model itself is negligible. Memory is dominated by loading 480×960 maps into tensors. With batch size 4, this uses < 1 GB.

---

## References

- **SalViT360**: [Spherical Vision Transformer for 360° Video Saliency Prediction](https://arxiv.org/abs/2308.13004) (BMVC 2023)
- **YOLOv8**: [Ultralytics YOLOv8](https://docs.ultralytics.com/) — Jocher et al., 2023
- **Salient360!**: [Salient360! dataset](http://salient360.ls2n.fr/) — David et al., MMSys 2018
- **Saliency metrics**: Bylinskii et al., "What do different evaluation metrics tell us about saliency models?" (TPAMI 2019)
- **KL + CC loss**: Kümmerer et al., "Understanding Low- and High-Level Contributions to Fixation Prediction" (ICCV 2017)
