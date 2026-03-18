# %%
# # Two-Stage Neural Network for Dynamic Adaptive Compression

# **Problem:** At each TTI, choose the optimal compression level (components ∈ {25, 50, …, 400}) for each user to minimize effective error (QoE).

# **Two-Stage Approach:**

# | | Stage 1: Error Predictor | Stage 2: Direct Selector |
# |---|---|---|
# | **Task** | Regression: predict effective error | Classification: output optimal compression level |
# | **Input** | All users' features **including** components | All users' features **excluding** components |
# | **Output** | Predicted error per user (continuous) | Optimal compression class per user (16 classes) |
# | **Training data** | Real dataset | Synthetic labels from Stage 1 sweeps |
# | **Inference** | Only used offline for label generation | **Single forward pass** at runtime |

# **Result:** ~500× faster inference — one forward pass instead of coordinate descent with hundreds of passes.

# %%
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, TensorDataset, random_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, top_k_accuracy_score
import matplotlib.pyplot as plt
import os, json, copy, pickle, time

# ── Configuration ──────────────────────────────────────────────
import argparse
parser = argparse.ArgumentParser(description="Train stage-two compression models")
parser.add_argument("--mode", choices=["pca", "ae"], default="pca",
                    help="Use PCA or AE dataset/model directories")
args = parser.parse_args()
MODE = args.mode

DATASET_PATH    = f"datasets_{MODE}/random_cl_dataset_clean.csv"
# Stage 1 models directory should match stage_one_model output
STAGE1_DIR      = f"stage_one_models_{MODE}"
STAGE2_DIR      = f"stage_two_models_{MODE}"
os.makedirs(STAGE2_DIR, exist_ok=True)

# ── Fine compression levels (used for Stage 1 sweep) ─────────
if MODE == "pca":
    COMP_LEVELS_FINE = list(range(5, 81, 5))    # 16 fine levels (matches training data)
    BIN_SIZE = 1                                # each CL is its own class
else:
    COMP_LEVELS_FINE = list(range(4, 373, 16))  # 24 fine levels
    BIN_SIZE = 4

NUM_FINE_LEVELS = len(COMP_LEVELS_FINE)
NUM_BINS        = NUM_FINE_LEVELS // BIN_SIZE

# Representative CL for each bin (centre element of each group)
# e.g. PCA bins: [15, 40, 65, 90, 115, 140, 165, 190]
COMP_LEVELS = [
    COMP_LEVELS_FINE[i * BIN_SIZE + BIN_SIZE // 2]
    for i in range(NUM_BINS)
]
COMP_TO_IDX     = {c: i for i, c in enumerate(COMP_LEVELS)}
NUM_COMP_LEVELS = NUM_BINS   # Stage 2 outputs this many classes

CQI_MIN, CQI_MAX = 3, 15
CQI_VOCAB_SIZE  = CQI_MAX - CQI_MIN + 1     # 13
CQI_EMBED_DIM   = 4

# Stage 1 config (must match model.ipynb)
S1_HIDDEN       = [256, 128, 64]
S1_CONT_FEATS   = ['meantrafficsize', 'frameComplexity', 'frame_rate', 'components']
NUM_S1_CONT     = len(S1_CONT_FEATS)

# Stage 2 config
STATIC_FEATS     = ['meantrafficsize', 'frameComplexity', 'frame_rate']
NUM_STATIC_FEATS = len(STATIC_FEATS)
S2_HIDDEN       = [256, 128]
S2_BATCH        = 256
S2_LR           = 1e-3
S2_EPOCHS       = 200
S2_PATIENCE     = 20

# Loss-aware label generation: penalise high CLs to account for
# unmodeled packet-loss at high compression levels.  The training data
# only contains *received* frames so Stage 1 never learned about the
# penalty incurred when large frames miss the deadline or are lost.
# Calibrated so the label distribution peaks around CL 50-90 (the
# static-comparison sweet-spot) rather than maxing out at CL 200.
LOSS_PENALTY_WEIGHT = 0.0       # disabled — let Stage 1 predictions determine labels directly

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {DEVICE}")
print(f"Mode: {MODE}")
print(f"Fine CLs ({NUM_FINE_LEVELS}): {COMP_LEVELS_FINE}")
print(f"Bins ({NUM_BINS}): {COMP_LEVELS}")
print(f"Stage 1 models: {STAGE1_DIR}/")
print(f"Stage 2 output: {STAGE2_DIR}/")

# %% [markdown]
# ## 1. Load Data & Stage 1 Models
# 
# Load the dataset and the pre-trained Stage 1 error predictor models from `model.ipynb`.

# %%
# ── Stage 1 model definition (must match model.ipynb) ─────────
class CompressionPredictor(nn.Module):
    """Stage 1: predicts log(1+effectiveError) for each user."""
    def __init__(self, num_users, cqi_vocab=CQI_VOCAB_SIZE,
                 cqi_dim=CQI_EMBED_DIM, hidden=None):
        super().__init__()
        if hidden is None:
            hidden = S1_HIDDEN
        self.num_users = num_users
        self.cqi_embed = nn.Embedding(cqi_vocab, cqi_dim)
        per_user = NUM_S1_CONT + cqi_dim   # 4 + 4 = 8
        in_dim   = num_users * per_user
        layers = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h),
                       nn.ReLU(), nn.Dropout(0.1)]
            prev = h
        layers.append(nn.Linear(prev, num_users))
        self.net = nn.Sequential(*layers)

    def forward(self, x_cont, x_cqi):
        cqi_emb = self.cqi_embed(x_cqi)
        x = torch.cat([x_cont, cqi_emb], dim=-1)
        x = x.view(x.size(0), -1)
        return self.net(x)


