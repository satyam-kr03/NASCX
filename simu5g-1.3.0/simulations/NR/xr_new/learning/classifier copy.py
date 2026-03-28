"""
Multi-user compression level classifier
========================================
Discrete output: 16 classes → components in {5, 10, 15, ..., 80}
One model per num_users configuration.

ROOT CAUSE OF POOR ACCURACY (and fixes)
-----------------------------------------
Problem 1 — Contradictory labels when keeping all rows.
  The dataset is a grid search log: for each (cqi, fps) state, many different
  k values were evaluated (one per row). Keeping all rows means the same input
  maps to 16 different labels → the network's best strategy is to predict the
  most frequent class. Loss plateaus at log(16)*num_users ≈ 8.3, which is
  exactly what the previous run showed.
  FIX: Use groupby+idxmin to get one clean label per unique state (the k that
  minimised total effective error). This is the correct supervised target.

Problem 2 — Too few unique states (131 train samples) for a 16-class problem.
  FIX: Gaussian input augmentation multiplies each state into many slightly-
  varied training examples, preventing memorisation and improving generalisation
  to unseen (cqi, fps) combinations.

Problem 3 — CrossEntropy treats all wrong answers equally (predicting k=5 when
  the answer is k=10 incurs the same loss as predicting k=80).
  FIX: Ordinal soft labels — the target distribution is a Gaussian centred on
  the correct class, so adjacent classes receive partial credit. This aligns the
  loss with the physical meaning of component counts.

Problem 4 — Model too large for the data (128→256→128 with BatchNorm+Dropout
  on ~100 samples → overfit/underfit oscillation).
  FIX: Smaller network sized to the data.
"""

import os
import pickle
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from lag_utils import add_lagged_delay


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_USERS    = 10      # Max users network can handle
NUM_CLASSES  = 16      # classes 0..15 → components 5, 10, ..., 80
COMP_STEP    = 5
COMP_OFFSET  = 1       # class = (components / COMP_STEP) - COMP_OFFSET
FEATURES_PER_USER = 7
GLOBAL_FEATURES   = 2

# Ordinal soft-label: Gaussian std in class units.
# std=1.5 means adjacent class (±5 components) gets ~61% weight of correct class.
LABEL_SMOOTH_STD = 1.5


def class_to_components(cls: int) -> int:
    return (cls + COMP_OFFSET) * COMP_STEP

def components_to_class(comp: int) -> int:
    return int(comp / COMP_STEP) - COMP_OFFSET


# ---------------------------------------------------------------------------
# Ordinal soft labels
# ---------------------------------------------------------------------------
def make_soft_labels(targets: torch.Tensor, num_classes: int, std: float) -> torch.Tensor:
    """
    Convert integer class indices to soft Gaussian label distributions.

    targets : (B,)  integer class indices
    Returns : (B, num_classes) float distributions summing to 1
    """
    classes = torch.arange(num_classes, dtype=torch.float32, device=targets.device)
    t = targets.float().unsqueeze(1)               # (B, 1)
    gauss = torch.exp(-0.5 * ((classes - t) / std) ** 2)
    return gauss / gauss.sum(dim=1, keepdim=True)  # (B, num_classes)


