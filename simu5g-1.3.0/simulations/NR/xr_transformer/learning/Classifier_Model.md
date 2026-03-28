# Multi-User Compression Level Classifier (Transformer)

This document details the neural network implementation and training pipeline for the optimal XR compression level assignment, as defined in `classifier.py`.

## 1. Overview
The learning module features a PyTorch-based multi-user classifier that predicts the optimal number of dimensionality reduction components (e.g., PCA/Autoencoder components) per user.

The problem is formulated as a classification over **16 discrete classes**, mapping to viable transmission configurations: `components ∈ {5, 10, 15, ..., 80}`. The system utilises a **single unified Transformer model** capable of handling dynamic admission up to $N_{max} = 10$ concurrent users.

### Why Transformer?
In a shared 5G medium, one user's high data rate or poor channel quality directly impacts available resources and latency for all other users. The **self-attention mechanism** explicitly models these inter-user dependencies, which a standard MLP (processing a flat, concatenated feature vector) cannot naturally capture.

---

## 2. Neural Network Architecture (`MultiUserCompressionNet`)

The model treats each user's feature vector as a **token** in a sequence of length $N_{max}$. Self-attention learns pairwise inter-user interference patterns, while a shared classification head produces per-user predictions.

### Input Representation
- **Per-user features** (5 dimensions): `[error_at_80, error_ratio, cqi, frame_rate, prev_delay_ms]`
- **Full input tensor**: `(B, 5 × N_{max})` — interleaved and zero-padded for inactive user slots.
- **User mask**: `(B, N_{max})` — `1.0` for active users, `0.0` for padding. Converted to `src_key_padding_mask` for the Transformer.

### Architecture Layers
1. **Feature Projection**: `Linear(5, d_model=32)` — lifts each user's raw 5-dim features into the model dimensionality.
2. **Positional Embedding**: Learnable `(1, N_max, d_model)` parameter added to tokens so the model can distinguish user slot positions.
3. **Transformer Encoder**: `nn.TransformerEncoder` with:
   - `num_layers = 2`
   - `nhead = 4` (each head attends to $d_{model}/n_{head} = 8$ dimensions)
   - `dim_feedforward = 64`
   - `dropout = 0.1`
   - `activation = GELU`
   - `batch_first = True`
   - Padding mask ensures attention is **not computed** over inactive (zero-padded) user slots.
4. **Classification Head** (shared across all users):
   - `LayerNorm(d_model)` → `Linear(d_model, 16)`
   - Applied independently to each user token, producing `(B, N_{max}, 16)` logits, unbundled into a list of `N_{max}` tensors of shape `(B, 16)`.

---

## 3. Training Paradigm & Specific Enhancements

### A. Non-Contradictory Optimal Targets (Label Unification)
The simulation data is a grid-search log where the same state maps to many different `k` values. Grouping via macroscopic bins (`avg_cqi_bin`, `avg_fps_bin`, `avg_delay_bin`, etc.) and selecting the oracle-optimal configuration (`idxmin` on total cost) yields one clean label per unique state.

### B. Custom Cost Mechanism
```
total_cost = total_error_scaled + penalty_weight × (avg_comps_scaled²)
penalty_weight = 0.25 × max(0, num_users − 2)
```
Discourages over-allocating components at higher user densities.

### C. Gaussian State Augmentation
Inside `CompressionDataset`, Gaussian noise (`augment_std = 0.2`) is added to inputs each batch to expand the effective training set from ~130 unique states.

### D. Ordinal Soft Labels & Masked KL-Divergence
`make_soft_labels()` converts integer targets into Gaussian probability distributions (`std=1.5`) over the 16 classes. KL-Divergence loss naturally penalises distant mis-predictions more than adjacent ones. The loss is **masked** so that gradients from padded user slots are zeroed out.

---

## 4. Pipeline Execution

The primary entry point `train_all` controls the flow:
1. **Pre-processing**: Loads `datasets/pca/dataset.csv`.
2. **Data Amalgamation & Padding**: Loops from 2–10 users, zero-padding to $N_{max} = 10$.
3. **Splitting & Scaling**: 80/20 train/test split. `StandardScaler` fitted per-column on non-zero values; zeros (padding) remain zero.
4. **Training**: `Adam` (weight decay $10^{-4}$) + `CosineAnnealingLR` over 300 epochs.
5. **Evaluation**: Exact match, ±5 components (±1 class), ±15 components (±3 classes).
6. **Persistence**: Saves `compression_unified.pth` + `compression_unified_scaler.pkl` to `./models/`.
