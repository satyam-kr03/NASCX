# Implementation Plan: Dynamic Per-Frame Compression

> **Date**: February 10, 2026
> **Goal**: Transform the system from static per-session compression to truly dynamic per-frame compression where each frame can receive a different compression level based on its actual size and current network conditions.

---

## Problem Statement

Currently, the ML model predicts **one compression level per user** before the simulation starts. Every frame for that user uses the same compression, regardless of:
- **Frame size variations** — large complex frames get the same treatment as small simple ones
- **Changing network conditions** — CQI measured once in warmup, never re-evaluated

This makes the system a "network-aware configuration selector" rather than a truly dynamic adaptive compressor.

---

## Key Insight: No C++ Changes Required

The `XRTrafficSource` already supports varying `components` values per frame — it simply reads `(frame, components, mse, size_bytes)` from the CSV sequentially. If we generate a CSV where frame 1 has `components=15` and frame 2 has `components=50`, the simulation handles it natively.

**The entire adaptation logic lives in the Python-side CSV generation.**

---

## Architecture Overview

```
CURRENT (Static):
  ML Model → one compression_level per user → fixed PCA CSV → simulation

NEW (Dynamic):
  ML Model → per-frame compression_level → adaptive PCA CSV → simulation
             ↑                                    ↑
     (num_users, cqi, fps,              (each frame row has
      current_frame_size)                different components)
```

---

## Implementation Steps

### Step 1: Enrich PCA Sweep Data with Frame Complexity Metric

**File**: No new files needed — use existing `traffic_*.csv` / `pca_sweep_summary_scaled.csv`

Each traffic profile's PCA sweep data already contains per-frame sizes at ALL 16 compression levels. We define a **frame complexity proxy**:

```
frame_complexity = size_bytes at components=80 (maximum quality / least compression)
```

This is the "uncompressed-equivalent" size — a large value means the frame is complex (high-motion, detailed content) and will need more careful compression decisions.

**Rationale**: At `components=80`, the frame is minimally compressed, so `size_bytes` reflects the inherent frame complexity. A complex frame at `components=80` might be 120KB, while a simple one might be 40KB. The model needs this to make per-frame decisions.

No code changes needed for this step — the data already exists in the CSV files.

---

### Step 2: Generate Per-Frame Dataset

**File**: `generate_per_frame_dataset.py` (new)

**Purpose**: Run batch simulations where each frame uses a potentially different compression level, and record per-frame delivery outcomes.

#### 2a. Simulation Strategy

Since we need per-frame ground truth (did frame X with size S arrive on time at CQI C?), we run simulations with **mixed compression levels**:

- For each simulation run:
  1. Randomly assign compression levels **per-frame** (not per-user)
  2. Generate adaptive PCA CSVs where each frame row has a randomly selected compression level
  3. Run the simulation
  4. Parse per-frame results from the receiver's CSV output

#### 2b. Per-Frame Result Collection

The `XRTrafficReceiver` already writes per-frame results to a CSV file when `resultFile` is configured:

```csv
frameNumber,components,mse,sizeBytes,genTime,recvTime,delay_ms,receivedOnTime,effectiveError,deadline_ms
```

This is **exactly** what we need! Each row tells us whether a frame with `sizeBytes` and `components` arrived on time at the given network conditions.

We configure this by adding `--*.ue[*].app[0].resultFile=...` to the simulation command.

#### 2c. New Dataset Schema

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | int | Simulation run identifier |
| `num_users` | int | Total users in simulation (2-10) |
| `user_id` | int | User index |
| `fps` | int | Frame rate |
| `avg_cqi` | float | Average CQI for this user (from simulation) |
| `frame_number` | int | Frame index within the stream |
| `frame_complexity` | float | Size at max components (80) — proxy for inherent frame difficulty |
| `compression_level` | int | PCA components used for this frame |
| `compressed_size_bytes` | int | Actual compressed frame size |
| `mse` | float | Reconstruction error at this compression |
| `delay_ms` | float | Actual delivery delay |
| `received_on_time` | int | 1 if delay ≤ deadline, 0 otherwise |