# ── Load dataset ──────────────────────────────────────────────
df = pd.read_csv(DATASET_PATH)
print(f"Dataset: {df.shape[0]} rows, {df.shape[1]} columns")
print(f"User configs: {sorted(df['num_users'].unique())}")

# ── Load global scaler ────────────────────────────────────────
with open(os.path.join(STAGE1_DIR, 'global_scaler.pkl'), 'rb') as f:
    global_scaler = pickle.load(f)
print(f"Scaler loaded — means: {global_scaler.mean_}")

# ── Load all 9 Stage 1 models ────────────────────────────────
s1_models = {}
for n_u in range(2, 11):
    model = CompressionPredictor(n_u).to(DEVICE)
    path = os.path.join(STAGE1_DIR, f'model_{n_u}users.pt')
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.eval()
    s1_models[n_u] = model
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Loaded {n_u}-user model ({n_params:,} params)")

print(f"\n✓ All 9 Stage 1 models loaded.")

# %%
def extract_static_features(df, num_users):
    """Extract per-user static features (no components), CQI indices, original comp, and actual errors."""
    subset = df[df['num_users'] == num_users].reset_index(drop=True)
    n = len(subset)

    static_cont = np.zeros((n, num_users, NUM_STATIC_FEATS), dtype=np.float32)
    cqi_idx     = np.zeros((n, num_users), dtype=np.int64)
    orig_comp   = np.zeros((n, num_users), dtype=np.int64)
    actual_err  = np.zeros((n, num_users), dtype=np.float32)

    for u in range(num_users):
        for j, feat in enumerate(STATIC_FEATS):
            static_cont[:, u, j] = subset[f'user{u}_{feat}'].values
        cqi_idx[:, u]  = subset[f'user{u}_cqi'].values.astype(int) - CQI_MIN
        orig_comp[:, u] = subset[f'user{u}_components'].values.astype(int)
        actual_err[:, u] = subset[f'user{u}_effectiveError'].values

    return static_cont, cqi_idx, orig_comp, actual_err

# %% [markdown]
# ## 2. Generate Labels via Binned Stage 1 Sweep
#
# For each sample and each user:
# 1. Sweep all fine compression levels through Stage 1.
# 2. Add a quadratic loss penalty proportional to (CL / max_CL)^2 to each prediction.
#    This compensates for the unmodeled packet-loss / deadline-miss
#    at high CLs (Stage 1 was trained only on received frames).
# 3. Average the penalised error within each of the 8 bins.
# 4. Select the bin with the lowest average penalised error as the label.
#
# Reducing 40 fine CLs down to 8 bins makes the classification
# problem tractable (the previous 40-class accuracy was ~25%).

# %%
@torch.no_grad()
def _predict_batch(s1_model, static_cont, comp_col, cqi_idx, scaler,
                   batch_size=512):
    """Predict effective error for given static features + CL assignment."""
    n = static_cont.shape[0]
    x_full = np.concatenate([static_cont, comp_col[:, :, None]], axis=-1)
    shape = x_full.shape
    x_scaled = scaler.transform(
        x_full.reshape(-1, NUM_S1_CONT)).reshape(shape)

    preds = np.zeros((n, static_cont.shape[1]), dtype=np.float32)
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        xc  = torch.tensor(
            x_scaled[start:end], dtype=torch.float32).to(DEVICE)
        xcq = torch.tensor(
            cqi_idx[start:end], dtype=torch.long).to(DEVICE)
        preds[start:end] = s1_model(xc, xcq).cpu().numpy()
    return preds  # (n, N)


