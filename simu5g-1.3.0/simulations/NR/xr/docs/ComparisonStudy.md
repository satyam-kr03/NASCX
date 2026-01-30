# ML-Guided vs Random Compression Selection: Comparison Study

> **Study Date**: January 30, 2026  
> **Methodology**: Two-Phase Simulation with Actual CQI Values

## Overview

This study compares two compression selection strategies for XR traffic in 5G NR networks:

1. **Random Selection** — Baseline approach that randomly assigns compression levels (5-80) to each user
2. **ML-Guided Selection** — Uses a trained XGBoost model to predict optimal compression based on **actual per-user CQI values** collected from a warmup simulation

## Methodology

### Two-Phase Simulation Approach

Unlike previous studies that used fixed CQI values (14.5), this study uses **actual CQI values from simu5g**:

1. **Phase 1 (Warmup)**: Run a 50-frame simulation with random compression to collect real per-user CQI values
2. **Phase 2 (Evaluation)**: Query ML model per-user with their actual CQI, then run full simulation

### Setup

- **Simulation Framework**: Simu5G (OMNeT++)
- **User Range**: 2-10 concurrent XR users
- **Compression Levels**: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80
- **ML Model**: XGBoost regressor with coarser CQI bins (0.5 width) and sample weighting
- **Model Server**: FastAPI endpoint at `localhost:8000`

### Procedure

1. **Start Model Server**:

   ```bash
   cd /home/teaching/Projects/NASCX/simu5g-1.3.0 && . setenv
   conda activate omnetpp
   python3 simulations/NR/xr/model_server.py &
   ```

2. **Run Comparison Study**:

   ```bash
   python3 simulations/NR/xr/run_comparison.py --runs 3
   ```

3. For each ML-guided evaluation, the script:
   - Runs warmup to collect actual per-user CQI values
   - Queries model with real CQI for per-user compression predictions
   - Runs full simulation with varied compression levels per user

---

## Results

| Metric              | Random | ML-Guided | Improvement |
| ------------------- | ------ | --------- | ----------- |
| **Avg MSE**         | 420.32 | 300.17    | **+28.6%**  |
| **Avg Delay (ms)**  | 5.57   | 5.49      | **+1.4%**   |
| **Avg Reliability** | 74.0%  | 86.2%     | **+16.4%**  |
| **Satisfaction Rate** | 0.0% | 1.9%      | **+1.9pp**  |

> [!IMPORTANT]
> Lower MSE and Delay are better. Higher Reliability and Satisfaction are better.  
> Improvement percentages indicate the relative gain of ML-Guided over Random.

---

## Key Findings

1. **Significant MSE Improvement**: ML-guided selection achieved **28.6% lower average MSE**, reducing mean squared error from 420.32 to 300.17. The per-user CQI-aware predictions select compression levels that maintain better video quality.

2. **Improved Reliability**: Delay reliability improved from **74.0% to 86.2%** (+16.4%), meaning significantly more frames met their delivery deadlines with ML-guided compression.

3. **Varied Per-User Compression**: Unlike previous approaches that assigned identical compression to all users, the two-phase approach produces varied compression levels (e.g., `[55, 15, 25, 25]`) based on each user's actual channel conditions.

4. **Positive Satisfaction Rate**: For the first time, ML-guided selection achieved a non-zero satisfaction rate (1.9%), demonstrating that the improved reliability is beginning to push some users above the strict 99% threshold.

---

## Technical Improvements

### Model Training Enhancements

- **Coarser CQI bins** (0.5 instead of 0.05) — More training samples per bin
- **Sample weighting** — Balanced compression level distribution in training

### Two-Phase Simulation Benefits

- Uses **real CQI values** from simu5g instead of fixed estimates
- Enables **per-user compression differentiation** based on actual channel conditions
- Produces more credible and representative results

---

## Files

| File                                  | Description                              |
| ------------------------------------- | ---------------------------------------- |
| `comparison_results/comparison_*.csv` | Raw per-user results for analysis        |
| `model_server.py`                     | FastAPI server hosting the ML model      |
| `run_comparison.py`                   | Comparison study with two-phase warmup   |
| `train_improved_model.py`             | Improved model training script           |
| `compression_model.joblib`            | Trained XGBoost model                    |

---

## Conclusion

The two-phase ML-guided compression selection with actual CQI values demonstrates **significant improvements** over random selection:

- **28.6% improvement in video quality (MSE)**
- **16.4% improvement in delay reliability**
- **First positive satisfaction rate** with ML guidance

By using actual per-user CQI values from simu5g, the model makes more informed compression decisions that better reflect real network conditions. The varied per-user compression assignments (instead of uniform compression for all users) enable the system to optimize for individual channel conditions, leading to better overall QoE.