This dataset captures **per-frame** relationships between frame complexity, compression, network conditions, and delivery success.

#### 2d. Generating Mixed-Compression PCA CSVs

```python
def create_adaptive_pca_file(user_id, frame_compression_map, data_by_level, output_dir):
    """Create a PCA CSV where each frame can have a different compression level.
    
    Args:
        frame_compression_map: dict mapping frame_number -> compression_level
        data_by_level: dict mapping compression_level -> list of frame dicts
    """
    output_file = output_dir / f"user_{user_id}_adaptive.csv"
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'components', 'mse', 'size_bytes'])
        
        for frame_num, comp_level in sorted(frame_compression_map.items()):
            # Find this frame at the specified compression level
            frames_at_level = data_by_level[comp_level]
            frame_data = next(fr for fr in frames_at_level if fr['frame'] == frame_num)
            writer.writerow([frame_data['frame'], frame_data['components'],
                           frame_data['mse'], frame_data['size_bytes']])
    
    return output_file
```

#### 2e. Simulation Sweep Parameters

For comprehensive per-frame training data:

| Parameter | Values |
|-----------|--------|
| `num_users` | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| `fps` | 60, 72, 90, 120 |
| `traffic_profile` | 5 profiles |
| `compression strategy` | "random-per-frame" (random comp per frame) |
| `runs per config` | 5-10 |

Each simulation produces `num_users × num_frames` training samples, so even a modest sweep generates abundant per-frame data.

---

### Step 3: Derive Per-Frame Optimal Compression Labels

**File**: Part of `train_dynamic_model.py` (new)

From the per-frame dataset, for each scenario `(num_users, cqi_bin, fps, frame_complexity_bin)`:

1. Group all observations across all frames that share similar conditions
2. For each `compression_level` tested, compute the fraction that arrived on time
3. Among compression levels with ≥ 80% on-time rate, select the one with **lowest MSE** (least compression, best quality)
4. This is the **optimal per-frame compression label**

```python
def find_per_frame_optimal(group):
    """For a group of similar frames, find the optimal compression level."""
    # Aggregate by compression_level
    stats = group.groupby('compression_level').agg(
        on_time_rate=('received_on_time', 'mean'),
        avg_mse=('mse', 'mean')
    ).reset_index()
    
    # Filter: must meet reliability threshold
    reliable = stats[stats['on_time_rate'] >= RELIABILITY_THRESHOLD]
    
    if len(reliable) > 0:
        # Best quality among reliable options (lowest MSE = lowest compression)
        return reliable.loc[reliable['avg_mse'].idxmin(), 'compression_level']
    else:
        # Fallback: highest compression (smallest size)
        return stats.loc[stats['on_time_rate'].idxmax(), 'compression_level']
```

The binning strategy:
- **CQI bins**: width 0.5 (same as current)
- **Frame complexity bins**: width based on data distribution (e.g., quantile-based, ~10 bins)
- **FPS**: exact values (60, 72, 90, 120)

---

### Step 4: Train Per-Frame Model

**File**: `train_dynamic_model.py` (new)

#### 4a. Features

| Feature | Description | Source |
|---------|-------------|--------|
| `num_users` | Users in the cell | Simulation config |
| `cqi` | Channel quality indicator | Simulation result |
| `fps` | Frame rate | Simulation config |
| `frame_complexity` | Frame size at max components (80) | PCA sweep data |

**Key change**: `frame_complexity` replaces the static `(size_mean_kb, size_std_kb)` pair. This is a per-frame feature that varies with every frame.

#### 4b. Target

`optimal_compression` — per-frame optimal compression level (5, 10, ..., 80)

#### 4c. Model

XGBoost Regressor (same architecture as current, but now trained on per-frame data):

```python
FEATURE_COLUMNS = ['num_users', 'cqi', 'fps', 'frame_complexity']

model = XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.08,
    min_child_weight=2,
    subsample=0.8,
    colsample_bytree=0.8,
)
```