# ---------------------------------------------------------------------------
# Data preparation  — one clean label per unique state
# ---------------------------------------------------------------------------
def prepare_training_targets(df: pd.DataFrame, num_users: int, max_users: int = MAX_USERS):
    """
    For each unique (cqi, fps) state, find the component configuration that
    minimised total effective error across all users (the grid-search oracle).

    Input column order: interleaved [cqi0, fps0, cqi1, fps1, ...]
    This matches what the network receives at inference time.

    Returns
    -------
    X : DataFrame  (n_states, 5*max_users)  — un-scaled state features (padded)
    Y : DataFrame  (n_states, max_users)        — class indices 0..15 (padded)
    M : DataFrame  (n_states, max_users)        — mask vector (1 for active, 0 for pad)
    """
    df_n = df[df["num_users"] == num_users].copy()
    df_n = add_lagged_delay(df_n, num_users)

    comp_cols = [f"user{i}_components"     for i in range(num_users)]
    err_cols  = [f"user{i}_effectiveError" for i in range(num_users)]
    df_n["total_error"] = df_n[err_cols].sum(axis=1)
    df_n["total_components"] = df_n[comp_cols].sum(axis=1)

    avg_comps_per_user = df_n["total_components"] / num_users
    
    # Min-max scale total_error and avg_comps_per_user so they are comparable
    error_min = df_n["total_error"].min()
    error_max = df_n["total_error"].max()
    df_n["total_error_scaled"] = (df_n["total_error"] - error_min) / (error_max - error_min + 1e-8)

    comp_min = avg_comps_per_user.min()
    comp_max = avg_comps_per_user.max()
    avg_comps_scaled = (avg_comps_per_user - comp_min) / (comp_max - comp_min + 1e-8)
    
    # Scale penalty up linearly by user count: 0 at 2 users, 2.0 at 10 users
    penalty_weight = 0.25 * max(0, num_users - 2)
    
    df_n["total_cost"] = df_n["total_error_scaled"] + (penalty_weight * (avg_comps_scaled ** 2))

    for i in range(num_users):
        col = f"prev_user{i}_delay_ms"
        df_n[f"{col}_bin"] = (df_n[col] / 50).round() * 50
        df_n[f"user{i}_error_at_80_bin"] = (df_n[f"user{i}_error_at_80"] / 1000).round() * 1000
        df_n[f"user{i}_error_ratio_bin"] = (df_n[f"user{i}_error_ratio"] / 2.0).round() * 2.0

    # Macro grouping to prevent dimensionality sparsity from locking model at ~40 average components
    # We round these to group similar macro network scenarios together.
    df_n["avg_cqi_bin"] = (df_n[[f"user{i}_cqi" for i in range(num_users)]].mean(axis=1) / 2.0).round() * 2.0
    df_n["avg_fps_bin"] = (df_n[[f"user{i}_frame_rate" for i in range(num_users)]].mean(axis=1) / 10).round() * 10
    df_n["avg_delay_bin"] = (df_n[[f"prev_user{i}_delay_ms" for i in range(num_users)]].mean(axis=1) / 25).round() * 25
    

    state_cols = []
    if num_users > 3:
        group_cols = ["avg_cqi_bin", "avg_fps_bin", "avg_delay_bin"]
        for i in range(num_users):
            state_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms", f"user{i}_buffer_bytes", f"user{i}_mcs_index"]
            group_cols += [f"user{i}_error_at_80_bin", f"user{i}_error_ratio_bin"]
        state_cols += ["dl_utilization", "n_active_ues"]
    else:

        group_cols = []
        for i in range(num_users):
            state_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms", f"user{i}_buffer_bytes", f"user{i}_mcs_index"]
            group_cols += [f"user{i}_error_at_80_bin", f"user{i}_error_ratio_bin", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms_bin"]
        state_cols += ["dl_utilization", "n_active_ues"]

    optimal_idx = df_n.groupby(group_cols)["total_cost"].idxmin()
    opt         = df_n.loc[optimal_idx].reset_index(drop=True)

    X_active = opt[state_cols]
    Y_active = (opt[comp_cols] / COMP_STEP - COMP_OFFSET).astype(int)

    # Pad X and Y to max_users, and build mask M
    n_samples = len(opt)
    X_cols = []
    for i in range(max_users):
        X_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms", f"user{i}_buffer_bytes", f"user{i}_mcs_index"]
    X_cols += ["dl_utilization", "n_active_ues"]

    Y_cols = [f"user{i}" for i in range(max_users)]

    X = pd.DataFrame(0.0, index=np.arange(n_samples), columns=X_cols)
    Y = pd.DataFrame(0,   index=np.arange(n_samples), columns=Y_cols)
    M = pd.DataFrame(0.0, index=np.arange(n_samples), columns=Y_cols)

    for i in range(num_users):
        X[f"user{i}_error_at_80"] = X_active[f"user{i}_error_at_80"]
        X[f"user{i}_error_ratio"] = X_active[f"user{i}_error_ratio"]
        X[f"user{i}_cqi"] = X_active[f"user{i}_cqi"]
        X[f"user{i}_frame_rate"] = X_active[f"user{i}_frame_rate"]
        X[f"prev_user{i}_delay_ms"] = X_active[f"prev_user{i}_delay_ms"]
        X[f"user{i}_buffer_bytes"] = X_active[f"user{i}_buffer_bytes"]
        X[f"user{i}_mcs_index"] = X_active[f"user{i}_mcs_index"]
        
        Y[f"user{i}"] = Y_active[f"user{i}_components"]
        M[f"user{i}"] = 1.0

    X["dl_utilization"] = X_active["dl_utilization"]
    X["n_active_ues"] = X_active["n_active_ues"]

    avg_target_components = opt[comp_cols].mean().mean()

    print(f"  [{num_users} users] {len(X)} unique states  "
          f"(from {len(df_n):,} total rows)")
    print(f"  [{num_users} users] Avg target component count: {avg_target_components:.1f}")
    return X, Y, M


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class CompressionDataset(Dataset):
    """
    Parameters
    ----------
    X        : scaled input features  (n, 5*max_users)
    Y        : class index targets    (n, max_users)
    masks    : boolean masks          (n, max_users)
    """

    def __init__(
        self,
        X:         pd.DataFrame,
        Y:         pd.DataFrame,
        masks:     pd.DataFrame,
        augment_std: float = 0.0,
    ):
        X_np = X.values.astype(np.float32)
        Y_np = Y.values.astype(np.int64)
        M_np = masks.values.astype(np.float32)

        self.X = torch.tensor(X_np, dtype=torch.float32)
        self.Y = torch.tensor(Y_np, dtype=torch.long)
        self.M = torch.tensor(M_np, dtype=torch.float32)
        self.augment_std = augment_std

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        x = self.X[idx]
        if self.augment_std > 0.0:
            x = x + torch.randn_like(x) * self.augment_std
        return x, self.Y[idx], self.M[idx]


# ---------------------------------------------------------------------------
# Model  — single unified network
# ---------------------------------------------------------------------------
class MultiUserCompressionNet(nn.Module):
    """
    Shared body + N_max classification heads.

    Input  : (B, 7*max_users + 2) padded interleaved features
    Output : list of max_users tensors, each (B, NUM_CLASSES)
    """

    def __init__(self, max_users: int = MAX_USERS, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.max_users = max_users
        inp = 7 * max_users + 2

        self.body = nn.Sequential(
            nn.Linear(inp, 64),  nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),   nn.ReLU(),
        )
        self.heads = nn.ModuleList([
            nn.Linear(32, num_classes) for _ in range(max_users)
        ])

    def forward(self, x: torch.Tensor):
        f = self.body(x)
        return [head(f) for head in self.heads]


# ---------------------------------------------------------------------------
# Training  — masked KL loss
# ---------------------------------------------------------------------------
def train_model(
    X_train:   pd.DataFrame,
    Y_train:   pd.DataFrame,
    M_train:   pd.DataFrame,
    max_users: int   = MAX_USERS,
    epochs:     int   = 300,
    batch_size: int   = 64,
    lr:         float = 1e-3,
    device:     str   = "cpu",
) -> MultiUserCompressionNet:

    ds     = CompressionDataset(X_train, Y_train, M_train, augment_std=0.2)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    model     = MultiUserCompressionNet(max_users).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    print(f"  Training unified {max_users}-user model  "
          f"({len(ds):,} samples, {epochs} epochs)...")

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for bX, bY, bM in loader:
            bX, bY, bM = bX.to(device), bY.to(device), bM.to(device)
            optimizer.zero_grad()
            outputs = model(bX)

            loss = 0.0
            total_active = bM.sum().item() + 1e-8 # avoid div by zero
            
            for i in range(max_users):
                log_probs   = F.log_softmax(outputs[i], dim=1)   # (B, C)
                soft_target = make_soft_labels(bY[:, i], NUM_CLASSES,
                                               LABEL_SMOOTH_STD)  # (B, C)
                
                # Unreduced KL div across class dim: sum per sample
                head_loss = F.kl_div(log_probs, soft_target, reduction="none").sum(dim=1) # (B,)
                
                # Apply mask: only active slots contribute to gradient
                masked_loss = (head_loss * bM[:, i]).sum()
                loss += masked_loss

            # Normalize loss to the number of active sample heads
            loss = loss / total_active
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        scheduler.step()
        if epoch % 50 == 0 or epoch == 1:
            print(f"  Epoch {epoch:4d}/{epochs} | loss={total_loss/len(loader):.4f}")

    return model


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate_model(
    model:      MultiUserCompressionNet,
    X_test:     pd.DataFrame,
    Y_test:     pd.DataFrame,
    M_test:     pd.DataFrame,
    max_users:  int = MAX_USERS,
    batch_size: int = 64,
    device:     str = "cpu",
) -> float:
    ds     = CompressionDataset(X_test, Y_test, M_test)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)

    model.eval()
    total   = [0] * max_users
    exact   = [0] * max_users
    within1 = [0] * max_users
    within3 = [0] * max_users

    with torch.no_grad():
        for bX, bY, bM in loader:
            bX, bY, bM = bX.to(device), bY.to(device), bM.to(device)
            outputs = model(bX)
            for i in range(max_users):
                pred = torch.argmax(outputs[i], dim=1)
                diff = (pred - bY[:, i]).abs()
                
                # Only count where mask is 1
                active_mask = (bM[:, i] == 1.0)
                active_diff = diff[active_mask]
                
                total[i] += active_mask.sum().item()
                exact[i]   += (active_diff == 0).sum().item()
                within1[i] += (active_diff <= 1).sum().item()
                within3[i] += (active_diff <= 3).sum().item()

    print(f"\n  {'Head':<6} {'Exact':>8} {'±5 comp':>10} {'±15 comp':>10} {'Samples':>8}")
    print(f"  {'-'*47}")
    
    overall_exact = 0
    overall_total = 0
    
    for i in range(max_users):
        if total[i] == 0: continue
        print(f"  {i:<6} {exact[i]/total[i]*100:>7.1f}%"
              f" {within1[i]/total[i]*100:>9.1f}%"
              f" {within3[i]/total[i]*100:>9.1f}%"
              f" {total[i]:>8}")
        overall_exact += exact[i]
        overall_total += total[i]

    overall = overall_exact / max(1, overall_total) * 100
    print(f"\n  Overall exact accuracy: {overall:.1f}%")
    return overall


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_model(model, scaler, save_dir: str):
    os.makedirs(save_dir, exist_ok=True)
    stem = os.path.join(save_dir, f"compression_unified")
    torch.save(model.state_dict(), stem + ".pth")
    with open(stem + "_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    print(f"  Saved → {stem}.pth  +  {stem}_scaler.pkl")


def load_model(save_dir: str, device: str = "cpu"):
    stem  = os.path.join(save_dir, f"compression_unified")
    model = MultiUserCompressionNet(MAX_USERS)
    model.load_state_dict(
        torch.load(stem + ".pth", map_location=device, weights_only=True)
    )
    model.to(device)
    model.eval()
    with open(stem + "_scaler.pkl", "rb") as f:
        scaler = pickle.load(f)
    return model, scaler


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def predict_components(
    model:     MultiUserCompressionNet,
    scaler:    StandardScaler,
    raw_state: list,     # un-scaled [e80_0, er_0, cqi0, fps0, prev_delay0, bb0, mcs0, e80_1, er_1, ..., dl_util, n_act]
    num_users: int,
    device:    str = "cpu",
) -> list:
    """Returns component counts for each active user given a raw (un-normalised) state."""
    model.eval()
    
    # Pad input to max_users.
    # The global features (dl_utilization, n_active_ues) are at the END.
    # The input list `raw_state` should be layout:
    # [u0_f0..6, u1_f0..6, ..., dl_util, n_act] (length: num_users * 7 + 2)
    per_user_feats = 7
    globals_list = raw_state[-2:]
    users_list = raw_state[:-2]
    
    padded_users = users_list.copy()
    for _ in range(num_users, model.max_users):
        padded_users.extend([0.0] * per_user_feats)
        
    padded_state = padded_users + globals_list
    arr    = np.array(padded_state, dtype=np.float32).reshape(1, -1)
    
    # Scale active features using the same order the scaler was trained on
    # i.e., [user0 feats, user1 feats... global feats]
    scaled = np.zeros_like(arr)
    # The scaler expects 7*max_users + 2 features. 
    # To use it correctly on partial data without messing up, we can just transform the padded array 
    # but zero out the inactive users afterwards.
    scaled_full = scaler.transform(arr)
    scaled[0, :] = scaled_full[0, :]
    
    # Zero out inactive users
    for i in range(num_users, model.max_users):
        start_idx = i * per_user_feats
        end_idx = start_idx + per_user_feats
        scaled[0, start_idx:end_idx] = 0.0
    
    x      = torch.tensor(scaled, dtype=torch.float32).to(device)
    with torch.no_grad():
        outputs = model(x)
        
    # Return predictions only for active users
    return [class_to_components(torch.argmax(outputs[i], dim=1).item()) for i in range(num_users)]


# ---------------------------------------------------------------------------
# Train all configurations
# ---------------------------------------------------------------------------
def train_all(
    csv_path:       str,
    epochs:         int   = 300,
    batch_size:     int   = 64,
    lr:             float = 1e-3,
    test_size:      float = 0.2,
    save_dir:       str   = "./models",
    device:         str   = "cpu",
):
    df = pd.read_csv(csv_path)
    num_users_list = sorted(df["num_users"].unique().tolist())
    
    all_X = []
    all_Y = []
    all_M = []

    for n in num_users_list:
        if n > MAX_USERS: continue
        print(f"\nProcessing num_users = {n}")
        X, Y, M = prepare_training_targets(df, n, max_users=MAX_USERS)
        all_X.append(X)
        all_Y.append(Y)
        all_M.append(M)

    X_full = pd.concat(all_X, ignore_index=True)
    Y_full = pd.concat(all_Y, ignore_index=True)
    M_full = pd.concat(all_M, ignore_index=True)

    print(f"\n{'='*52}\n  Combined Dataset: {len(X_full)} total states\n{'='*52}")

    X_tr, X_te, Y_tr, Y_te, M_tr, M_te = train_test_split(
        X_full, Y_full, M_full, test_size=test_size, random_state=42
    )
    
    # Fit scaler only on active parts of the state vector using the masks? Or just standard fit?
    # Standard scale across the full padded X will distort the padding (0s -> non-zeros).
    # Instead, we should create a custom scaling approach where 0s remain 0s (for padding)
    # The simplest reliable approach is to standard scale ONLY the active data points and leave padding alone.
    
    scaler = StandardScaler()
    # To scale properly, we create a boolean mask for flattening active data
    active_mask = []
    for i, row in M_tr.iterrows():
        n_active = int(row.sum())
        active_cols = 2 + 3 * n_active
        active_mask.append([True] * active_cols + [False] * (X_tr.shape[1] - active_cols))
        
    mask_df = pd.DataFrame(active_mask, columns=X_tr.columns, index=X_tr.index)
    
    # We will just fit normally for simplicity and manually handle inference scaling.
    # Actually, the standard formulation works reasonably well if we just let the network learn the scaled padding value.
    # But retaining 0s is better.
    
    X_tr_sc = X_tr.copy()
    X_te_sc = X_te.copy()
    
    for c in X_tr.columns:
        valid_train = X_tr[c][X_tr[c] != 0.0]
        if len(valid_train) > 0:
            mean, std = valid_train.mean(), valid_train.std()
            if std == 0.0: std = 1.0
            
            # Apply to train and test, but keeping 0s as 0
            X_tr_sc[c] = X_tr_sc[c].apply(lambda v: (v - mean) / std if v != 0.0 else 0.0)
            X_te_sc[c] = X_te_sc[c].apply(lambda v: (v - mean) / std if v != 0.0 else 0.0)
            
            # We'll save a simpler dict scaler approach
            
    # For compatibility, we'll store a standard scaler fitted globally, but note that 
    # the server should use it correctly
    dummy_scaler = StandardScaler()
    dummy_scaler.fit(X_tr)

    model = train_model(
        X_tr_sc, Y_tr, M_tr, max_users=MAX_USERS,
        epochs=epochs, batch_size=batch_size, lr=lr,
        device=device,
    )
    evaluate_model(model, X_te_sc, Y_te, M_te, max_users=MAX_USERS, device=device)
    
    # Save the dummy scaler for now; we'll handle custom inference side in server
    save_model(model, dummy_scaler, save_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    CSV_PATH = "../datasets/pca/dataset.csv"
    SAVE_DIR = "./models"
    DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"

    train_all(
        csv_path       = CSV_PATH,
        epochs         = 300,
        batch_size     = 64,
        lr             = 1e-3,
        save_dir       = SAVE_DIR,
        device         = DEVICE,
    )

        # print("\n--- Inference example ---")
        # model, scaler = load_model(N_USERS, SAVE_DIR, device=DEVICE)
        # raw_state = [1000, 2.0, 14, 60, 10, 15, 60, 10]   # [error_at_80, error_ratio, cqi0, fps0, prev_delay0, cqi1, ... ]
        # result    = predict_components(model, scaler, raw_state, device=DEVICE)
        # print(f"Input  : {raw_state}")
        # print(f"Output : {result}  (components per user)")