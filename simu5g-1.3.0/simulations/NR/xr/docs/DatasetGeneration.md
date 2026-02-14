# Dataset Generation for Dynamic Compression Model

## Overview

This document describes the dataset generation framework for training the per-frame dynamic compression model. The dataset captures the relationship between frame complexity, network conditions (CQI, number of users), and the **optimal compression level** required to meet delivery deadlines.

Unlike previous approaches that used random exploration, this framework uses a **Scenario Sweep** methodology to generating ground-truth labels for supervised learning.

---

## Methodology: Ground-Truth Sweep

To determine the optimal compression level for any given frame, we simulate the same scenario multiple times under different compression configurations.

1.  **Scenario Definition**: A specific configuration of Users, Traffic Profiles, FPS rates, and Random Seed is fixed.
2.  **Compression Sweep**: We run **16 parallel simulations** for this exact scenario.
    *   Simulation 1: All users, all frames set to Compression Level 5.
    *   Simulation 2: All users, all frames set to Compression Level 10.
    *   ...
    *   Simulation 16: All users, all frames set to Compression Level 80.
3.  **Label Extraction**: For every individual frame of each user, we analyze the 16 outcomes to find the **Highest Quality (Lowest MSE)** level that was successfully delivered on time.

This produces a clean, labeled dataset where the model aims to predict the optimal decision directly.

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

The output is a labeled dataset for Supervised Learning.

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | int | Unique simulation scenario identifier |
| `num_users` | int | Total users in simulation (2-10) |
| `user_id` | int | User index |
| `fps` | int | Frame rate |
| `avg_cqi` | float | Average CQI for this user |
| `frame_number` | int | Frame index within the video |
| `frame_complexity` | float | Frame size at independent max components (bytes) — inherent difficulty |
| **`optimal_compression_level`** | **int** | **Target Label**: The best compression level (5-80) |
| `min_possible_mse` | float | The MSE achieved by the optimal level |
| `achieved_delay` | float | The delay achieved by the optimal level |

### Key Concept: Frame Complexity

**Frame complexity** = the frame's size when using maximum components (80).
This is an **input feature** representing the inherent difficulty of the frame.
- High complexity (~120KB) requires more aggressive compression to fit in the pipe.
- Low complexity (~40KB) can use lighter compression (higher level) or none.

The model learns the mapping:
`f(Complexity, CQI, Users, FPS) → Optimal Compression Level`

---

## Usage

**Note:** This process is computationally intensive. A single "Run" involves 16 full simulations.

```bash
cd /home/teaching/Projects/NASCX
./opp_shell.sh
cd simu5g-1.3.0/simulations/NR/xr

# Quick test (1 scenario, 3 users, 16 simulations)
python3 generate_per_frame_dataset.py --test

# Full dataset generation (parallel)
# Uses multiprocessing to handle multiple scenarios at once.
python3 generate_per_frame_dataset.py --runs 5 --workers 16
```

### Parameters

| Argument | Default | Description |
|----------|---------|-------------|
| `--runs` | 5 | Scenarios per user count (2-10). Total scenarios = 9 × runs. |
| `--deadline` | 5.0 | Delay deadline in ms used to determine success. |
| `--seed` | 42 | Random seed |
| `--workers` / `-j` | auto | Parallel workers (recommend high core count) |
| `--save-interval` | 5 | Save to CSV every N completed scenarios |
| `--test` | - | Quick test with 3 users (1 scenario) |

---

## Files

| File | Description |
|------|-------------|
| `generate_traffic_profiles.py` | Generates synthetic traffic CSV files |
| `generate_per_frame_dataset.py` | Runs Scenario Sweeps and generates labeled dataset |
| `train_dynamic_model.py` | Trains the supervised XGBoost model (needs update for new schema) |
| `traffic_*.csv` | Traffic profiles (5 variants) |
| `datasets/per_frame_dataset.csv` | **New** Labeled per-frame dataset output |

---

## Pipeline

```
1. generate_traffic_profiles.py     → produces traffic_*.csv
2. generate_per_frame_dataset.py    → produces datasets/per_frame_dataset.csv (Labeled data)
3. train_dynamic_model.py           → produces compression_model_dynamic.joblib
4. model_server.py                  → serves /predict_per_frame endpoint
```
