# Multi-User Compression Level Classifier

This document details the neural network implementation and training pipeline for the optimal XR compression level assignment, as defined in `classifier.py`.

## 1. Overview
The learning module features a PyTorch-based multi-user classifier designed to predict the optimal number of dimensionality reduction components (e.g., PCA/Autoencoder components) to be transmitted per user. 

Instead of a regression task, the problem is formulated as a classification over **16 discrete classes**, mapping directly to the viable transmission configurations: `components ∈ {5, 10, 15, ..., 80}`. The system utilizes a **single unified model** capable of handling dynamic admission up to a maximum concurrent user count ($N_{max} = 10$).

---

## 2. Neural Network Architecture (`MultiUserCompressionNet`)

The classifier operates on a multi-head architecture, aiming to decouple shared feature extraction from user-specific decision generation, utilizing zero-padding for generic dynamic user loads:

- **Input Features**: The state tensor comprises `(3 * N_max) + 2` interleaved features representing the system and radio environment state (dynamically padded with zeros for inactive slots):
  `[error_at_80, error_ratio, cqi_0, fps_0, prev_delay_ms_0, cqi_1, fps_1, prev_delay_ms_1, ..., 0, 0, 0]`
- **Shared Body Extraction**: Designed to be deliberately lightweight to counteract over-fitting given the dataset bounds.
  - `Linear(input_dim, 32) → ReLU → Dropout(p=0.2) → Linear(32, 16) → ReLU`
- **Classification Heads**: There is `1` unique linear layer outputting raw logits of size `16` (classes) for *each* of the `N_max` possible user slots.

---

## 3. Training Paradigm & Specific Enhancements

During development, initial attempts encountered heavy accuracy stagnation, mostly resulting from predicting the most frequently occurring class. The revised logic in `classifier.py` incorporates four central design changes to effectively conquer this constraint:

### A. Non-Contradictory Optimal Targets (Label Unification)
The simulation data intrinsically operates as a grid-search log (where the same state evaluated multiple different compression assignments). Feeding raw rows into supervised learning causes contradictory input-to-label mappings. 
**Solution**: Grouping variables across macroscopic bins (`avg_cqi_bin`, `avg_fps_bin`, `avg_delay_bin`, etc.) and resolving the target label using an oracle formulation (`idxmin`) of the lowest total resulting network cost for that state.

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