#### 4d. Validation

Evaluate with:
- **Exact match accuracy**: predicted compression == optimal
- **Within ±5 accuracy**: practical tolerance
- **Simulated QoE**: run simulations with predicted per-frame compression and compare vs static

#### 4e. Output

Same format as current:
```python
joblib.dump({
    'model': model,
    'scaler': scaler,
    'feature_columns': FEATURE_COLUMNS,
    'valid_compression_levels': VALID_COMPRESSION_LEVELS.tolist(),
    'model_type': 'per_frame'  # NEW: identifies this as per-frame model
}, MODEL_PATH)
```

---

### Step 5: Update Model Server

**File**: `model_server.py` (modify)

#### 5a. New Request Schema

Add a `frame_complexity` field and a batch endpoint optimized for per-frame queries:

```python
class PerFramePredictionRequest(BaseModel):
    """Request schema for per-frame compression prediction."""
    num_users: int = Field(..., ge=1, le=20)
    avg_cqi: float = Field(..., ge=1.0, le=15.0)
    fps: int = Field(default=60, ge=30, le=144)
    frame_complexity: float = Field(..., ge=0.0, description="Frame size at max components (bytes)")

class FrameBatchRequest(BaseModel):
    """Batch request for all frames of a user."""
    num_users: int
    avg_cqi: float
    fps: int
    frame_complexities: List[float]  # One per frame
```

#### 5b. New Endpoint

```python
@app.post("/predict_per_frame")
async def predict_per_frame(request: FrameBatchRequest):
    """Predict compression level for each frame based on its complexity."""
    features = np.array([
        [request.num_users, request.avg_cqi, request.fps, fc]
        for fc in request.frame_complexities
    ])
    
    if scaler is not None:
        features = scaler.transform(features)
    
    raw_preds = model.predict(features)
    results = [snap_to_compression_level(p) for p in raw_preds]
    
    return {"per_frame_compression": results}
```

This is much more efficient than making one HTTP request per frame — a single batch call handles 1000+ frames.

---

### Step 6: Update Comparison Pipeline

**File**: `run_comparison.py` (modify)

#### 6a. New `get_compression_levels_dynamic()` Function

```python
def get_compression_levels_dynamic(num_users, fps_rates, traffic_profiles, user_cqis):
    """Get per-frame compression levels for each user (dynamic mode).
    
    Returns:
        Dict[int, Dict[int, int]] — user_id -> {frame_number: compression_level}
    """
    per_user_frame_compressions = {}
    
    for user_id in range(num_users):
        cqi = user_cqis.get(user_id, 14.0)
        fps = fps_rates[user_id]
        profile = traffic_profiles[user_id]
        
        # Load this user's PCA sweep data
        traffic_file = SIMULATION_DIR / profile['file']
        data_by_level = load_pca_data(traffic_file)
        
        # Get frame complexity = size_bytes at components=80 for each frame
        max_comp_frames = data_by_level[80]  # frames at max quality
        frame_complexities = [f['size_bytes'] for f in max_comp_frames]
        
        # Query model for per-frame compression in one batch
        response = requests.post(f"{MODEL_SERVER_URL}/predict_per_frame", json={
            "num_users": num_users,
            "avg_cqi": cqi,
            "fps": fps,
            "frame_complexities": frame_complexities
        })
        
        per_frame_comps = response.json()["per_frame_compression"]
        
        # Map frame_number -> compression_level
        frame_comp_map = {
            max_comp_frames[i]['frame']: per_frame_comps[i]
            for i in range(len(max_comp_frames))
        }
        
        per_user_frame_compressions[user_id] = frame_comp_map
    
    return per_user_frame_compressions
```

#### 6b. New `create_adaptive_pca_file()` Function

