# Dataset Generation for Dynamic Compression Model

## Overview

This document describes the dataset generation framework for training the per-frame dynamic compression model. The dataset captures the relationship between frame complexity, network conditions (CQI, number of users), compression level choices, and resulting delivery outcomes.

---

## Traffic Profiles

Five traffic profiles with varying frame size distributions:

| Profile | Mean (KB) | Std (KB) | Min (KB) | Max (KB) |
|---------|-----------|----------|----------|----------|
| `traffic_45kb.csv` | 45 | 24 | 6 | 84 |
| `traffic_65kb.csv` | 65 | 35 | 8 | 122 |
| `traffic_80kb.csv` | 80 | 43 | 10 | 150 |
| `traffic_95kb.csv` | 95 | 51 | 12 | 178 |
| `traffic_120kb.csv` | 120 | 64 | 15 | 225 |

Generate profiles with:
```bash
python3 generate_traffic_profiles.py
```

---

## FPS Rates

Each user is randomly assigned one of: **60, 72, 90, 120** fps.
Expected frame count = `fps × sim-time` (default 20s).

---

## Per-Frame Dataset Schema

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | int | Unique simulation run identifier |
| `num_users` | int | Total users in simulation (2-10) |
| `user_id` | int | User index |
| `fps` | int | Frame rate |
| `avg_cqi` | float | Average CQI for this user |
| `frame_number` | int | Frame index within the video |
| `frame_complexity` | float | Frame size at max components (bytes) — inherent difficulty |
| `compression_level` | int | PCA components assigned to this frame |
| `compressed_size_bytes` | int | Actual frame size after compression |
| `mse` | float | Reconstruction error for this frame |
| `delay_ms` | float | End-to-end delay for this frame |
| `received_on_time` | int | 1 if delivered within deadline, 0 otherwise |

### Key Concept: Frame Complexity

**Frame complexity** = the frame's size when using maximum components (80). At `components=80`, the frame is minimally compressed, so `size_bytes` reflects the inherent frame complexity:

- **Complex frames** (high-motion, detailed content) → larger size at `components=80` (~120KB)
- **Simple frames** (static, less detail) → smaller size at `components=80` (~40KB)

The per-frame model learns: *"For a frame of complexity X, under network conditions (num_users, CQI), what compression level best balances quality (MSE) and deliverability (on-time rate)?"*

---

## Usage

```bash
cd /home/teaching/Projects/NASCX
./opp_shell.sh
cd simu5g-1.3.0/simulations/NR/xr

# Quick test (3 users, per-frame compression)
python3 generate_per_frame_dataset.py --test

# Full dataset generation (parallel)
python3 generate_per_frame_dataset.py --runs 5 -j 8
```

### Parameters

| Argument | Default | Description |
|----------|---------|-------------|
| `--runs` | 5 | Runs per user count |
| `--deadline` | 5.0 | Delay deadline in ms |
| `--seed` | 42 | Random seed |
| `--workers` / `-j` | auto | Parallel workers |
| `--save-interval` | 5 | Checkpoint every N runs |
| `--test` | - | Quick test with 3 users |

---

## Files

| File | Description |
|------|-------------|
| `generate_traffic_profiles.py` | Generates synthetic traffic CSV files |
| `generate_per_frame_dataset.py` | Runs simulations and generates per-frame dataset |
| `train_dynamic_model.py` | Trains the dynamic per-frame XGBoost model |
| `traffic_*.csv` | Traffic profiles (5 variants) |
| `per_frame_dataset.csv` | Per-frame dataset output |
| `compression_model_dynamic.joblib` | Trained dynamic model |
| `traffic_profiles_metadata.csv` | Traffic profile statistics |

---

## Pipeline

```
1. generate_traffic_profiles.py     → produces traffic_*.csv
2. generate_per_frame_dataset.py    → produces per_frame_dataset.csv
3. train_dynamic_model.py           → produces compression_model_dynamic.joblib
4. model_server.py                  → serves /predict_per_frame endpoint
5. run_comparison.py                → runs Uncompressed vs ML-Dynamic comparison
```
