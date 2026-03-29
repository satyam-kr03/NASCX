# Comprehensive Plan: Improving Dynamic Compression Selection Model

## Background

The current model achieves performance close to the best static policy, which is a solid baseline. However, to justify dynamic compression, the model needs to **outperform** the best static policy by exploiting real-time network state information. The current model input features are limited to per-user:
- `error_at_80`, `error_ratio` (video content characteristics)
- `cqi` (channel quality — last wideband CQI)  
- `frame_rate` (fps)
- `prev_delay_ms` (previous frame's end-to-end delay)

The key insight for improvement is: **the model currently lacks awareness of shared resource contention and scheduling state**, which are precisely the signals that differentiate dynamic selection from static policy. A static policy cannot react to transient buffer build-up, scheduler congestion, or HARQ retransmissions — but a dynamic model can, if given these features.

---

## Proposed New Features (gNB-Accessible)

After deep analysis of the simu5g codebase, the following features are readily accessible at the gNB and would provide the model with network-state awareness that static policies fundamentally cannot exploit:

### Tier 1 — High-Impact, Easy to Extract

| # | Feature | Source in simu5g | Rationale |
|---|---------|-----------------|-----------|
| 1 | **DL Scheduler Utilization** | `LteMacEnb::getUtilization(DL)` → `LteSchedulerEnb::utilization_` | Fraction of RBs used in last TTI. Directly indicates congestion level. High utilization → compress more, low → use more components. |
| 2 | **Per-UE MAC Buffer Occupancy** (bytes) | `LteMacBase::macBuffers_` → per-CID `LteMacBuffer::getQueueOccupancy()` | Large buffer = backlog building, risk of deadline violation → should compress more. This is the most actionable signal for pre-emptive compression adjustment. |
| 3 | **Active UE Count** | `LteMacEnb::getActiveUesNumber(DL)` | Number of UEs with buffered data. More granular than `num_users` since a UE might be idle between frames. |
| 4 | **HARQ Retransmission Pending Count** | `LteMacEnb::needRtxDl_` | Pending retransmissions consume RBs. An upcoming RTX burst means less capacity for new frames. |

### Tier 2 — Medium-Impact, Moderate Effort

| # | Feature | Source in simu5g | Rationale |
|---|---------|-----------------|-----------|
| 5 | **Per-UE MCS Index** (derived from CQI) | `LteAmc::getItbsPerCqi(cqi, DL)` or `UserTxParams::readCqiVector()` | MCS directly determines achievable throughput per RB. More informative than raw CQI because it accounts for AMC table mapping. |
| 6 | **Available Resource Blocks** | `LteSchedulerEnb::readTotalAvailableRbs()` | Absolute number of free RBs. Combined with per-UE data rate needs, enables the model to reason about capacity. |
| 7 | **Per-UE Allocated RBs** (previous TTI) | `LteSchedulerEnb::readPerUeAllocatedBlocks()` | How many RBs were actually allocated to each UE. Reveals scheduler fairness dynamics and whether a UE is being resource-starved. |
| 8 | **HARQ Error Rate** | `LteMacBase::getHarqErrorRate(DL)` | High HARQ error rate suggests channel degradation beyond what CQI alone conveys. |

### Tier 3 — Advanced (potentially high impact, more complex)

| # | Feature | Source in simu5g | Rationale |
|---|---------|-----------------|-----------|
| 9 | **Per-Band CQI Variance** | `LteAmc::readMultiBandCqi()` | Sub-band CQI variance indicates frequency-selective fading. High variance → some bands are good, others poor → more uncertainty. |
| 10 | **BSR Buffer Status** | `LteMacEnb::bsrbuf_` | Uplink buffer status reports (though less relevant for DL XR scenario). |

---

## Recommended Feature Set for Phase 1

For the first improvement iteration, I recommend adding **4 new features** that give the model maximum new information with minimal implementation complexity:

**Per-frame features stored in Binder (per-UE):**
1. **`buffer_bytes`** — MAC DL buffer occupancy for this UE (bytes queued at gNB)
2. **`mcs_index`** — Current MCS index derived from CQI via AMC table

**Global features (same for all users in a frame):**
3. **`dl_utilization`** — DL scheduler utilization (0.0–1.0)
4. **`n_active_ues`** — Number of actively scheduled UEs

This changes the model input from `5 * N_max` features to `7 * N_max + 2` features:
```
[error_at_80, error_ratio, cqi, fps, prev_delay_ms, buffer_bytes, mcs_index,  ← per user (×10)
 ...,
 dl_utilization, n_active_ues]                                                 ← global (×1)
```

---

## Proposed Changes

### C++ Simulation Layer (Binder + XRTrafficSource + XRTrafficReceiver)

#### [MODIFY] [Binder.h](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h)
- Add fields to [XRVideoStats](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h#66-67) struct: `bufferBytes` (unsigned int), `mcsIndex` (unsigned int)
- Add new setter/getter methods: `setXRBufferBytes()`, `getXRBufferBytes()`, `setXRMcsIndex()`, `getXRMcsIndex()`
- Add global-level fields: `dlUtilization_` (double), `nActiveUes_` (int)
- Add setter/getter methods: `setDlUtilization()`, `getDlUtilization()`, `setNActiveUes()`, `getNActiveUes()`

#### [MODIFY] [Binder.cc](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.cc)
- Implement the new setter/getter methods

#### [MODIFY] [XRTrafficSource.cc](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.cc)
- In [sendPacket()](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.cc#168-381): Before sending, query gNB MAC module to get:
  - DL buffer occupancy for this UE's CID from `macBuffers_`
  - DL scheduler utilization from `LteMacEnb::getUtilization(DL)`
  - Active UE count from `LteMacEnb::getActiveUesNumber(DL)`
  - MCS index from `LteAmc::getItbsPerCqi(cqi, DL)`
- Store these in Binder via new setter methods
- In [queryModelServer()](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.cc#778-915): Include the new features in the JSON payload sent to the model server

#### [MODIFY] [XRTrafficSource.h](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.h)
- Add pointer to gNB MAC module (`LteMacEnb*`) for runtime queries

#### [MODIFY] [XRTrafficReceiver.cc](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficReceiver.cc)
- In CSV output: Add `buffer_bytes`, `mcs_index`, `dl_utilization`, `n_active_ues` columns to per-frame result file

---

### Dataset Generation Layer

#### [MODIFY] [generate_dataset.py](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/dataset_generation/generate_dataset.py)
- Update `collect_run_results()` to capture the new columns from per-user CSV files: `buffer_bytes`, `mcs_index`, `dl_utilization`, `n_active_ues`
- Include them in the final dataset.csv output

---

### ML Training & Inference Layer

#### [MODIFY] [classifier.py](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py)
- Update `FEATURES_PER_USER` from 5 to 7 (add `buffer_bytes`, `mcs_index`)
- Add `GLOBAL_FEATURES = 2` for `dl_utilization`, `n_active_ues`
- Update input dimension: `inp = 7 * MAX_USERS + 2`
- Update [prepare_training_targets()](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py#87-185) to include new columns
- Update [predict_components()](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py#403-431) to accept and pad the new features
- Consider enlarging the shared body slightly (32→64 hidden) given the richer input

#### [MODIFY] [classifier_model_server.py](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier_model_server.py)
- Update `/predict` endpoint to accept new features in JSON: `buffer_bytes`, `mcs_index`, `dl_utilization`, `n_active_ues`
- Update state vector construction to include these

---

## Why This Should Beat Static Policy

The fundamental advantage of dynamic compression: **static policies are chosen before the simulation runs and cannot adapt to transient network states**. The new features expose exactly the transient states:

1. **Buffer build-up** → A static policy sending 50 components doesn't know its queue is growing. The dynamic model sees `buffer_bytes` climbing and can proactively reduce to 30 components for 2-3 frames, then return to 50.
2. **Scheduler congestion bursts** → When `dl_utilization` spikes (e.g., multiple UEs have large frames simultaneously), the dynamic model can reduce compression for all users briefly, whereas static policy blindly sends the same amount.
3. **MCS adaptation lag** → After a mobility-induced CQI drop, the MCS may still be high for 1-2 frames (AMC hasn't updated). The model can anticipate this if it sees CQI dropping while MCS is still high.
4. **Temporal patterns** → `prev_delay_ms` combined with `buffer_bytes` creates a two-step lookahead: rising delay + rising buffer = imminent deadline violation → compress heavily now.

---

## Verification Plan

### Automated Tests

1. **Dataset Generation Verification**
   ```bash
   # After C++ changes, run a short simulation and verify new columns appear:
   cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new
   # Run single short sim with XR-DL-RandomCL config (2 users, 5s)
   # Then check: head -5 results/user_0.csv  → should show new columns
   ```

2. **Model Training Verification**
   ```bash
   cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning
   python classifier.py
   # Verify: model trains without errors, prints accuracy metrics
   ```

3. **Model Server Verification**
   ```bash
   # Start model server, send a test request with new features:
   curl -X POST http://localhost:5000/predict \
     -H 'Content-Type: application/json' \
     -d '{"users":[{"error_at_80":1000,"error_ratio":2.0,"cqi":12,"frame_rate":60,"prev_delay_ms":3.5,"buffer_bytes":50000,"mcs_index":15},...], "dl_utilization":0.6, "n_active_ues":4}'
   ```

### Manual Verification

- **Comparison test**: After full pipeline (data generation → training → evaluation), compare with the existing static baseline results. The user should run the same multi-user sweep configuration used for the static baseline comparison and verify that the new model's mean effective error is lower.
- **The user can re-run the existing comparison pipeline** (the automation script from a previous conversation) to generate the comparison plots.

> [!IMPORTANT]
> The implementation order matters: C++ changes → rebuild simu5g → regenerate dataset → retrain model → deploy model server → run evaluation sweep. Each step depends on the previous.