@torch.no_grad()
def generate_labels(s1_model, static_cont, cqi_idx, orig_comp, scaler,
                    batch_size=512, max_rounds=3):
    """
    Coordinate-descent label generation.

    For each user in turn, sweep their CL while holding all other users
    at their current-best CL.  Pick the CL that minimises the **total**
    predicted error (sum across all users).  Repeat for `max_rounds`.

    This keeps Stage-1 inputs close to the training distribution (only
    one user changes at a time) and captures cross-user congestion.

    Returns
    -------
    opt_labels : (n, N) int                   — optimal CL index per user
    all_errors : (n, N, NUM_FINE_LEVELS)      — per-user error at each CL
                                                (from the final round)
    """
    s1_model.eval()
    n, N, _ = static_cont.shape
    F = NUM_FINE_LEVELS
    cl_vals = np.array(COMP_LEVELS_FINE, dtype=np.float32)

    # Map each CL value → index (for orig_comp init)
    cl_to_idx = {int(c): i for i, c in enumerate(COMP_LEVELS_FINE)}

    # ── Initialise from training-data CLs (clipped to valid set) ──
    current_cl  = np.zeros((n, N), dtype=np.float32)
    current_idx = np.zeros((n, N), dtype=np.int64)
    for u in range(N):
        for i in range(n):
            raw = int(orig_comp[i, u])
            # snap to nearest valid CL
            idx = int(np.argmin(np.abs(cl_vals - raw)))
            current_idx[i, u] = idx
            current_cl[i, u]  = cl_vals[idx]

    # ── Coordinate descent ────────────────────────────────────
    for rnd in range(max_rounds):
        changed = False
        for u in range(N):
            best_total = np.full(n, float('inf'), dtype=np.float32)
            best_ci    = current_idx[:, u].copy()

            for ci, comp_val in enumerate(COMP_LEVELS_FINE):
                comp_col = current_cl.copy()          # (n, N)
                comp_col[:, u] = comp_val             # only change user u

                preds = _predict_batch(
                    s1_model, static_cont, comp_col,
                    cqi_idx, scaler, batch_size)      # (n, N)
                total_err = preds.sum(axis=1)         # (n,)

                improved = total_err < best_total
                best_total = np.where(improved, total_err, best_total)
                best_ci    = np.where(improved, ci, best_ci)

            new_cl = cl_vals[best_ci]
            if not np.array_equal(new_cl, current_cl[:, u]):
                changed = True
            current_idx[:, u] = best_ci
            current_cl[:, u]  = new_cl

        print(f"    CD round {rnd+1}: changed={changed}")
        if not changed:
            break

    # ── Build per-user per-CL error surface (for evaluation) ──
    all_errors = np.zeros((n, N, F), dtype=np.float32)
    for ci, comp_val in enumerate(COMP_LEVELS_FINE):
        comp_col = current_cl.copy()
        for u in range(N):
            comp_col_u = current_cl.copy()
            comp_col_u[:, u] = comp_val
            preds = _predict_batch(
                s1_model, static_cont, comp_col_u,
                cqi_idx, scaler, batch_size)
            all_errors[:, u, ci] = preds[:, u]

    # With BIN_SIZE=1, bins == fine levels
    opt_labels = current_idx
    return opt_labels, all_errors

# %%
# ── Generate labels for all 9 configurations ─────────────────
label_data = {}  # n_u -> (static_cont, cqi_idx, opt_labels, all_errors, orig_comp, actual_err)

for n_u in range(2, 11):
    sc, cq, oc, ae = extract_static_features(df, n_u)
    print(f"\nnum_users={n_u}")
    opt_labels, all_errors = generate_labels(
        s1_models[n_u], sc, cq, oc, global_scaler)
    label_data[n_u] = (sc, cq, opt_labels, all_errors, oc, ae)

    opt_comp_vals = np.array(COMP_LEVELS)[opt_labels]
    print(f"  samples={len(sc):>5d}  "
          f"label distribution: {dict(zip(*np.unique(opt_labels, return_counts=True)))}")

print("\n✓ Labels generated for all configurations.")

