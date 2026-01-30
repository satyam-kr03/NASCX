# Dataset Generation for Optimal Compression Selection

## Overview

This document describes the dataset generation framework for training ML models to predict optimal video compression levels based on network conditions. The dataset captures the relationship between CQI, number of users, compression level, and resulting QoE metrics.

---

## Dataset Schema

| Column              | Type  | Description                         |
| ------------------- | ----- | ----------------------------------- |
| `run_id`            | int   | Unique simulation run identifier    |
| `num_users`         | int   | Total users in simulation (2-10)    |
| `user_id`           | int   | User index (0 to num_users-1)       |
| `compression_level` | int   | PCA components (5, 10, 15, ..., 80) |
| `total_frames`      | int   | Expected frames (1074)              |
| `on_time_frames`    | int   | Frames delivered within deadline    |
| `avg_delay_ms`      | float | Average frame delay (ms)            |
| `delay_reliability` | float | Fraction of on-time frames (0-1)    |
| `user_satisfied`    | int   | 1 if reliability ≥ 99%, else 0      |
| `avg_mse`           | float | Mean Squared Error (QoE metric)     |
| `avg_cqi`           | float | Average downlink CQI (1-15)         |

---

## Simulation Configuration

### Network Parameters

| Parameter         | Value                  |
| ----------------- | ---------------------- |
| System Bandwidth  | 100 MHz                |
| Numerology        | μ=1 (30 kHz SCS)       |
| Resource Blocks   | 273                    |
| Carrier Frequency | 2.4 GHz                |
| Channel Model     | Flat Rayleigh Fading   |
| Scheduler         | PF (Proportional Fair) |
| Deployment Area   | 250m × 250m            |

### XR Traffic Model

| Parameter             | Value                               |
| --------------------- | ----------------------------------- |
| Frame Rate            | 60 fps                              |
| Delay Deadline        | 5 ms                                |
| Reliability Threshold | 99%                                 |
| Compression Levels    | 5, 10, 15, ..., 80 (PCA components) |

### UE Mobility (XR-DL-Dataset Config)

| Parameter         | Value                             |
| ----------------- | --------------------------------- |
| Mobility Model    | RandomWaypointMobility            |
| Speed Range       | 3-10 m/s (walking to jogging)     |
| Wait Time         | 0-1 s                             |
| Initial Positions | Random (50m-200m from cell edges) |

---

## Code Modifications

### XRTrafficSource

Added `compressionLevel` parameter to filter PCA data by component count.

```cpp
// XRTrafficSource.ned
int compressionLevel = default(0);  // 0=all, else filter (5,10,15,...,80)

// XRTrafficSource.cc - loadPCAData()
if (compressionLevel_ == 0 || fi.components == compressionLevel_) {
    frames.push_back(fi);
}
```

### XRTrafficReceiver

Added CQI extraction from PHY layer for dataset recording.

```cpp
// XRTrafficReceiver.cc - finish()
cModule *ue = getParentModule();  // app[0] is directly inside ue[x]
cModule *cellularNic = ue->getSubmodule("cellularNic");
cModule *phyModule = cellularNic->getSubmodule("nrPhy");  // Try NR first
if (phyModule == nullptr) {
    phyModule = cellularNic->getSubmodule("phy");  // Fall back to LTE
}
phyUe_ = dynamic_cast<LtePhyUe*>(phyModule);
avgCqi_ = phyUe_->getAverageCqi(DL);
```

---

## Dataset Generation Script

### Usage

```bash
cd /home/satyam/Desktop/NASCX && ./opp_shell.sh
cd simu5g-1.3.0/simulations/NR/xr

# Quick test (3 users, 1 run)
python3 generate_dataset.py --test

# Full dataset generation
python3 generate_dataset.py --runs 10 --deadline 5.0 --seed 42
```

### Parameters

| Argument     | Default | Description                     |
| ------------ | ------- | ------------------------------- |
| `--runs`     | 10      | Number of runs per user count   |
| `--deadline` | 5.0     | Delay deadline in ms            |
| `--seed`     | 42      | Random seed for reproducibility |
| `--test`     | -       | Run quick test with 3 users     |

### Output

- **File**: `compression_dataset.csv`
- **Rows**: `num_users × runs × users_per_run` (e.g., 9 user counts × 10 runs = ~450 rows)

---

## Compression Levels

The dataset includes 16 compression levels corresponding to PCA components:

| Level  | Components | Approx. MSE | Frame Size |
| ------ | ---------- | ----------- | ---------- |
| Low    | 5-15       | 350-800     | Small      |
| Medium | 20-40      | 100-275     | Medium     |
| High   | 45-80      | 40-100      | Large      |

Lower compression (more components) = lower MSE but larger frames = higher delay.

---

## Expected Dataset Characteristics

### CQI Variation

- UE mobility creates CQI variation (typically 8-15)
- Users closer to gNB have higher CQI
- CQI affects scheduling priority and achievable throughput

### Trade-offs

- **Low compression**: Low MSE but high delay (large frames)
- **High compression**: High MSE but low delay (small frames)
- Optimal point depends on CQI and network load

### Sample Data

| num_users | compression | avg_delay | reliability | avg_mse | avg_cqi |
| --------- | ----------- | --------- | ----------- | ------- | ------- |
| 2         | 20          | 2.30      | 100%        | 275.9   | 15      |
| 6         | 70          | 3.85      | 93.7%       | 106.3   | 15      |
| 10        | 65          | 4.41      | 77.7%       | 264.9   | 14      |

---

## Running Manual Simulations

```bash
# Test with mobility configuration
simu5g -r 0 -m -u Cmdenv -c XR-DL-Dataset \
  --*.numUe=3 \
  --*.server.numApps=3 \
  '--*.server.app[0].pcaFile="pca_sweep_summary_scaled.csv"' \
  '--*.server.app[0].compressionLevel=20' \
  '--*.server.app[1].pcaFile="pca_sweep_summary_scaled.csv"' \
  '--*.server.app[1].compressionLevel=40' \
  '--*.server.app[2].pcaFile="pca_sweep_summary_scaled.csv"' \
  '--*.server.app[2].compressionLevel=60' \
  --*.ue[*].app[0].deadlineMs=5ms \
  omnetpp.ini 2>&1 | tail -50
```

---

## Available Configurations

| Config                   | Description                            |
| ------------------------ | -------------------------------------- |
| `XR-DL-SingleUser`       | Single user baseline (static)          |
| `XR-DL-MultiUser-PF`     | Multi-user PF scheduler (static)       |
| `XR-DL-MultiUser-MaxCQI` | Multi-user MAX-CQI scheduler (static)  |
| `XR-DL-Dataset`          | **Dataset generation (with mobility)** |

---

## Files Modified

| File                                    | Changes                             |
| --------------------------------------- | ----------------------------------- |
| `src/apps/xr/XRTrafficSource.ned`       | Added `compressionLevel` parameter  |
| `src/apps/xr/XRTrafficSource.h`         | Added `compressionLevel_` member    |
| `src/apps/xr/XRTrafficSource.cc`        | Filtering logic in `loadPCAData()`  |
| `src/apps/xr/XRTrafficReceiver.h`       | Added `avgCqi_`, `phyUe_` members   |
| `src/apps/xr/XRTrafficReceiver.cc`      | CQI extraction in `finish()`        |
| `simulations/NR/xr/omnetpp.ini`         | Added `XR-DL-Dataset` configuration |
| `simulations/NR/xr/generate_dataset.py` | Dataset generation script           |
