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
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from lag_utils import add_lagged_delay


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_COMP  = 5
MAX_COMP  = 80
COMP_STEP = 5

def clamp_components(comp: float) -> int:
    scaled = round(comp / COMP_STEP) * COMP_STEP
    return int(max(MIN_COMP, min(MAX_COMP, scaled)))


# ---------------------------------------------------------------------------
# Data preparation  — one clean label per unique state
# ---------------------------------------------------------------------------
def prepare_training_targets(df: pd.DataFrame, num_users: int):
    """
    For each unique (cqi, fps) state, find the component configuration that
    minimised total effective error across all users (the grid-search oracle).

    Input column order: interleaved [cqi0, fps0, cqi1, fps1, ...]
    This matches what the network receives at inference time.

    Returns
    -------
    X : DataFrame  (n_states, 2*num_users)  — un-scaled state features
    Y : DataFrame  (n_states, num_users)    — class indices 0..15
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

    df_n["error_at_80_bin"] = (df_n["error_at_80"] / 1000).round() * 1000
    df_n["error_ratio_bin"] = (df_n["error_ratio"] / 2.0).round() * 2.0

    # Macro grouping to prevent dimensionality sparsity from locking model at ~40 average components
    # We round these to group similar macro network scenarios together.
    df_n["avg_cqi_bin"] = (df_n[[f"user{i}_cqi" for i in range(num_users)]].mean(axis=1) / 2.0).round() * 2.0
    df_n["avg_fps_bin"] = (df_n[[f"user{i}_frame_rate" for i in range(num_users)]].mean(axis=1) / 10).round() * 10
    df_n["avg_delay_bin"] = (df_n[[f"prev_user{i}_delay_ms" for i in range(num_users)]].mean(axis=1) / 25).round() * 25
    

    state_cols = ["error_at_80", "error_ratio"]
    if num_users > 3:
        group_cols = ["error_at_80_bin", "error_ratio_bin", "avg_cqi_bin", "avg_fps_bin", "avg_delay_bin"]
        for i in range(num_users):
            state_cols += [f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms"]
    else:

        group_cols = ["error_at_80_bin", "error_ratio_bin"]
        for i in range(num_users):
            state_cols += [f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms"]
            group_cols += [f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms_bin"]

    optimal_idx = df_n.groupby(group_cols)["total_cost"].idxmin()
    opt         = df_n.loc[optimal_idx].reset_index(drop=True)

    X = opt[state_cols].reset_index(drop=True)
    Y = opt[comp_cols].reset_index(drop=True).astype(float)
    Y.columns = [f"user{i}" for i in range(num_users)]

    avg_target_components = opt[comp_cols].mean().mean()

    print(f"  [{num_users} users] {len(X)} unique states  "
          f"(from {len(df_n):,} total rows)")
    print(f"  [{num_users} users] Avg target component count: {avg_target_components:.1f}")
    return X, Y


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class CompressionDataset(Dataset):
    """
    Parameters
    ----------
    X        : scaled input features  (n, 2*num_users)
    Y        : class index targets    (n, num_users)
    """

    def __init__(
        self,
        X:         pd.DataFrame,
        Y:         pd.DataFrame,
        augment_std: float = 0.0,
    ):
        X_np = X.values.astype(np.float32)
        Y_np = Y.values.astype(np.float32)

        self.X = torch.tensor(X_np, dtype=torch.float32)
        self.Y = torch.tensor(Y_np, dtype=torch.float32)
        self.augment_std = augment_std

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        x = self.X[idx]
        if self.augment_std > 0.0:
            x = x + torch.randn_like(x) * self.augment_std
        return x, self.Y[idx]


# ---------------------------------------------------------------------------
# Model  — small network appropriate for limited unique states
# ---------------------------------------------------------------------------
class MultiUserCompressionNet(nn.Module):
    """
    Shared body + one classification head per user.

    Input  : (B, 3*num_users + 2)  interleaved [error_at_80, error_ratio, cqi0, fps0, prev_delay0, cqi1, fps1, prev_delay1, ...]
    Output : list of num_users tensors, each (B, 1)  — raw regressions
    """

    def __init__(self, num_users: int):
        super().__init__()
        self.num_users = num_users
        inp = 3 * num_users + 2

        self.body = nn.Sequential(
            nn.Linear(inp, 32),  nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),   nn.ReLU(),
        )
        self.heads = nn.ModuleList([
            nn.Linear(16, 1) for _ in range(num_users)
        ])

    def forward(self, x: torch.Tensor):
        f = self.body(x)
        return [head(f).squeeze(1) for head in self.heads]


# ---------------------------------------------------------------------------
# Training  — ordinal soft-label KL loss
# ---------------------------------------------------------------------------
def train_model(
    X_train:   pd.DataFrame,
    Y_train:   pd.DataFrame,
    num_users: int,
    epochs:     int   = 300,
    batch_size: int   = 64,
    lr:         float = 1e-3,
    device:     str   = "cpu",
) -> MultiUserCompressionNet:

    ds     = CompressionDataset(X_train, Y_train, augment_std=0.2)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    model     = MultiUserCompressionNet(num_users).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    print(f"  Training {num_users}-user model  "
          f"({len(ds):,} samples, {epochs} epochs)...")

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for bX, bY in loader:
            bX, bY = bX.to(device), bY.to(device)
            optimizer.zero_grad()
            outputs = model(bX)

            loss = 0.0
            criterion = nn.MSELoss()
            for i in range(num_users):
                loss += criterion(outputs[i], bY[:, i])

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
    scaler_Y:   MinMaxScaler,
    num_users:  int,
    batch_size: int = 64,
    device:     str = "cpu",
) -> float:
    ds     = CompressionDataset(X_test, Y_test)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)

    model.eval()
    total   = 0
    exact   = [0] * num_users
    within1 = [0] * num_users
    within3 = [0] * num_users

    with torch.no_grad():
        for bX, bY in loader:
            bX, bY = bX.to(device), bY.to(device)
            outputs = model(bX)
            total  += bY.size(0)
            
            # Inverse transform predictions and targets
            out_stacked = torch.stack(outputs, dim=1).cpu().numpy()
            pred_unscaled = torch.tensor(scaler_Y.inverse_transform(out_stacked), device=device)
            target_unscaled = torch.tensor(scaler_Y.inverse_transform(bY.cpu().numpy()), device=device)

            for i in range(num_users):
                pred = torch.round(pred_unscaled[:, i] / 5.0) * 5.0
                pred = torch.clamp(pred, min=5.0, max=80.0)
                diff = (pred - target_unscaled[:, i]).abs() / 5.0
                exact[i]   += (diff == 0).sum().item()
                within1[i] += (diff <= 1).sum().item()
                within3[i] += (diff <= 3).sum().item()

    print(f"\n  {'User':<6} {'Exact':>8} {'±5 comp':>10} {'±15 comp':>10}")
    print(f"  {'-'*38}")
    for i in range(num_users):
        print(f"  {i:<6} {exact[i]/total*100:>7.1f}%"
              f" {within1[i]/total*100:>9.1f}%"
              f" {within3[i]/total*100:>9.1f}%")

    overall = sum(exact) / (total * num_users) * 100
    print(f"\n  Overall exact accuracy: {overall:.1f}%")
    return overall


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_model(model, scaler_X, scaler_Y, num_users: int, save_dir: str):
    os.makedirs(save_dir, exist_ok=True)
    stem = os.path.join(save_dir, f"compression_{num_users}users")
    torch.save(model.state_dict(), stem + ".pth")
    with open(stem + "_scaler_X.pkl", "wb") as f:
        pickle.dump(scaler_X, f)
    with open(stem + "_scaler_Y.pkl", "wb") as f:
        pickle.dump(scaler_Y, f)
    print(f"  Saved → {stem}.pth  +  {stem}_scaler_X.pkl  +  {stem}_scaler_Y.pkl")


def load_model(num_users: int, save_dir: str, device: str = "cpu"):
    stem  = os.path.join(save_dir, f"compression_{num_users}users")
    model = MultiUserCompressionNet(num_users)
    model.load_state_dict(
        torch.load(stem + ".pth", map_location=device, weights_only=True)
    )
    model.to(device)
    model.eval()
    with open(stem + "_scaler_X.pkl", "rb") as f:
        scaler_X = pickle.load(f)
    with open(stem + "_scaler_Y.pkl", "rb") as f:
        scaler_Y = pickle.load(f)
    return model, scaler_X, scaler_Y


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def predict_components(
    model:     MultiUserCompressionNet,
    scaler_X:  StandardScaler,
    scaler_Y:  MinMaxScaler,
    raw_state: list,     # un-scaled [error_at_80, error_ratio, cqi0, fps0, prev_delay0, cqi1, fps1, prev_delay1, ...]
    device:    str = "cpu",
) -> list:
    """Returns component counts for each user given a raw (un-normalised) state."""
    model.eval()
    arr    = np.array(raw_state, dtype=np.float32).reshape(1, -1)
    scaled = scaler_X.transform(arr)
    x      = torch.tensor(scaled, dtype=torch.float32).to(device)
    with torch.no_grad():
        outputs = model(x)
    
    out_stacked = torch.stack(outputs, dim=1).cpu().numpy()
    pred_unscaled = scaler_Y.inverse_transform(out_stacked)[0]
    return [clamp_components(p) for p in pred_unscaled]


# ---------------------------------------------------------------------------
# Train all configurations
# ---------------------------------------------------------------------------
def train_all(
    csv_path:       str,
    num_users_list: list  = None,
    epochs:         int   = 300,
    batch_size:     int   = 64,
    lr:             float = 1e-3,
    test_size:      float = 0.2,
    save_dir:       str   = "./models",
    device:         str   = "cpu",
):
    df = pd.read_csv(csv_path)
    if num_users_list is None:
        num_users_list = sorted(df["num_users"].unique().tolist())

    for n in num_users_list:
        print(f"\n{'='*52}\n  num_users = {n}\n{'='*52}")

        X, Y = prepare_training_targets(df, n)

        X_tr, X_te, Y_tr, Y_te = train_test_split(
            X, Y, test_size=test_size, random_state=42
        )
        scaler_X  = StandardScaler()
        X_tr_sc = pd.DataFrame(scaler_X.fit_transform(X_tr), columns=X_tr.columns)
        X_te_sc = pd.DataFrame(scaler_X.transform(X_te),     columns=X_te.columns)

        scaler_Y = MinMaxScaler(feature_range=(0, 1))
        Y_tr_sc = pd.DataFrame(scaler_Y.fit_transform(Y_tr), columns=Y_tr.columns)
        Y_te_sc = pd.DataFrame(scaler_Y.transform(Y_te),     columns=Y_te.columns)

        model = train_model(
            X_tr_sc, Y_tr_sc, n,
            epochs=epochs, batch_size=batch_size, lr=lr,
            device=device,
        )
        evaluate_model(model, X_te_sc, Y_te_sc, scaler_Y, n, device=device)
        save_model(model, scaler_X, scaler_Y, n, save_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    CSV_PATH = "../datasets/pca/dataset.csv"
    SAVE_DIR = "./models"
    DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
    # N_USERS  = 3

    for N_USERS in range(2, 11):
        train_all(
            csv_path       = CSV_PATH,
            num_users_list = [N_USERS],
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