# %%
# ── Visualise label distribution ───────────────────────────────
fig, axes = plt.subplots(3, 3, figsize=(14, 10))
for idx, n_u in enumerate(range(2, 11)):
    ax = axes[idx // 3][idx % 3]
    _, _, opt_labels, _, _, _ = label_data[n_u]
    all_labels = opt_labels.flatten()
    ax.bar(range(NUM_COMP_LEVELS),
           [np.sum(all_labels == i) for i in range(NUM_COMP_LEVELS)],
           tick_label=[str(c) for c in COMP_LEVELS], color='steelblue', edgecolor='k')
    ax.set_title(f'{n_u} users')
    ax.set_xlabel('components')
    ax.set_ylabel('count')
    ax.tick_params(axis='x', rotation=45, labelsize=7)
plt.suptitle('Optimal Compression Label Distribution (from Stage 1)', fontsize=14)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 3. Stage 2: Direct Selector (Classifier)
# 
# Architecture:
# - **Input per user (4 continuous):** `meantrafficsize`, `stdtrafficsize`, `frameComplexity`, `frame_rate` — NO compression level
# - **CQI Embedding:** same 11-bin → 4-dim as Stage 1
# - All users concatenated → captures cross-user dependencies
# - **Hidden:** `[256 → 128]` with BatchNorm, ReLU, Dropout
# - **Output:** `N × 16` logits — one 16-class classification head per user
# 
# Loss: Cross-entropy (with optional label smoothing to handle slight Stage 1 uncertainty)

# %%
class CompressionSelector(nn.Module):
    """
    Stage 2: directly outputs optimal compression class per user.

    Inputs
    ------
    x_cont : (B, N, 3)  – normalised [meantrafficsize,
                           frameComplexity, frame_rate]
    x_cqi  : (B, N)     – CQI index (0-10)

    Output
    ------
    (B, N, 16) – logits over 16 compression classes per user
    """

    def __init__(self, num_users, cqi_vocab=CQI_VOCAB_SIZE,
                 cqi_dim=CQI_EMBED_DIM, hidden=None):
        super().__init__()
        if hidden is None:
            hidden = S2_HIDDEN
        self.num_users = num_users
        self.cqi_embed = nn.Embedding(cqi_vocab, cqi_dim)

        per_user = NUM_STATIC_FEATS + cqi_dim  # 3 + 4 = 7  (no components!)
        in_dim   = num_users * per_user

        layers = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h),
                       nn.ReLU(), nn.Dropout(0.15)]
            prev = h
        layers.append(nn.Linear(prev, num_users * NUM_COMP_LEVELS))
        self.net = nn.Sequential(*layers)

    def forward(self, x_cont, x_cqi):
        cqi_emb = self.cqi_embed(x_cqi)                         # (B, N, 4)
        x = torch.cat([x_cont, cqi_emb], dim=-1)                # (B, N, 8)
        x = x.view(x.size(0), -1)                               # (B, N*8)
        logits = self.net(x)                                     # (B, N*C)
        return logits.view(-1, self.num_users, NUM_COMP_LEVELS)  # (B, N, C)


# Quick shape check
_m2 = CompressionSelector(num_users=5).to(DEVICE)
_x2 = torch.randn(2, 5, NUM_STATIC_FEATS).to(DEVICE)
_c2 = torch.randint(0, CQI_VOCAB_SIZE, (2, 5)).to(DEVICE)
print(f"Stage 2 output shape: {_m2(_x2, _c2).shape}")  # (2, 5, 16)
print(f"Parameters (5-user selector): {sum(p.numel() for p in _m2.parameters()):,}")

# %% [markdown]
# ## 4. Prepare Stage 2 Datasets & Training

# %%
# ── Build a scaler for the 4 static features (no components) ──
all_static = []
for n_u in range(2, 11):
    sc, _, _, _, _, _ = label_data[n_u]
    all_static.append(sc.reshape(-1, NUM_STATIC_FEATS))

static_scaler = StandardScaler().fit(np.concatenate(all_static, axis=0))
print(f"Static scaler fitted — means: {static_scaler.mean_}, stds: {static_scaler.scale_}")


