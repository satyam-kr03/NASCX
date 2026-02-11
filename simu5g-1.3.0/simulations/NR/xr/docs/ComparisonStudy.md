# ML-Dynamic vs Fixed-Static vs Uncompressed: Comparison Study

> **Study Date**: February 11, 2026  
> **Methodology**: Three-Way Simulation — Uncompressed (Motivation) vs Fixed-Static (Fair Baseline) vs ML-Dynamic (Our Method)

## Overview

This study compares three compression strategies for XR traffic in 5G NR networks:

1. **Uncompressed (Motivation)** — All frames use `components=80` (maximum quality, least compression). Demonstrates **why compression is needed**: large frames overwhelm the network and miss deadlines, resulting in penalty MSE = max MSE at 5 components for most frames.
2. **Fixed-Static (Fair Baseline)** — All frames use a single fixed compression level. We sweep levels [10, 20, 30, 40, 50, 60, 70] and pick the one with the **lowest average MSE**. This is the strongest naive baseline — if ML can't beat this, the model isn't useful.
3. **ML-Dynamic (Our Method)** — Uses a trained XGBoost model to predict per-frame compression levels based on:
   - **Number of users** in the cell
   - **Actual per-user CQI values** collected from a warmup simulation
   - **Frame rate (FPS)** — 60, 72, 90, or 120 fps
   - **Frame complexity** — size at `components=80`, reflecting inherent frame difficulty

### Why Three Baselines?

| Baseline | Purpose | What It Answers |
|---|---|---|
| **Uncompressed** | Motivation | "Why is compression needed at all?" |
| **Best Fixed-Static** | Fair comparison | "Does per-frame ML beat the best naive fixed strategy?" |
| **ML-Dynamic** | Our contribution | "Does intelligent adaptation add value?" |

The **uncompressed** baseline alone is a straw-man — it's so bad that any compression looks good. The **best fixed-static** is the real test: it forces the ML model to prove that its per-frame decisions are better than simply picking one good compression level for all frames.

### QoE Metric: MSE with Deadline Penalty

The comparison uses a unified MSE metric from `XRTrafficReceiver.cc`:
- **On-time frames**: MSE = actual PCA reconstruction error
- **Late/lost frames**: MSE = **max MSE at 5 components** (penalty, auto-computed from PCA CSV)

This means MSE already captures both quality degradation (from compression) and delivery failure (from missed deadlines). The **best** strategy minimizes this combined metric.

## Methodology

### Two-Phase Simulation Approach

1. **Phase 1 (Warmup)**: Run a 50-frame simulation with mid-level compression to collect real per-user CQI values
2. **Phase 2 (Evaluation)**: 
   - **Uncompressed**: All frames use `components=80`
   - **Fixed-Static**: All frames use a single fixed `components` value (swept across levels)
   - **ML-Dynamic**: Query model per-frame with user's CQI, FPS, and frame complexity

### Setup

- **Simulation Framework**: Simu5G (OMNeT++)
- **User Range**: 2-10 concurrent XR users
- **Compression Levels**: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80
- **Fixed-Static Sweep**: 10, 20, 30, 40, 50, 60, 70
- **FPS Rates**: 60, 72, 90, 120 fps (randomly assigned per user)
- **Traffic Profiles**: 5 profiles with varying mean frame sizes (45KB, 65KB, 80KB, 95KB, 120KB)
- **ML Model**: XGBoost regressor (dynamic per-frame model)
  - Features: `num_users`, `cqi`, `fps`, `frame_complexity`
- **Model Server**: FastAPI endpoint at `localhost:8000`

### Frame Complexity

The **frame complexity** metric is defined as:

```
frame_complexity = size_bytes at components=80
```

At `components=80` (maximum quality), the frame is minimally compressed, so `size_bytes` reflects the inherent frame complexity:
- **Complex frames** (high-motion, detailed content) → larger size at `components=80` (~120KB)
- **Simple frames** (static, less detail) → smaller size at `components=80` (~40KB)

The dynamic model uses this information to make per-frame compression decisions: compress complex frames more aggressively to meet deadlines, while keeping simple frames at higher quality.

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

3. The script automatically:
   - Runs **uncompressed** simulations (all frames at components=80)
   - Runs **fixed-static** simulations for each level in [10, 20, 30, 40, 50, 60, 70]
   - Runs **ML-dynamic** simulations (warmup → CQI collection → per-frame model queries)
   - Identifies the **best fixed level** (lowest MSE) and compares ML-Dynamic against it

---

## Expected Results

### Fixed-Static Sweep

| Level | Expected Behavior |
|---|---|
| **Low (10-20)** | Small frames → good delivery, but high compression MSE |
| **Mid (30-50)** | Balance of quality and delivery — likely best fixed level |
| **High (60-70)** | Better quality but larger frames → more deadline violations |
| **80 (Uncompressed)** | Best quality but worst delivery → dominated by penalty MSE |

### 3-Way Summary

| Metric              | Uncompressed | Best Fixed | ML-Dynamic |
| ------------------- | ------------ | ---------- | ---------- |
| **Avg MSE**         | ~penalty (late-dominated) | Lower (balanced) | Lowest (adaptive) |
| **Avg Delay (ms)**  | Very high    | Moderate   | Lowest     |
| **Avg Reliability** | Very low (~8%) | Moderate | Highest    |

> [!IMPORTANT]
> The **key comparison** is ML-Dynamic vs Best Fixed. If ML-Dynamic achieves lower MSE,
> it proves that per-frame adaptation adds value over the best naive fixed strategy.

---

## Key Insights

1. **Uncompressed is a Straw-Man**: With penalty MSE for late frames set to the max MSE at 5 components, the uncompressed scenario's "perfect quality" is irrelevant — almost all frames miss deadlines. This motivates compression but doesn't provide a fair benchmark.

2. **Best Fixed-Static is the Real Test**: The best fixed compression level represents the strongest naive strategy. It already provides a good quality-delivery trade-off without any intelligence. ML-Dynamic must beat this to justify its complexity.

3. **Per-Frame Adaptation**: The ML-Dynamic model identifies frames that would miss deadlines and compresses them more aggressively, while keeping simpler frames at higher quality. This frame-level granularity is what gives it an edge over fixed compression.

4. **Network-Aware Decisions**: By incorporating CQI (channel quality) and user count, the model adjusts compression based on actual network conditions — more compression when the network is congested, less when conditions are favorable.

---

## Files

| File                                  | Description                                      |
| ------------------------------------- | ------------------------------------------------ |
| `comparison_results/comparison_*.csv` | Raw per-user results for analysis                |
| `model_server.py`                     | FastAPI server hosting the dynamic ML model      |
| `run_comparison.py`                   | 3-way comparison: Uncompressed vs Fixed vs ML    |
| `train_dynamic_model.py`              | Dynamic per-frame model training script          |
| `compression_model_dynamic.joblib`    | Trained dynamic XGBoost model                    |

---

## Conclusion

The three-way comparison provides a rigorous evaluation:

- **Uncompressed** (motivation): Shows that raw transmission is infeasible — nearly all frames miss deadlines
- **Best Fixed-Static** (fair baseline): The strongest naive strategy — picks one compression level that balances quality and delivery
- **ML-Dynamic** (our method): Per-frame adaptive compression that leverages network conditions and frame complexity

The fair comparison against the best fixed level answers the real question: **does ML-driven per-frame adaptation outperform the best simple strategy?**
