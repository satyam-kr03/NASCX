# NASCX Codebase Refactoring — Implementation Plan

Refactor, simplify, and polish the **Network-Aware Semantic Compression for XR** pipeline so that a new developer can clone, understand, build, and run the entire system within a single work session.

---

## Current State Summary

The project spans **two code trees**:

| Area | Path | Files | LoC (approx.) |
|------|------|-------|---------------|
| C++ OMNeT++ modules | `src/apps/xr/` | 10 | ~2,700 |
| Python simulation pipeline | `simulations/NR/xr/` | 17 scripts + 6 docs | ~4,500 |

**Total**: ~7,200 LoC across C++ and Python, plus 6 Markdown docs and one `.ini` config.

---

## Resolved Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | AE mode (`--mode ae`) | **Prune** — remove all AE references as dead code |
| 2 | `z-scale.py` | **Keep & generalize** — important step when adding new videos to scale to target data rate |
| 3 | `join_datasets.py` | **Dead** — remove reference from `run_all.sh` |
| 4 | Plotting scripts | **Refactor** to produce the **3 paper figures**: (a) ε̄ vs K for fixed N, (b) K_opt vs N, (c) ε̄ vs N for multiple delay bounds |
| 5 | Traffic file split | **Intentional** — `compression/traffic_files/` = training half, `comparison/traffic_files/` = evaluation half. Document clearly |

---

## Scope & Constraints

> [!IMPORTANT]
> **Scope confirmation**: This plan addresses *code quality, structure, and documentation* only. It does **not** change the scientific methodology (cost function, label smoothing, model architecture, etc.).

> [!WARNING]
> **Breaking changes**: Several file renames and directory restructures are proposed (Phase 1). The `run_all.sh` master script will be rewritten to match.

> [!IMPORTANT]
> **Build verification**: After C++ refactoring (Phase 3), we must do a full `make` of the Simu5G project. Please confirm the OMNeT++/Simu5G build environment is available.

---

## Proposed Changes

Changes are organized into **7 phases** in dependency order.

---

### Phase 1 — Project Structure & Housekeeping

Flatten confusing nesting, remove dead files, and establish a clean layout.

#### Current problems
- `pca.py` (13 lines) is a trivial wrapper around `pca/main.py` — unnecessary indirection
- `__pycache__/` directories are committed
- `run_all.sh` references a non-existent `join_datasets.py`
- `test_res.csv` (88 KB) and `test_res.csv.summary` sit in the root — stale outputs
- AE-related code paths are dead but still present in multiple scripts

#### Proposed directory layout

```
simulations/NR/xr/
├── README.md                        ← NEW: replaces Pipeline.md (expanded)
├── omnetpp.ini                      ← stays in root (OMNeT++ expects it here)
├── demo.xml                         ← stays in root
├── compression/
│   ├── README.md                    ← RENAMED from PCA_Pipeline.md
│   ├── main.py                      ← was pca/main.py (promoted)
│   ├── models.py                    ← was pca/models.py
│   ├── data.py                      ← was pca/data.py
│   ├── evaluate.py                  ← was pca/evaluate.py
│   ├── utils.py                     ← was pca/utils.py
│   ├── rescale.py                   ← RENAMED+GENERALIZED from z-scale.py
│   └── traffic_files/               ← TRAINING split (unchanged)
├── dataset_generation/
│   ├── README.md                    ← RENAMED from Dataset_Generation.md
│   └── generate_dataset.py
├── datasets/
│   ├── clean_dataset.py
│   └── pca/
├── learning/
│   ├── README.md                    ← RENAMED from Classifier_Model.md
│   ├── classifier.py
│   ├── model_server.py              ← RENAMED from classifier_model_server.py
│   ├── lag_utils.py
│   └── models/
├── comparison/
│   ├── README.md                    ← RENAMED from Comparison_Pipeline.md
│   ├── run_comparison.py            ← RENAMED from run_comparison_parallel.py
│   ├── plot_paper_figures.py        ← NEW: replaces plot_comparison.py + plot_multiuser.py
│   ├── run_multiuser_sweep.sh
│   └── traffic_files/               ← EVALUATION split (unchanged, documented)
├── scripts/
│   └── run_pipeline.sh              ← REWRITTEN from run_all.sh
├── requirements.txt                 ← NEW
└── .gitignore                       ← NEW
```