# ── Build per-config datasets ─────────────────────────────────
class SelectorDataset(Dataset):
    """Dataset for Stage 2 classifier."""
    def __init__(self, static_cont, cqi_idx, opt_labels, scaler):
        shape = static_cont.shape
        scaled = scaler.transform(static_cont.reshape(-1, NUM_STATIC_FEATS)).reshape(shape)
        self.X_cont = torch.tensor(scaled, dtype=torch.float32)
        self.X_cqi  = torch.tensor(cqi_idx, dtype=torch.long)
        self.y      = torch.tensor(opt_labels, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X_cont[idx], self.X_cqi[idx], self.y[idx]


s2_datasets = {}  # n_u -> (train, val, test)
for n_u in range(2, 11):
    sc, cq, ol, _, _, _ = label_data[n_u]
    ds = SelectorDataset(sc, cq, ol, static_scaler)

    n_total = len(ds)
    n_test  = int(0.10 * n_total)
    n_val   = int(0.10 * n_total)
    n_train = n_total - n_val - n_test

    train_ds, val_ds, test_ds = random_split(
        ds, [n_train, n_val, n_test],
        generator=torch.Generator().manual_seed(42)
    )
    s2_datasets[n_u] = (train_ds, val_ds, test_ds)
    print(f"num_users={n_u:>2d}  train={n_train}, val={n_val}, test={n_test}")

# %%
def train_selector(num_users, train_ds, val_ds,
                   epochs=S2_EPOCHS, patience=S2_PATIENCE):
    """Train a CompressionSelector for a given user count."""
    train_dl = DataLoader(train_ds, batch_size=S2_BATCH, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=S2_BATCH)

    model = CompressionSelector(num_users).to(DEVICE)
    opt   = torch.optim.Adam(model.parameters(), lr=S2_LR)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=8, factor=0.5)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)

    best_val, best_state, wait = float('inf'), None, 0
    history = {'train_loss': [], 'val_loss': [], 'val_acc': []}

    for ep in range(1, epochs + 1):
        # ── Train ──
        model.train()
        t_loss = 0.0
        for xc, xcqi, yt in train_dl:
            xc, xcqi, yt = xc.to(DEVICE), xcqi.to(DEVICE), yt.to(DEVICE)
            logits = model(xc, xcqi)               # (B, N, 16)
            # Reshape for cross-entropy: (B*N, 16) vs (B*N,)
            loss = loss_fn(logits.reshape(-1, NUM_COMP_LEVELS), yt.reshape(-1))
            opt.zero_grad(); loss.backward(); opt.step()
            t_loss += loss.item() * xc.size(0)
        t_loss /= len(train_ds)

        # ── Validate ──
        model.eval()
        v_loss, correct, total = 0.0, 0, 0
        with torch.no_grad():
            for xc, xcqi, yt in val_dl:
                xc, xcqi, yt = xc.to(DEVICE), xcqi.to(DEVICE), yt.to(DEVICE)
                logits = model(xc, xcqi)
                v_loss += loss_fn(logits.reshape(-1, NUM_COMP_LEVELS),
                                  yt.reshape(-1)).item() * xc.size(0)
                preds = logits.argmax(dim=-1)      # (B, N)
                correct += (preds == yt).sum().item()
                total   += yt.numel()
        v_loss /= len(val_ds)
        v_acc = correct / total
        sched.step(v_loss)

        history['train_loss'].append(t_loss)
        history['val_loss'].append(v_loss)
        history['val_acc'].append(v_acc)

        if v_loss < best_val:
            best_val = v_loss
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                print(f"  Early stop at epoch {ep}")
                break

        if ep % 25 == 0 or ep == 1:
            print(f"  Epoch {ep:>3d}  train_loss={t_loss:.4f}  val_loss={v_loss:.4f}  "
                  f"val_acc={v_acc:.3f}  lr={opt.param_groups[0]['lr']:.1e}")

    model.load_state_dict(best_state)
    return model, history

# %%
# ── Train all 9 Stage 2 models ────────────────────────────────
s2_models    = {}
s2_histories = {}

for n_u in range(2, 11):
    print(f"\n{'='*55}")
    print(f"Training Stage 2 selector for num_users = {n_u}")
    print(f"{'='*55}")
    train_ds, val_ds, test_ds = s2_datasets[n_u]
    model, hist = train_selector(n_u, train_ds, val_ds)
    s2_models[n_u]    = model
    s2_histories[n_u] = hist
    print(f"  Best val loss: {min(hist['val_loss']):.4f}  "
          f"Best val acc: {max(hist['val_acc']):.3f}")

print("\n✓ All 9 Stage 2 models trained.")

# %% [markdown]
# ## 5. Evaluation
# 
# Metrics:
# 1. **Selection accuracy** — does Stage 2 pick the same compression as the Stage 1 oracle?
# 2. **Top-3 accuracy** — is the oracle's choice in Stage 2's top 3 predictions?
# 3. **QoE comparison** — compare predicted effective error of Stage 2's choice vs Stage 1 oracle vs random
# 4. **Inference speed** — Stage 2 single pass vs Stage 1 coordinate descent

