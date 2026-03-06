# Model Architecture for Dynamic Adaptive Network-Aware Compression

## 1. System Overview & Problem Formulation
**Context:** In XR 360-degree video streaming over 5G networks, dynamic variations in channel conditions and video complexity cause fluctuations in user Quality of Experience (QoE). 
**Goal:** At each Transmission Time Interval (TTI), the network must assign an optimal compression level (defined as the number of PCA components) to every active user. The chosen configuration must minimize the total **effective error** (a metric combining visual distortion and network latency/loss) across all users.
**Compression Levels:** The system supports 16 discrete compression levels ranging from 25 to 400 components, at intervals of 25.

**The Challenge:** Due to shared radio resources, one user's heavy traffic load directly increases congestion and interference for other users. Thus, compression assignment cannot be evaluated independently per-user; it must be a joint optimization problem capturing cross-user dependencies.
**The Solution:** A **Two-Stage Neural Network Architecture**. 
* **Stage 1** acts as a computationally heavy, highly accurate regression oracle assessing the exact effective error of any given joint compression state.
* **Stage 2** acts as an ultra-fast classification network that learns to mimic Stage 1's optimal choices, outputting the correct compression classes for all users in a single forward pass, adhering to strict real-time TTI bounds.
* **Multi-Model Support:** Dedicated sub-models are trained for each active user count configuration (from 2 up to 10 users).

---

## 2. Stage 1: The Error Predictor (Regression Oracle)

### Objective
Accurately predict the raw effective error for each user given the complete multi-user state, which explicitly includes the tentatively assigned compression levels.

### Input Features
The model operates on a concatenated feature vector for all $N$ users simultaneously.
For each user, the following features are extracted:
* **Continuous Features (5 per user):**
  * `meantrafficsize`
  * `stdtrafficsize`
  * `frameComplexity`
  * `frame_rate`
  * `components` (The evaluated compression level: 25-400)
  * *Note:* Continuous features are standardized using a single `StandardScaler` fitted globally across all user configurations.
* **Discrete Features (1 per user):** 
  * `CQI` (Channel Quality Indicator): Integer ranging from 5 to 15 (vocabulary size of 11).

*Total normalized input dimension:* $N \times (5 \text{ continuous} + 4 \text{ CQI embed dims}) = N \times 9$.

### Architecture Details
1. **CQI Embedding:** A learnable `nn.Embedding(vocab_size=11, embed_dim=4)` layer translates the discrete network condition state into a dense 4D vector.
2. **Concatenation:** Embedded CQI and normalized continuous features from all users are flattened.
3. **MLP Backbone:** A fully-connected Multi-Layer Perceptron (MLP) with dimensions `[256, 128, 64]`.
4. **Regularization:** Each hidden layer operates with `nn.BatchNorm1d`, `nn.ReLU` activation, and `nn.Dropout(p=0.1)`.
5. **Output Layer:** A final linear projection layer yields exactly $N$ values—the continuous, predicted effective errors for each user under the evaluated multi-user compression assumptions.

### Training Details
* **Optimizer:** Adam (Initial LR = `1e-3`) with a `ReduceLROnPlateau` scheduler (factor = `0.5`, patience = `7`).
* **Loss Function:** `L1Loss` (Mean Absolute Error) targeting the original scale raw effective error.
* **Hyperparameters:** Batch size of `256`, `150` max epochs, early stopping patience of `15`. Train/Val/Test splits at `80/10/10`.

### Inference Strategy: Coordinate Descent
During simulation, the Stage 1 model utilizes a **Coordinate Descent** search algorithm to find the optimal joint compression state:
1. Initialize all users to the median level (e.g., 200 components).
2. Fix $N-1$ users, sweeping the 16 compression levels for the target user.
3. Run the $16 \times N \times 9$ input permutations through the Stage 1 model.
4. Select the specific level that minimizes the *sum* of predicted effective errors across *all* $N$ users.
5. Repeat for all users over `max_rounds=5` until convergence (typically stable within 2-3 rounds).

**Limitation:** While highly accurate, completing up to $O(\text{rounds} \times N \times 16)$ forward passes at every TTI breaks real-time latency requirements.

---

## 3. Stage 2: The Direct Selector (Real-Time Classifier)

### Objective
Eliminate the multi-pass offline search by predicting the optimal compression class directly. This stage translates knowledge from the Stage 1 regression model into an ultra-fast classification task.

### Label Generation (Knowledge Distillation)
Stage 2 relies on synthetic datasets labeled by the Stage 1 oracle. 
* For every observed sample state, the Stage 1 Coordinate Descent sweeper evaluates all level combinations and assigns the optimal compression level (as an index from `0` to `15`) that minimizes total multi-user error. 
* Stage 2 then uses this output index as its "ground truth" target.

### Input Features
The inputs are identical to Stage 1, **excluding** the `components` feature which is now the prediction target rather than an input assumption.
* **Continuous (4 per user):** `meantrafficsize`, `stdtrafficsize`, `frameComplexity`, `frame_rate`.
* **Discrete (1 per user):** `CQI` indices.

*Total normalized input dimension:* $N \times (4 \text{ continuous} + 4 \text{ CQI embed dims}) = N \times 8$.

### Architecture Details
1. **CQI Embedding:** Reuses the exact same configuration as Stage 1.
2. **MLP Backbone:** Trimmed dynamically for increased speed. Hidden dimensions: `[256, 128]`.
3. **Regularization:** Slightly increased dropout `nn.Dropout(p=0.15)` alongside BatchNorm and ReLU to prevent overfitting against the synthetic oracle targets.
4. **Classification Head:** Linear projection outputting dimension $N \times 16$, which maps to class logits representing the 16 possible compression levels for each user.

### Training Details
* **Loss Function:** `CrossEntropyLoss` with `label_smoothing=0.05`. Label smoothing mitigates hard-penalizations on ambiguous border cases where the Stage 1 oracle had a marginal error preference between two adjacent compression levels.
* **Optimizer:** Adam (Initial LR = `1e-3`) with `ReduceLROnPlateau` (factor = `0.5`, patience = `8`).
* **Hyperparameters:** Batch size of `256`, `200` max epochs, early stopping patience of `20`. 

### Evaluation & Inference Speedup
* **Accuracy:** Evaluated heavily on Top-1 and Top-3 accuracy against the Stage 1 oracle labeling.
* **QoE Preservation:** The overall effective error triggered by Stage 2 predictions tracks exceptionally close to the mathematically optimal baseline found in Stage 1, significantly outperforming random assignments.
* **Latency:** Executed via a **single forward pass**, Stage 2 achieves approximately a **~500x speedup** compared to Stage 1 CD inference. The sub-millisecond execution times make the model viable for real-time cellular scheduling blocks inside C++ NS3/Simu5G environments.

---

## 4. Production Artifacts & Environment Export
To bridge the gap between Python training and the C++ simulation environment, all required models and variables are decoupled and exported deterministically:
* **Configuration Matrices:** Saved manually to `config.json` defining bounded embedding structures, static feature names, and categorical target arrays.
* **Data Pipelines:** The globally-fitted Scikit-Learn `StandardScaler` arrays (`static_scaler.pkl`) are serialized directly, guaranteeing identically normalized streams at inference.
* **TorchScript Compilations:** Active networks (`model_Xusers.pt` & `selector_Xusers.pt`) are traced with static pseudo-tensors into TorchScript serialized formats (`_scripted.pt`). This isolates computation graphs directly readable by `libtorch` C++ bindings inside Simu5G.