#### Files to delete/archive
- `compression/pca.py` (trivial wrapper)
- `compression/pca/__init__.py` (will refactor imports after promotion)
- `compression/pca/run_multiple.sh` (document in README instead)
- Root `test_res.csv`, `test_res.csv.summary` (stale outputs)
- `comparison/plot_comparison.py` (superseded by `plot_paper_figures.py`)
- `comparison/plot_multiuser.py` (superseded by `plot_paper_figures.py`)

#### [MODIFY] `compression/rescale.py` (was `z-scale.py`)
Currently hardcoded to a single video (`vietnam.csv`) at 60 Mbps. Generalize:
- Accept CLI args: `--input`, `--output`, `--target-mbps`, `--fps`, `--reference-cl` (default 80)
- Add proper docstring and `argparse`
- Keep the z-score + linear rescaling math unchanged

---

### Phase 2 — Python Code Quality (All Scripts)

Systematic improvements applied consistently across all Python files.

#### [MODIFY] `dataset_generation/generate_dataset.py` (506 → ~400 lines)

**Issues to fix:**
1. **Redundant `import random` inside `run_simulation()`** (line 153) — already imported at module top
2. **Global mutable state** (`TRAFFIC_DIR`, `PCA_FILES`, `DATASET_DIR`, `FILE_PREFIX`) set via `global` — refactor to a config dataclass passed through functions
3. **Magic numbers**: line 47 comment says "2000 frames" but `MAX_FRAMES = 1000`
4. **`run_simulation()` takes a single 7-element tuple** — use a dataclass for readability
5. **`--mode ae` argument and all AE code paths** — remove entirely
6. **Error handling**: bare `print()` instead of `logging`

**Changes:**
- Add `@dataclass` for `SimConfig` and `RunResult`
- Prune all `--mode ae` / AE references
- Replace `print()` with `logging`
- Fix stale comment about "2000 frames"
- Extract `build_prescribed_schedule()` from the monolithic `run_simulation()`

---

#### [MODIFY] `learning/classifier.py` (555 → ~470 lines)