# %%
@torch.no_grad()
def evaluate_selector(s2_model, s1_model, test_ds, static_cont_all, cqi_all,
                      all_errors_all, scaler_s1, scaler_s2):
    """
    Evaluate Stage 2 on test set. Returns dict of metrics.
    """
    s2_model.eval(); s1_model.eval()
    dl = DataLoader(test_ds, batch_size=512)
    all_preds, all_labels = [], []

    for xc, xcqi, yt in dl:
        xc, xcqi = xc.to(DEVICE), xcqi.to(DEVICE)
        logits = s2_model(xc, xcqi)         # (B, N, 16)
        all_preds.append(logits.cpu())
        all_labels.append(yt)

    all_preds  = torch.cat(all_preds)       # (T, N, 16)
    all_labels = torch.cat(all_labels)      # (T, N)
    pred_cls   = all_preds.argmax(dim=-1)   # (T, N)

    T, N = all_labels.shape

    # ── Accuracy metrics ──
    flat_preds  = pred_cls.numpy().flatten()
    flat_labels = all_labels.numpy().flatten()
    acc_top1 = accuracy_score(flat_labels, flat_preds)

    # Top-3 accuracy
    flat_probs = F.softmax(all_preds, dim=-1).numpy().reshape(-1, NUM_COMP_LEVELS)
    acc_top3 = top_k_accuracy_score(flat_labels, flat_probs, k=3,
                                     labels=list(range(NUM_COMP_LEVELS)))

    # ── QoE comparison using Stage 1 error surface ──
    # Get test set indices
    test_indices = test_ds.indices if hasattr(test_ds, 'indices') else list(range(len(test_ds)))

    # S1 oracle errors (at optimal compression)
    oracle_labels = all_labels.numpy()                             # (T, N)
    s2_labels     = pred_cls.numpy()                               # (T, N)

    oracle_errors = np.zeros((T, N))
    s2_errors     = np.zeros((T, N))
    random_errors = np.zeros((T, N))

    for i, tidx in enumerate(test_indices):
        for u in range(N):
            oracle_errors[i, u] = all_errors_all[tidx, u, oracle_labels[i, u]]
            s2_errors[i, u]     = all_errors_all[tidx, u, s2_labels[i, u]]
            random_errors[i, u] = all_errors_all[tidx, u, np.random.randint(NUM_COMP_LEVELS)]

    return {
        'top1_acc': acc_top1,
        'top3_acc': acc_top3,
        'oracle_err_mean': oracle_errors.mean(),
        's2_err_mean': s2_errors.mean(),
        'random_err_mean': random_errors.mean(),
        'oracle_err_per_sample': oracle_errors.sum(axis=1),  # sum across users
        's2_err_per_sample': s2_errors.sum(axis=1),
    }


# ── Evaluate all configs ──────────────────────────────────────
eval_results = {}
print(f"{'Config':>8s}  {'Top-1':>6s}  {'Top-3':>6s}  {'Oracle err':>10s}  "
      f"{'S2 err':>10s}  {'Random err':>10s}  {'S2/Oracle':>9s}")
print("-" * 75)

# time consuming part so commenting out for now — will run after demo section
for n_u in range(2, 11):
    _, _, test_ds = s2_datasets[n_u]
    sc, cq, ol, ae, oc, actual = label_data[n_u]
    res = evaluate_selector(
        s2_models[n_u], s1_models[n_u], test_ds,
        sc, cq, ae, global_scaler, static_scaler
    )
    eval_results[n_u] = res
    ratio = res['s2_err_mean'] / res['oracle_err_mean']
    print(f"{n_u:>8d}  {res['top1_acc']:>6.1%}  {res['top3_acc']:>6.1%}  "
          f"{res['oracle_err_mean']:>10.2f}  {res['s2_err_mean']:>10.2f}  "
          f"{res['random_err_mean']:>10.2f}  {ratio:>9.2f}×")