```python
def create_adaptive_pca_file(user_id, frame_comp_map, data_by_level, output_dir):
    """Create PCA CSV where each frame has a DIFFERENT compression level."""
    output_file = output_dir / f"user_{user_id}_adaptive.csv"
    
    # Index data_by_level for fast lookup: (frame, components) -> row
    frame_lookup = {}
    for level, frames in data_by_level.items():
        for f in frames:
            frame_lookup[(f['frame'], level)] = f
    
    with open(output_file, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(['frame', 'components', 'mse', 'size_bytes'])
        
        for frame_num in sorted(frame_comp_map.keys()):
            comp = frame_comp_map[frame_num]
            row = frame_lookup[(frame_num, comp)]
            writer.writerow([row['frame'], row['components'], 
                           row['mse'], row['size_bytes']])
    
    return output_file
```

#### 6c. Updated `run_simulation()` for Dynamic Mode

The existing `run_simulation` takes `compression_levels: List[int]` (one per user). For dynamic mode, it takes a dict of per-frame maps instead. The simulation command stays the same — only the PCA CSV content changes.

#### 6d. Two-Way Comparison

The comparison includes two modes:

| Mode | Description |
|------|-------------|
| `uncompressed` | All frames at components=80 (maximum quality, least compression) |
| `ml-dynamic` | ML-predicted per-frame compression (adaptive) |

---

### Step 7: Update Documentation

**Files**: `docs/ComparisonStudy.md`, `docs/DatasetGeneration.md`

Update to reflect:
- New dataset schema with per-frame features
- Two-way comparison methodology (Uncompressed vs ML-Dynamic)
- New results and findings

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `generate_per_frame_dataset.py` | **CREATE** | New dataset generation with per-frame results |
| `train_dynamic_model.py` | **CREATE** | Train per-frame compression model |
| `model_server.py` | **REWRITE** | Dynamic-only server with `/predict_per_frame` endpoint |
| `run_comparison.py` | **REWRITE** | Uncompressed vs ML-Dynamic comparison |
| `docs/ComparisonStudy.md` | **REWRITE** | Document two-way comparison methodology |
| `docs/DatasetGeneration.md` | **MODIFY** | Document per-frame dataset schema |
| `train_improved_model.py` | **REMOVED** | Static model training no longer needed |
| `compression_model.joblib` | **REMOVED** | Static model artifact no longer needed |
| `compression_scaler.joblib` | **REMOVED** | Static model scaler no longer needed |
| `XRTrafficSource.cc` | **NO CHANGE** | Already supports varying components per frame |
| `XRTrafficReceiver.cc` | **NO CHANGE** | Already writes per-frame CSV results |

---

## Execution Order

```
1. generate_per_frame_dataset.py  → produces per_frame_dataset.csv
2. train_dynamic_model.py         → produces compression_model_dynamic.joblib
3. model_server.py                → serves per-frame predictions (dynamic only)
4. run_comparison.py              → runs Uncompressed vs ML-Dynamic comparison
5. docs/                          → documents results
```

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Per-frame simulations take longer (mixed compression CSVs) | Same simulation time — only CSV content changes |
| Model overfits to per-frame noise | Use binning for frame_complexity (quantile-based) |
| HTTP latency for batch predictions | Single batch endpoint for all frames per user |
| Dataset size explosion | Each sim already produces ~1000+ frames × users of training data |

---

## Expected Impact

| Metric | Uncompressed (Baseline) | Dynamic ML (expected) |
|--------|------------------------|----------------------|
| **MSE** | ~0 (best possible) | Higher — trade-off of adaptive compression |
| **Delay** | Higher — large frames take longer | Lower — smaller compressed frames delivered faster |
| **Reliability** | Lower — deadline violations from large frames | Higher — per-frame adaptation prevents missed deadlines |
| **Satisfaction** | Lower — large frames cause failures | Higher — per-frame adaptation prevents the "one bad frame ruins everything" problem |

The key insight: **Uncompressed transmission provides the best quality but poorest delivery reliability.** The dynamic model trades acceptable quality for significantly better delivery by compressing large, complex frames that would otherwise miss their deadlines.