**Issues to fix:**
1. **`prepare_training_targets()` is 135 lines** — decompose into oracle target computation + feature padding
2. **Stale comments**: Line 163 mentions "LSTM" and "sequences" — model is an MLP
3. **Dead code**: Commented-out inference example (lines 550-555)
4. **Docstring mismatch**: `CompressionDataset` says "5\*max_users" but actual is `21*max_users+2`
5. **`LABEL_SMOOTH_STD`** set to `1.0` but doc says `1.5` — pick `1.0` (it's the active code value) and fix doc

**Changes:**
- Decompose `prepare_training_targets()` into:
  - `compute_oracle_targets(df, num_users)` → cost function + optimal selection
  - `build_padded_features(opt, num_users, max_users)` → X, Y, M matrices
- Add `predict_with_probabilities()` function (needed by model server — see below)
- Remove dead commented code
- Fix all stale comments and docstrings
- Add `verify_class_mapping()` assertion at module load

---

#### [MODIFY] `learning/model_server.py` (was `classifier_model_server.py`, 267 → ~200 lines)

**Issues to fix:**
1. **Duplicate scaling/padding logic** (lines 190-215) — copy-pasted from `predict_components()`. The endpoint calls `predict_components()` on line 181, then *reimplements the same logic* to get probabilities
2. **AE references in docstrings** — remove

**Changes:**
- Use new `predict_with_probabilities()` from `classifier.py` — eliminate 25 lines of duplicate code
- Add request/response logging
- Use `pathlib.Path` consistently

---

#### [MODIFY] `learning/lag_utils.py` (110 → ~70 lines)

**Issues to fix:**
1. **Dead variable**: `n_dropped` on line 62 is `len(df) - len(df)` — always 0
2. **`check_lag_quality()` never called** — remove as dead code
3. **Module docstring** references `compression_policy.py` which doesn't exist

**Changes:**
- Fix `n_dropped` computation
- Remove `check_lag_quality()` (40 lines of dead code)
- Fix stale docstring

---

#### [MODIFY] `datasets/clean_dataset.py` (97 → ~85 lines)

**Issues to fix:**
1. **Row-by-row `apply()` for delay check** — extremely slow on large datasets. Vectorize
2. **No logging of removed rows**

**Changes:**
- Vectorize delay-check logic using pandas boolean indexing
- Add summary statistics output

---

#### [MODIFY] `comparison/run_comparison.py` (was `run_comparison_parallel.py`, 708 → ~480 lines)

**Issues to fix:**
1. **Massive code duplication**: Model-results and static-results branches in `assemble_comparison()` are near-identical 40-line blocks (lines 393-446 vs 449-502)
2. **Double `import argparse`** (lines 22 and 40)
3. **`COMP_LEVELS` computed at module load** using `MODE='pca'` — AE branch is dead anyway
4. **Print string "step 25"** (line 581) — actual step is 5
5. **All AE references** — prune

**Changes:**
- Extract `_extract_user_metrics(run_dir, user_idx, df)` helper
- Remove all AE code paths and the `--mode` argument
- Remove duplicate `import argparse`
- Fix "step 25" → "step 5"

---

#### [NEW] `comparison/plot_paper_figures.py` (~300 lines)

Replaces `plot_comparison.py` (414 lines) + `plot_multiuser.py` (395 lines) with a single focused script producing the **3 paper figures**:

**Figure 1: ε̄ vs K** — Mean effective error as a function of static compression level K for a given N
- Reads `comparison_results/comparison_usersN.csv` for a specific N
- Plots static curve + model horizontal band
- Largely exists as `fig_error_vs_cl()` in current `plot_comparison.py` — extract and clean

**Figure 2: K_opt vs N** — Optimal static compression level versus number of users
- Reads all `comparison_users{2..10}.csv` files
- For each N, finds the static CL that minimizes mean error
- Line plot of K_opt on y-axis vs N on x-axis
- **New logic** — not directly present in either current script

**Figure 3: ε̄ vs N for multiple delay bounds** — Mean effective error versus N, one curve per deadline value
- Requires comparison runs at multiple `deadlineMs` values (2.5, 5, 10, 20 ms)
- For each (N, deadline), plot model's ε̄
- **New logic** — requires the sweep to be run at multiple deadlines, which means `run_multiuser_sweep.sh` needs a `--deadline` parameter

**Shared infrastructure:**
- Shared `PALETTE`, `plt.rcParams` style block (currently duplicated between both scripts)
- Shared `load()`, `static_agg()`, `model_stats()` helpers
- All figures output PDF + PNG at 300 DPI with IEEE column widths

**CLI interface:**
```
python plot_paper_figures.py --figure 1 --num-users 5      # ε̄ vs K
python plot_paper_figures.py --figure 2                     # K_opt vs N
python plot_paper_figures.py --figure 3                     # ε̄ vs N (multi-deadline)
python plot_paper_figures.py --all                          # generate all 3
```

---

#### [MODIFY] `compression/pca/*.py` (707 lines total)

**Issues to fix:**
1. `pca.py` wrapper doesn't forward CLI args to `main()`
2. `data.py`: Hardcoded resolution `(224, 224)` not parameterized

**Changes:**
- Promote `pca/main.py` → `compression/main.py`; remove `pca.py` wrapper and `pca/__init__.py`
- Adjust internal imports (`from .models import ...` → `from models import ...`)

---

### Phase 3 — C++ Code Quality

#### [MODIFY] [XRTrafficSource.h](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.h)

**Issues to fix:**
1. **`using namespace std;` and `using namespace omnetpp;`** in a header — namespace pollution
2. **Scaffolding comments**: `// ===== ADD THESE FOR BINDER SUPPORT =====` / `// ===== END ADDITIONS =====`
3. **Mixed initialization** in constructor member initializer list

**Changes:**
- Remove `using namespace` directives; use explicit qualification
- Remove scaffolding comments
- Use C++11 in-class member initializers
- Add Doxygen comments to public/protected methods

---

#### [MODIFY] [XRTrafficSource.cc](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficSource.cc) (~1008 → ~850 lines)

**Issues to fix:**
1. **`sendPacket()` is 130 lines** — 4 near-identical branches for `random`/`prescribed`/`model`/`fixed`
2. **`sprintf(msgName, ...)` buffer** — unsafe
3. **`httpPost()` uses `popen("wget ...")` + temp files** — fragile
4. **`queryModelServer()` manual JSON parsing** — fragile string search
5. **Magic number `150528`** (uncompressed PCA feature count) — undocumented
6. **`std::cout` mixed with `EV <<`** — inconsistent logging
7. **`loadPCAData()` is 175 lines** — monolithic

**Changes:**
- Extract `FrameInfo resolveFrameInfo(int frameNum)` — eliminates 4-way branch duplication
- Replace `sprintf` with `snprintf`
- Add RAII temp file wrapper for `httpPost()`
- Define `static constexpr int UNCOMPRESSED_COMPONENTS = 150528;`
- Remove all `std::cout`; use `EV <<` consistently
- Decompose `loadPCAData()` into `parseCSV()`, `buildErrorVectors()`, `computeVideoStats()`

---

#### [MODIFY] [XRTrafficReceiver.cc](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficReceiver.cc) (~654 → ~550 lines)

**Issues to fix:**
1. **12 `std::cout` debug statements** — should use OMNeT++ `EV` macros
2. **`getMaxMSE()` prints CWD** — debugging leftover
3. **Static variables for global stats** persist across simulation restarts
4. **Commented-out `recordScalar` block** — dead code
5. **Duplicate Binder lookup** — same pattern as `XRTrafficSource.cc`

**Changes:**
- Replace all `std::cout` with `EV <<`
- Remove CWD debug printing
- Add `ReceivedFrameStats::createLost()` static factory
- Add static variable reset in `initialize()`
- Remove dead `recordScalar` code
- Extract `Binder* resolveBinderModule()` into shared `XRUtils.h`

---

#### [MODIFY] [XRTrafficReceiver.h](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/src/apps/xr/XRTrafficReceiver.h)

- Remove `using namespace` directives
- Move `#include <fstream>` to `.cc`

---

#### [NEW] `src/apps/xr/XRUtils.h`

Shared utilities:
- `Binder* resolveBinderModule(omnetpp::cSimulation*)` — used by both Source and Receiver
- `static constexpr int UNCOMPRESSED_COMPONENTS = 150528;`
- `static constexpr int NUM_CL_LEVELS = 16;`

---

### Phase 4 — OMNeT++ Configuration Cleanup

#### [MODIFY] [omnetpp.ini](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr/omnetpp.ini) (498 → ~350 lines)

**Issues to fix:**
1. **4 configs share ~90% identical UE position blocks** — copy-pasted 4 times
2. **Stale config `XR-DL-Dataset`** — superseded by `XR-DL-RandomCL`
3. **Commented-out queue overrides** at bottom (lines 495-498)
4. **Inconsistent `deadlineMs`**: SingleUser=10ms, others=5ms
5. **Inconsistent `expectedFrames`**: 1074 vs 1000
6. **`XR-DL-MultiUser-MaxCQI`** is near-identical to `XR-DL-MultiUser-PF`**

**Changes:**
- Create `[Config NR-XR-Positions]` mixin for UE positions (define once)
- Remove or archive `XR-DL-Dataset`
- Remove commented-out queue overrides
- Add inline comments explaining deadline/frame count choices
- Consolidate `MaxCQI` + `PF` using `${scheduler=PF,MAXCI}` iteration

---

### Phase 5 — Documentation Overhaul

#### [NEW] `simulations/NR/xr/README.md`

Replace `Pipeline.md` with a comprehensive developer README:
1. **Prerequisites**: OMNeT++ version, Simu5G version, Python version, pip dependencies
2. **Quick Start**: 5-step copy-paste guide
3. **Architecture Diagram**: Mermaid flowchart (data flow between components)
4. **Directory Layout**: Table with purpose + train/eval traffic split explanation
5. **Configuration Reference**: Key `omnetpp.ini` parameters
6. **Troubleshooting**: Common failures and fixes

#### [MODIFY] All per-module `README.md` files

Standardize format:
1. **Overview** (2-3 sentences)
2. **Usage** (exact CLI commands)
3. **Inputs / Outputs** (table)
4. **Key Parameters** (table with defaults)
5. **Implementation Notes**

#### [MODIFY] [onboarding.md](file:///home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/onboarding.md)

- Remove citation markers (`[cite_start]`, `[cite: ...]`)
- Add cross-references to per-module READMEs
- Add "Getting Started" section

#### [NEW] `src/apps/xr/README.md`

C++ module developer guide:
- Build instructions
- Module interaction diagram (Source → UDP → Receiver → Binder feedback)
- How to add a new selection mode / metric

---

### Phase 6 — Developer Experience

#### [NEW] `simulations/NR/xr/requirements.txt`

```
pandas>=2.0
numpy>=1.24
torch>=2.0
scikit-learn>=1.3
fastapi>=0.100
uvicorn>=0.23
requests>=2.31
matplotlib>=3.7
```

#### [MODIFY] `scripts/run_pipeline.sh` (was `run_all.sh`)

Rewrite as a robust, documented pipeline runner:
- Add argument parsing (`--skip-compression`, `--skip-training`, `--num-users`, etc.)
- Add prerequisite checks (Python version, pip packages, simu5g binary)
- Remove dead `join_datasets.py` step
- Fix and uncomment the model server launch/teardown
- Add color-coded status output and timing per phase

#### [MODIFY] `comparison/run_multiuser_sweep.sh`

- Add `--deadline` parameter to support sweeping delay bounds for paper Figure 3
- Update call from `run_comparison_parallel.py` → `run_comparison.py`
- Remove AE mode references

#### [NEW] `simulations/NR/xr/.gitignore`

```gitignore
__pycache__/
*.pyc
*.pyo
results/
datasets/pca/dataset.csv
comparison/comparison_results*/
learning/models/
*.log
test_res.csv*
```

---

### Phase 7 — Testing & Validation

| Phase | Verification |
|-------|-------------|
| 1 (Structure) | All imports resolve; `python -c "from compression.main import main"` works |
| 2 (Python quality) | `python -m py_compile <file>` on every `.py`; `python generate_dataset.py --dry-run` succeeds |
| 3 (C++ quality) | Full `make` of Simu5G project compiles cleanly |
| 4 (Config) | `simu5g omnetpp.ini -u Cmdenv -c XR-DL-SingleUser --sim-time-limit=1s` runs without error |
| 5 (Docs) | Manual review of all README.md files |
| 6 (DX) | `pip install -r requirements.txt && bash scripts/run_pipeline.sh --help` works |
| 7 (Final) | End-to-end dry-run verification |

---

## Verification Plan

### Automated Tests
1. `python -m py_compile` on every Python file after changes
2. `make` of the Simu5G project after C++ changes
3. `python generate_dataset.py --dry-run` to verify argument parsing
4. `python -c "from learning.classifier import MultiUserCompressionNet; print('OK')"` to verify imports
5. Quick simulation smoke test: `simu5g omnetpp.ini -u Cmdenv -c XR-DL-SingleUser --sim-time-limit=2s`

### Manual Verification
- Walk through the new README as if onboarding — every command should copy-paste and work
- Verify `run_pipeline.sh --help` prints sensible output
- Verify `.gitignore` correctly ignores generated artifacts

---

## Estimated Effort

| Phase | Est. Time | Priority |
|-------|-----------|----------|
| 1 — Structure | 1-2 hours | High |
| 2 — Python quality | 3-4 hours | High |
| 3 — C++ quality | 3-4 hours | High |
| 4 — Config cleanup | 1 hour | Medium |
| 5 — Documentation | 2-3 hours | High |
| 6 — Developer experience | 1-2 hours | Medium |
| 7 — Testing | 1-2 hours | High |
| **Total** | **~12-17 hours** | |

Recommended execution order: **Phase 1 → 2 → 3 → 4 → 5 → 6 → 7** (structure first so imports work, then code quality, then docs and DX last).
