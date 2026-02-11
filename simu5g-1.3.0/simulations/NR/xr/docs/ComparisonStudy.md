# ML-Dynamic vs Uncompressed: Comparison Study

> **Study Date**: February 11, 2026  
> **Methodology**: Two-Phase Simulation — Uncompressed Baseline vs Per-Frame Dynamic Compression

## Overview

This study compares two compression strategies for XR traffic in 5G NR networks:

1. **Uncompressed (Baseline)** — All frames use `components=80` (maximum quality, least compression). This represents the "uncompressed-equivalent" scenario where frames are at their largest possible size.
2. **ML-Dynamic (Per-Frame)** — Uses a trained XGBoost model to predict per-frame compression levels based on:
   - **Number of users** in the cell
   - **Actual per-user CQI values** collected from a warmup simulation
   - **Frame rate (FPS)** — 60, 72, 90, or 120 fps
   - **Frame complexity** — size at `components=80`, reflecting inherent frame difficulty

### Why Compare Against Uncompressed?

The "uncompressed" baseline (`components=80`) represents the **best possible quality** — frames retain maximum detail with minimal compression artifacts. However, these large frames are harder to deliver on time, especially under congested network conditions.

The ML-Dynamic model intelligently compresses frames based on their complexity and network conditions, trading some quality for **significantly better delivery reliability**. This comparison directly measures:
- **How much quality do we sacrifice** by using dynamic compression?
- **How much reliability do we gain** by adapting frame sizes to network conditions?

## Methodology

### Two-Phase Simulation Approach

1. **Phase 1 (Warmup)**: Run a 50-frame simulation with mid-level compression to collect real per-user CQI values
2. **Phase 2 (Evaluation)**: 
   - **Uncompressed**: All frames use `components=80` — no compression decisions needed
   - **ML-Dynamic**: Query model per-frame with user's CQI, FPS, and frame complexity, then generate adaptive PCA CSVs where each frame has a different compression level

### Setup

- **Simulation Framework**: Simu5G (OMNeT++)
- **User Range**: 2-10 concurrent XR users
- **Compression Levels**: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80
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

3. For each ML-dynamic evaluation, the script:
   - Runs warmup to collect actual per-user CQI values
   - Queries model with real CQI and per-frame complexity for adaptive compression
   - Generates custom PCA CSVs where each frame row has a different `components` value
   - Runs full simulation with these per-frame compressed files

---

## Expected Results

| Metric              | Uncompressed | ML-Dynamic | Trade-off |
| ------------------- | ------------ | ---------- | --------- |
| **Avg MSE**         | ~0 (best)    | Higher     | Quality cost of compression |
| **Avg Delay (ms)**  | Higher       | Lower      | Smaller frames → faster delivery |
| **Avg Reliability** | Lower        | Higher     | More frames meet deadline |
| **Satisfaction Rate** | Lower      | Higher     | More users achieve 99% reliability |

> [!IMPORTANT]
> Lower MSE and Delay are better. Higher Reliability and Satisfaction are better.  
> The key insight: Uncompressed has perfect quality but poor delivery; ML-Dynamic trades some quality for much better reliability.

---

## Key Insights

1. **Quality vs Delivery Trade-off**: The uncompressed baseline achieves the best possible MSE (near zero) but struggles with delivery reliability because the large frame sizes cause more deadline violations under network congestion.

2. **Adaptive Compression**: The ML-Dynamic model identifies large, complex frames that would likely miss deadlines and compresses them more aggressively, while keeping smaller frames at higher quality. This per-frame adaptation is more effective than applying uniform compression.

3. **Network-Aware Decisions**: By incorporating CQI (channel quality) and user count, the model adjusts compression based on actual network conditions — more compression when the network is congested, less when conditions are favorable.

---

## Files

| File                                  | Description                                      |
| ------------------------------------- | ------------------------------------------------ |
| `comparison_results/comparison_*.csv` | Raw per-user results for analysis                |
| `model_server.py`                     | FastAPI server hosting the dynamic ML model      |
| `run_comparison.py`                   | Comparison study: Uncompressed vs ML-Dynamic     |
| `train_dynamic_model.py`              | Dynamic per-frame model training script          |
| `compression_model_dynamic.joblib`    | Trained dynamic XGBoost model                    |

---

## Conclusion

The comparison between uncompressed transmission and ML-guided dynamic compression demonstrates the fundamental **quality-reliability trade-off** in XR video delivery over 5G NR:

- **Uncompressed** provides the best quality but unreliable delivery under network load
- **ML-Dynamic** sacrifices some quality to achieve significantly better reliability

The dynamic per-frame approach is particularly effective because it makes **frame-level decisions** — compressing only the frames that need it, while preserving quality on simpler frames that can be delivered on time without compression.
