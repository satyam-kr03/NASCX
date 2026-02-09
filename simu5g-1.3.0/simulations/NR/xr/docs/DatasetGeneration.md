# Dataset Generation for Optimal Compression Selection

## Overview

This document describes the dataset generation script for training ML models to predict optimal video compression levels. The script runs Simu5G simulations with varying parameters and collects QoE metrics.

---

## Dataset Schema

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | int | Unique simulation run identifier |
| `num_users` | int | Total users in simulation (2-10) |
| `user_id` | int | User index (0 to num_users-1) |
| `fps` | int | Frame rate (60, 72, 90, 120) |
| `compression_level` | int | PCA components (5, 10, 15, ..., 80) |
| `size_mean_kb` | float | Mean frame size of traffic profile (KB) |
| `size_min_kb` | float | Min frame size of traffic profile (KB) |
| `size_max_kb` | float | Max frame size of traffic profile (KB) |
| `size_std_kb` | float | Std dev of frame sizes (KB) |
| `total_frames` | int | Expected frames (fps × sim-time) |
| `on_time_frames` | int | Frames delivered within deadline |
| `avg_delay_ms` | float | Average frame delay (ms) |
| `delay_reliability` | float | Fraction of on-time frames (0-1) |
| `user_satisfied` | int | 1 if reliability ≥ 99%, else 0 |
| `avg_mse` | float | Mean Squared Error (QoE metric) |
| `avg_cqi` | float | Average downlink CQI (1-15) |

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

## Usage

```bash
cd simu5g-1.3.0/simulations/NR/xr

# Generate traffic profiles first
python3 generate_traffic_profiles.py

# Run dataset generation
python3 generate_dataset.py
```

### Configuration

Edit parameters directly in `generate_dataset.py`:

```python
# At the bottom of the file:
generate_dataset(num_runs=10, deadline_ms=5.0, seed=42)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_runs` | 10 | Number of runs per user count |
| `deadline_ms` | 5.0 | Delay deadline in ms |
| `seed` | 42 | Random seed for reproducibility |

---

## How It Works

1. **Loop through user counts** (2 to 10 users)
2. **For each run**, randomly assign:
   - Compression level per user (5, 10, 15, ..., 80)
   - FPS per user (60, 72, 90, 120)
   - Traffic profile per user
3. **Run simulation** using `simu5g` command
4. **Parse results** from `user_results.csv` (written by `XRTrafficReceiver`)
5. **Save merged dataset** to `compression_dataset.csv`

---

## Files

| File | Description |
|------|-------------|
| `generate_dataset.py` | Main script (~175 lines) |
| `traffic_*.csv` | Traffic profiles (5 variants) |
| `compression_dataset.csv` | Output dataset |
| `omnetpp.ini` | Simulation config (uses `XR-DL-Dataset`) |