# %%
# ── Training curves ───────────────────────────────────────────
fig, axes = plt.subplots(3, 3, figsize=(14, 10))
for idx, n_u in enumerate(range(2, 11)):
    ax = axes[idx // 3][idx % 3]
    h = s2_histories[n_u]
    ax.plot(h['train_loss'], label='train loss')
    ax.plot(h['val_loss'],   label='val loss')
    ax2 = ax.twinx()
    ax2.plot(h['val_acc'], color='green', alpha=0.6, label='val acc')
    ax2.set_ylim(0, 1)
    ax.set_title(f'{n_u} users')
    ax.set_xlabel('epoch')
    ax.set_ylabel('loss')
    ax2.set_ylabel('accuracy', color='green')
    if idx == 0:
        ax.legend(loc='upper right', fontsize=7)
plt.suptitle('Stage 2 — Training Loss & Validation Accuracy', fontsize=14)
plt.tight_layout()
plt.show()

# ── QoE comparison bar chart ──────────────────────────────────
configs = list(range(2, 11))
oracle_errs = [eval_results[n]['oracle_err_mean'] for n in configs]
s2_errs     = [eval_results[n]['s2_err_mean'] for n in configs]
random_errs = [eval_results[n]['random_err_mean'] for n in configs]

x = np.arange(len(configs))
w = 0.25
fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(x - w, oracle_errs, w, label='Stage 1 Oracle (optimal)', color='green', edgecolor='k')
ax.bar(x,     s2_errs,     w, label='Stage 2 Selector',         color='steelblue', edgecolor='k')
ax.bar(x + w, random_errs, w, label='Random',                   color='salmon', edgecolor='k')
ax.set_xticks(x)
ax.set_xticklabels([f'{n} users' for n in configs])
ax.set_ylabel('Mean Predicted Effective Error')
ax.set_title('QoE Comparison: Oracle vs Stage 2 vs Random')
ax.legend()
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 6. Inference Speed Benchmark
# 
# Compare latency of:
# 1. **Stage 2:** Single forward pass → prediction
# 2. **Stage 1 + Coordinate Descent:** Multiple forward passes to sweep compression levels

# %%
@torch.no_grad()
def benchmark_inference(n_u, n_iters=500):
    """Benchmark single-sample latency for both approaches."""
    s1 = s1_models[n_u]; s1.eval()
    s2 = s2_models[n_u]; s2.eval()

    # Dummy single-sample inputs
    xc_s1 = torch.randn(1, n_u, NUM_S1_CONT).to(DEVICE)
    xq_s1 = torch.randint(0, CQI_VOCAB_SIZE, (1, n_u)).to(DEVICE)
    xc_s2 = torch.randn(1, n_u, NUM_STATIC_FEATS).to(DEVICE)
    xq_s2 = torch.randint(0, CQI_VOCAB_SIZE, (1, n_u)).to(DEVICE)

    # Warm up
    for _ in range(50):
        s2(xc_s2, xq_s2)
        s1(xc_s1, xq_s1)
    if DEVICE.type == 'cuda':
        torch.cuda.synchronize()

    # ── Stage 2: single forward pass ──
    t0 = time.perf_counter()
    for _ in range(n_iters):
        logits = s2(xc_s2, xq_s2)
        _ = logits.argmax(dim=-1)
    if DEVICE.type == 'cuda':
        torch.cuda.synchronize()
    s2_time = (time.perf_counter() - t0) / n_iters * 1e6  # μs

    # ── Stage 1 + sweep (16 levels per user, 3 rounds coord descent) ──
    n_rounds = 3
    t0 = time.perf_counter()
    for _ in range(n_iters):
        for rnd in range(n_rounds):
            for u in range(n_u):
                for ci in range(NUM_COMP_LEVELS):
                    _ = s1(xc_s1, xq_s1)
    if DEVICE.type == 'cuda':
        torch.cuda.synchronize()
    s1_time = (time.perf_counter() - t0) / n_iters * 1e6  # μs

    fwd_passes_s1 = n_rounds * n_u * NUM_COMP_LEVELS
    return s2_time, s1_time, fwd_passes_s1


# print(f"{'Config':>8s}  {'S2 (μs)':>10s}  {'S1+CD (μs)':>12s}  {'S1 fwd passes':>14s}  {'Speedup':>8s}")
# print("-" * 65)
# for n_u in range(2, 11):
#     s2_t, s1_t, fwd = benchmark_inference(n_u, n_iters=300)
#     print(f"{n_u:>8d}  {s2_t:>10.1f}  {s1_t:>12.1f}  {fwd:>14d}  {s1_t/s2_t:>8.0f}×")

# %% [markdown]
# ## 7. Demo: Single-TTI Inference
# 
# Show how Stage 2 is used at runtime — a single forward pass to get compression levels for all users.

# %%
@torch.no_grad()
def predict_compression(s2_model, user_features, user_cqi, scaler):
    """
    Single-pass inference: get optimal compression for all users.

    Parameters
    ----------
    s2_model      : trained CompressionSelector
    user_features : (N, 4) array — [meantrafficsize, stdtrafficsize,
                    frameComplexity, frame_rate]
    user_cqi      : (N,) int array — CQI indices (0-based, i.e., raw CQI - CQI_MIN)
    scaler        : fitted StandardScaler for static features

    Returns
    -------
    comp_levels   : list[int] — chosen compression level per user
    probs         : (N, 16) — softmax probabilities per user
    """
    s2_model.eval()
    N = s2_model.num_users
    scaled = scaler.transform(user_features.reshape(-1, NUM_STATIC_FEATS)).reshape(1, N, NUM_STATIC_FEATS)
    xc  = torch.tensor(scaled, dtype=torch.float32).to(DEVICE)
    xcq = torch.tensor(user_cqi.reshape(1, N), dtype=torch.long).to(DEVICE)

    logits = s2_model(xc, xcq)                          # (1, N, 16)
    probs  = F.softmax(logits, dim=-1)[0].cpu().numpy()  # (N, 16)
    pred_idx = logits[0].argmax(dim=-1).cpu().numpy()     # (N,)
    comp = [COMP_LEVELS[i] for i in pred_idx]
    return comp, probs


# ── Demo with a test sample ──────────────────────────────────
demo_n_u = 5
sc, cq, ol, ae, oc, actual_err = label_data[demo_n_u]
_, _, test_ds = s2_datasets[demo_n_u]
sample_idx = test_ds.indices[0]

# Raw features for this sample
user_feats = sc[sample_idx]     # (N, 4)
user_cqi   = cq[sample_idx]    # (N,)
oracle_lbl = ol[sample_idx]    # (N,)
orig_comp  = oc[sample_idx]    # (N,) — what was actually used in simulation

comp_pred, probs = predict_compression(s2_models[demo_n_u], user_feats, user_cqi, static_scaler)

print(f"{'User':>6s}  {'CQI':>4s}  {'FPS':>4s}  {'Sim comp':>8s}  {'Oracle':>6s}  {'Stage2':>6s}  "
      f"{'Oracle err':>10s}  {'S2 err':>10s}  {'Sim err':>10s}")
print("-" * 90)
for u in range(demo_n_u):
    o_err = ae[sample_idx, u, oracle_lbl[u]]
    s2_err = ae[sample_idx, u, COMP_TO_IDX[comp_pred[u]]]
    sim_err = actual_err[sample_idx, u]
    print(f"{u:>6d}  {user_cqi[u]+CQI_MIN:>4d}  {user_feats[u, 3]:>4.0f}  {orig_comp[u]:>8d}  "
          f"{COMP_LEVELS[oracle_lbl[u]]:>6d}  {comp_pred[u]:>6d}  "
          f"{o_err:>10.2f}  {s2_err:>10.2f}  {sim_err:>10.2f}")

# %% [markdown]
# ## 8. Save Stage 2 Models & Artifacts

# %%
# ── Save config ───────────────────────────────────────────────
s2_config = {
    'comp_levels': COMP_LEVELS,
    'cqi_min': CQI_MIN, 'cqi_max': CQI_MAX,
    'cqi_vocab_size': CQI_VOCAB_SIZE,
    'cqi_embed_dim': CQI_EMBED_DIM,
    'hidden_dims': S2_HIDDEN,
    'static_feat_names': STATIC_FEATS,
    'num_classes': NUM_COMP_LEVELS,
}
with open(os.path.join(STAGE2_DIR, 'config.json'), 'w') as f:
    json.dump(s2_config, f, indent=2)

# ── Save scaler ──────────────────────────────────────────────
with open(os.path.join(STAGE2_DIR, 'static_scaler.pkl'), 'wb') as f:
    pickle.dump(static_scaler, f)

# ── Save models + TorchScript ────────────────────────────────
for n_u in range(2, 11):
    model = s2_models[n_u]
    model.eval()

    # State dict
    torch.save(model.state_dict(),
               os.path.join(STAGE2_DIR, f'selector_{n_u}users.pt'))

    # TorchScript for C++ / fast inference
    dummy_xc  = torch.randn(1, n_u, NUM_STATIC_FEATS).to(DEVICE)
    dummy_cqi = torch.zeros(1, n_u, dtype=torch.long).to(DEVICE)
    scripted  = torch.jit.trace(model, (dummy_xc, dummy_cqi))
    scripted.save(os.path.join(STAGE2_DIR, f'selector_{n_u}users_scripted.pt'))

# ── Save evaluation summary ──────────────────────────────────
eval_summary = {}
for n_u in range(2, 11):
    r = eval_results[n_u]
    eval_summary[n_u] = {
        'top1_accuracy': float(r['top1_acc']),
        'top3_accuracy': float(r['top3_acc']),
        'oracle_mean_error': float(r['oracle_err_mean']),
        's2_mean_error': float(r['s2_err_mean']),
        'random_mean_error': float(r['random_err_mean']),
    }
with open(os.path.join(STAGE2_DIR, 'evaluation.json'), 'w') as f:
    json.dump(eval_summary, f, indent=2)

print(f"✓ Saved to {STAGE2_DIR}/")
print(f"  config.json, static_scaler.pkl, evaluation.json")
for n_u in range(2, 11):
    print(f"  selector_{n_u}users.pt  |  selector_{n_u}users_scripted.pt")


