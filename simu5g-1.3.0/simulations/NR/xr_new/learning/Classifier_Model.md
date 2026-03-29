# Multi-User Compression Level Classifier

This document details the neural network implementation and training pipeline for the optimal XR compression level assignment, as defined in `classifier.py`.

## 1. Overview
The learning module features a PyTorch-based multi-user classifier designed to predict the optimal number of dimensionality reduction components (e.g., PCA/Autoencoder components) to be transmitted per user. 

Instead of a regression task, the problem is formulated as a classification over **16 discrete classes**, mapping directly to the viable transmission configurations: `components ∈ {5, 10, 15, ..., 80}`. The system utilizes a **single unified model** capable of handling dynamic admission up to a maximum concurrent user count ($N_{max} = 10$).

---

## 2. Neural Network Architecture (`MultiUserCompressionNet`)

The classifier operates on a multi-head architecture, aiming to decouple shared feature extraction from user-specific decision generation, utilizing zero-padding for generic dynamic user loads:

- **Input Features**: The state tensor comprises `(7 * N_max) + 2` interleaved features representing the system and radio environment state (dynamically padded with zeros for inactive slots):
  `[user0_error_at_80, user0_error_ratio, user0_cqi, user0_frame_rate, prev_user0_delay_ms, user0_buffer_bytes, user0_mcs_index, user1_error_at_80, ..., dl_utilization, n_active_ues]`
- **Shared Body Extraction**: Designed to be deliberately lightweight to counteract over-fitting given the dataset bounds.
  - `Linear(input_dim=7*N_max+2, 64) → ReLU → Dropout(p=0.2) → Linear(64, 32) → ReLU`
- **Classification Heads**: `N_max` parallel linear head layers, each outputting raw logits of size `NUM_CLASSES=16` for each user slot.

---

## 3. Training Paradigm & Specific Enhancements

During development, initial attempts encountered heavy accuracy stagnation, mostly resulting from predicting the most frequently occurring class. The revised logic in `classifier.py` incorporates four central design changes to effectively conquer this constraint:

### A. Non-Contradictory Optimal Targets (Label Unification)
The simulation data intrinsically operates as a grid-search log (where the same state is evaluated under many different per-user component configurations). Feeding raw rows into supervised learning causes contradictory input-to-label mappings.
**Solution**: Frame-level optimal target selection is computed via a cost function and then `groupby("frameNumber").idxmin()` to pick the single best row per frame.
- Cost is: `total_cost = total_error_scaled + (0.15 * variance_penalty_scaled) + (1e-3 * avg_comps_scaled)`
- `total_error` uses frame-rate-normalized effective errors (`error / fps`) so high-FPS users are not unfairly underweighted.
- `variance_penalty` encourages fairness instead of extreme starvation of specific users.
- This produces clean target classes per frame (one class per active user) and supports padded states for $N < N_{max}$.
### B. Custom Cost Mechanism 
The optimization target blends transmission distortion and bandwidth allocation. A cost index is formulated dynamically per `num_users` count:
```
total_cost = total_error_scaled + penalty_weight * (avg_comps_scaled ^ 2)
```
- The `penalty_weight` naturally pushes back against utilizing 80 components per user. It purposefully scales linearly based on network density, triggering at `N > 2` (`0.25 * max(0, num_users - 2)`).

### C. Gaussian State Augmentation
Synthetically enhances variation, which significantly limits model memorization of the roughly ~130 unique macroscopic states identified in smaller setups.
**Implementation**: Inside the `CompressionDataset`, uniform Gaussian noise is layered onto the input states (`augment_std = 0.2`) on consecutive batches.

### D. Ordinal Soft Labels & Masked KL-Divergence
In standard CrossEntropy loss, predicting 5 components when 10 was the correct target induces equivalent loss to randomly predicting 80; there is no penalty correlation to proximity. 
**Implementation**: `make_soft_labels()` structures the integer target into a Gaussian probability distribution mapped across adjoining classes (`std=1.5`). The error gradients are then minimized referencing **KL Divergence**. To scale this dynamically without compromising the shared body limits, the total loss utilizes a **masking strategy**, zeroing-out penalty computations for classification heads predicting inactive padded slots, guaranteeing the shared body exclusively updates based on real user interference structures.

---

## 4. Pipeline Execution

The primary entry point `train_all` controls the flow:
1. **Pre-processing**: Loads `datasets/pca/dataset.csv`.
2. **Data Amalgamation & Padding**: Loops from 2 to 10 users building normalized row instances zero-padded seamlessly to state requirements up to $N_{max} = 10$.
3. **Data Splitting & Scaling**: Generates combined `.2` splits, utilizing an isolated `StandardScaler` ensuring that generic $(0,0,0)$ padding retains numerical neutrality globally while true states are explicitly standardized.
4. **Optimization Routine**: Runs `Adam` optimizer (weight decay $10^{-4}$) partnered with a `CosineAnnealingLR` scheduler across 300 epochs factoring dynamic batch divisor scales.
5. **Evaluation**: Predicts outcomes on active validation states calculating percentages matching: 
   - `Exact match`
   - `Within ±1 Class (±5 components)`
   - `Within ±3 Classes (±15 components)`
6. **Persistence**: Deploys the unified state optimized weights into `/models/compression_unified.pth` alongside its corresponding standardized state `pickle`.
