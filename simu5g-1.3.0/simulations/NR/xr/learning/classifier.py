"""
Multi-user compression level classifier.
=========================================
Discrete output: 16 classes → components in {5, 10, 15, ..., 80}

Architecture: shared MLP body + N_max per-user classification heads.
Training uses masked KL-divergence loss with ordinal soft labels.
"""

import logging
import os
import pickle
from typing import Optional

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

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_USERS = 10          # Maximum users the network can handle
NUM_CLASSES = 16        # classes 0..15 → components 5, 10, ..., 80
COMP_STEP = 5
COMP_OFFSET = 1         # class = (components / COMP_STEP) - COMP_OFFSET

# Compression levels for the MSE error vector
CL_LEVELS = list(range(5, 81, 5))   # [5, 10, 15, ..., 80]
NUM_CL_LEVELS = len(CL_LEVELS)      # 16
MSE_FEATURES = [f"mse_at_{cl}" for cl in CL_LEVELS]

# Per-user: 16 MSE + cqi + frame_rate + prev_delay + buffer_bytes + mcs_index = 21
FEATURES_PER_USER = NUM_CL_LEVELS + 5
GLOBAL_FEATURES = 2     # dl_utilization, n_active_ues

# Ordinal soft-label Gaussian std in class units.
# std=1.0 means adjacent class (±5 components) gets ~61% weight of correct class.
LABEL_SMOOTH_STD = 1.0

# Verify class mapping is consistent
assert all(
    (cls + COMP_OFFSET) * COMP_STEP == comp
    for cls, comp in enumerate(CL_LEVELS)
), "Class ↔ component mapping is broken"


def class_to_components(cls: int) -> int:
    """Convert a class index (0..15) to a component count (5..80)."""
    return (cls + COMP_OFFSET) * COMP_STEP


def components_to_class(comp: int) -> int:
    """Convert a component count (5..80) to a class index (0..15)."""
    return int(comp / COMP_STEP) - COMP_OFFSET


# ---------------------------------------------------------------------------
# Ordinal soft labels
# ---------------------------------------------------------------------------
def make_soft_labels(targets: torch.Tensor, num_classes: int, std: float) -> torch.Tensor:
    """Convert integer class indices to soft Gaussian label distributions.

    Args:
        targets: (B,) integer class indices.
        num_classes: Total number of classes.
        std: Gaussian standard deviation in class-index units.

    Returns:
        (B, num_classes) float distributions summing to 1.
    """
    classes = torch.arange(num_classes, dtype=torch.float32, device=targets.device)
    t = targets.float().unsqueeze(1)               # (B, 1)
    gauss = torch.exp(-0.5 * ((classes - t) / std) ** 2)
    return gauss / gauss.sum(dim=1, keepdim=True)   # (B, num_classes)


# ---------------------------------------------------------------------------
# Oracle target computation
# ---------------------------------------------------------------------------
def compute_oracle_targets(df: pd.DataFrame, num_users: int) -> pd.DataFrame:
    """Find the optimal compression configuration for each frame.

    For each frame, computes a cost that combines:
      - Normalized effective error (scaled per-user by frame rate)
      - Fairness penalty (variance of component assignments)

    Returns the DataFrame filtered to optimal rows with a ``total_cost`` column.
    """
    df_n = df[df["num_users"] == num_users].copy()
    df_n = add_lagged_delay(df_n, num_users)

    comp_cols = [f"user{i}_components" for i in range(num_users)]
    err_cols = [f"user{i}_effectiveError" for i in range(num_users)]

    # Normalize error by frame_rate so high-FPS users aren't starved
    for i in range(num_users):
        norm_col = f"user{i}_normError"
        df_n[norm_col] = df_n[err_cols[i]] / df_n[f"user{i}_frame_rate"].clip(lower=1)

    normalized_err_cols = [f"user{i}_normError" for i in range(num_users)]
    df_n["total_error"] = df_n[normalized_err_cols].sum(axis=1)
    df_n["total_components"] = df_n[comp_cols].sum(axis=1)

    # Fairness penalty on component variance
    fairness_weight = 50.0
    df_n["variance_penalty"] = df_n[comp_cols].var(axis=1).fillna(0) * fairness_weight

    # Min-max scale total_error and variance_penalty so they are comparable
    for col in ["total_error", "variance_penalty"]:
        col_min = df_n[col].min()
        col_max = df_n[col].max()
        df_n[f"{col}_scaled"] = (df_n[col] - col_min) / (col_max - col_min + 1e-8)

    # Cost = error + fairness penalty (no component penalty — just tie-breaking)
    df_n["total_cost"] = (
        df_n["total_error_scaled"] + 0.15 * df_n["variance_penalty_scaled"]
    )

    # Find optimal configuration per frame
    optimal_idx = df_n.groupby("frameNumber")["total_cost"].idxmin()
    opt = df_n.loc[optimal_idx].reset_index(drop=True)

    avg_target = opt[comp_cols].mean().mean()
    log.info(
        f"  [{num_users} users] {len(opt)} optimal states "
        f"(from {len(df_n):,} total rows), "
        f"avg target components: {avg_target:.1f}"
    )

    return opt


# ---------------------------------------------------------------------------
# Feature padding
# ---------------------------------------------------------------------------
def build_padded_features(
    opt: pd.DataFrame,
    num_users: int,
    max_users: int = MAX_USERS,
) -> tuple:
    """Build padded feature (X), target (Y), and mask (M) matrices.

    Pads to ``max_users`` so that the unified model can handle variable
    user counts.  Inactive user slots are zero-filled with mask=0.

    Returns:
        (X, Y, M) as DataFrames.
    """
    comp_cols = [f"user{i}_components" for i in range(num_users)]
    n_samples = len(opt)

    # Build column lists for the full (padded) layout
    X_cols = []
    for i in range(max_users):
        X_cols += [f"user{i}_mse_at_{cl}" for cl in CL_LEVELS]
        X_cols += [
            f"user{i}_cqi", f"user{i}_frame_rate",
            f"prev_user{i}_delay_ms",
            f"user{i}_buffer_bytes", f"user{i}_mcs_index",
        ]
    X_cols += ["dl_utilization", "n_active_ues"]

    Y_cols = [f"user{i}" for i in range(max_users)]

    X = pd.DataFrame(0.0, index=np.arange(n_samples), columns=X_cols)
    Y = pd.DataFrame(0, index=np.arange(n_samples), columns=Y_cols)
    M = pd.DataFrame(0.0, index=np.arange(n_samples), columns=Y_cols)

    # Fill in active user data
    Y_active = (opt[comp_cols] / COMP_STEP - COMP_OFFSET).astype(int)

    for i in range(num_users):
        for cl in CL_LEVELS:
            X[f"user{i}_mse_at_{cl}"] = opt[f"user{i}_mse_at_{cl}"].values
        X[f"user{i}_cqi"] = opt[f"user{i}_cqi"].values
        X[f"user{i}_frame_rate"] = opt[f"user{i}_frame_rate"].values
        X[f"prev_user{i}_delay_ms"] = opt[f"prev_user{i}_delay_ms"].values
        X[f"user{i}_buffer_bytes"] = opt[f"user{i}_buffer_bytes"].values
        X[f"user{i}_mcs_index"] = opt[f"user{i}_mcs_index"].values

        Y[f"user{i}"] = Y_active[f"user{i}_components"]
        M[f"user{i}"] = 1.0

    X["dl_utilization"] = opt["dl_utilization"].values
    X["n_active_ues"] = opt["n_active_ues"].values

    return X, Y, M


def prepare_training_targets(
    df: pd.DataFrame,
    num_users: int,
    max_users: int = MAX_USERS,
) -> tuple:
    """High-level function: compute oracle targets, then pad features.

    Returns:
        (X, Y, M) DataFrames ready for training.
    """
    opt = compute_oracle_targets(df, num_users)
    return build_padded_features(opt, num_users, max_users)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class CompressionDataset(Dataset):
    """PyTorch dataset for compression level classification.

    Args:
        X: Scaled input features (n_samples, FEATURES_PER_USER * max_users + GLOBAL_FEATURES).
        Y: Class index targets (n_samples, max_users).
        masks: Boolean masks (n_samples, max_users).  1.0 for active users.
    """

    def __init__(self, X: pd.DataFrame, Y: pd.DataFrame, masks: pd.DataFrame):
        self.X = torch.tensor(X.values.astype(np.float32), dtype=torch.float32)
        self.Y = torch.tensor(Y.values.astype(np.int64), dtype=torch.long)
        self.M = torch.tensor(masks.values.astype(np.float32), dtype=torch.float32)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx], self.M[idx]


# ---------------------------------------------------------------------------
# Model — single unified network
# ---------------------------------------------------------------------------
class MultiUserCompressionNet(nn.Module):
    """Shared body + N_max classification heads.

    Input:  (B, FEATURES_PER_USER * max_users + GLOBAL_FEATURES)
    Output: list of max_users tensors, each (B, NUM_CLASSES)
    """

    def __init__(self, max_users: int = MAX_USERS, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.max_users = max_users
        inp = FEATURES_PER_USER * max_users + GLOBAL_FEATURES

        self.body = nn.Sequential(
            nn.Linear(inp, 256), nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128), nn.ReLU(),
        )
        self.heads = nn.ModuleList([
            nn.Linear(128, num_classes) for _ in range(max_users)
        ])

    def forward(self, x: torch.Tensor) -> list:
        f = self.body(x)
        return [head(f) for head in self.heads]


# ---------------------------------------------------------------------------
# Training — masked KL loss
# ---------------------------------------------------------------------------
def train_model(
    X_train: pd.DataFrame,
    Y_train: pd.DataFrame,
    M_train: pd.DataFrame,
    max_users: int = MAX_USERS,
    epochs: int = 300,
    batch_size: int = 64,
    lr: float = 1e-3,
    device: str = "cpu",
) -> MultiUserCompressionNet:
    """Train the unified multi-user classifier."""
    ds = CompressionDataset(X_train, Y_train, M_train)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    model = MultiUserCompressionNet(max_users).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    log.info(
        f"  Training unified {max_users}-user model "
        f"({len(ds):,} samples, {epochs} epochs)..."
    )

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for bX, bY, bM in loader:
            bX, bY, bM = bX.to(device), bY.to(device), bM.to(device)
            optimizer.zero_grad()
            outputs = model(bX)

            loss = torch.tensor(0.0, device=device)
            total_active = bM.sum().item() + 1e-8

            for i in range(max_users):
                log_probs = F.log_softmax(outputs[i], dim=1)
                soft_target = make_soft_labels(
                    bY[:, i], NUM_CLASSES, LABEL_SMOOTH_STD
                )
                head_loss = F.kl_div(
                    log_probs, soft_target, reduction="none"
                ).sum(dim=1)
                masked_loss = (head_loss * bM[:, i]).sum()
                loss = loss + masked_loss

            loss = loss / total_active
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        scheduler.step()
        if epoch % 50 == 0 or epoch == 1:
            log.info(f"  Epoch {epoch:4d}/{epochs} | loss={total_loss/len(loader):.4f}")

    return model


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate_model(
    model: MultiUserCompressionNet,
    X_test: pd.DataFrame,
    Y_test: pd.DataFrame,
    M_test: pd.DataFrame,
    max_users: int = MAX_USERS,
    batch_size: int = 64,
    device: str = "cpu",
) -> float:
    """Evaluate model accuracy on a test set."""
    ds = CompressionDataset(X_test, Y_test, M_test)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)

    model.eval()
    total = [0] * max_users
    exact = [0] * max_users
    within1 = [0] * max_users
    within3 = [0] * max_users

    with torch.no_grad():
        for bX, bY, bM in loader:
            bX, bY, bM = bX.to(device), bY.to(device), bM.to(device)
            outputs = model(bX)
            for i in range(max_users):
                pred = torch.argmax(outputs[i], dim=1)
                diff = (pred - bY[:, i]).abs()
                active_mask = bM[:, i] == 1.0
                active_diff = diff[active_mask]

                total[i] += active_mask.sum().item()
                exact[i] += (active_diff == 0).sum().item()
                within1[i] += (active_diff <= 1).sum().item()
                within3[i] += (active_diff <= 3).sum().item()

    log.info(f"\n  {'Head':<6} {'Exact':>8} {'±5 comp':>10} {'±15 comp':>10} {'Samples':>8}")
    log.info(f"  {'-'*47}")

    overall_exact = 0
    overall_total = 0

    for i in range(max_users):
        if total[i] == 0:
            continue
        log.info(
            f"  {i:<6} {exact[i]/total[i]*100:>7.1f}%"
            f" {within1[i]/total[i]*100:>9.1f}%"
            f" {within3[i]/total[i]*100:>9.1f}%"
            f" {total[i]:>8}"
        )
        overall_exact += exact[i]
        overall_total += total[i]

    overall = overall_exact / max(1, overall_total) * 100
    log.info(f"\n  Overall exact accuracy: {overall:.1f}%")
    return overall


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_model(model: MultiUserCompressionNet, scaler: StandardScaler, save_dir: str) -> None:
    """Save model weights and scaler to disk."""
    os.makedirs(save_dir, exist_ok=True)
    stem = os.path.join(save_dir, "compression_unified")
    torch.save(model.state_dict(), stem + ".pth")
    with open(stem + "_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    log.info(f"  Saved → {stem}.pth  +  {stem}_scaler.pkl")


def load_model(save_dir: str, device: str = "cpu") -> tuple:
    """Load model and scaler from disk."""
    stem = os.path.join(save_dir, "compression_unified")
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
# Inference helpers
# ---------------------------------------------------------------------------
def _prepare_input(
    model: MultiUserCompressionNet,
    scaler: StandardScaler,
    raw_state: list,
    num_users: int,
) -> np.ndarray:
    """Pad, scale, and zero-out inactive users in a raw state vector.

    Args:
        raw_state: Un-scaled flat feature vector:
            [u0_mse5..u0_mse80, u0_cqi, u0_fps, u0_prev_delay, u0_bb, u0_mcs,
             u1_mse5..u1_mse80, ..., dl_util, n_act]
            Length: num_users * FEATURES_PER_USER + GLOBAL_FEATURES

    Returns:
        Scaled numpy array of shape (1, FEATURES_PER_USER * max_users + GLOBAL_FEATURES).
    """
    per_user = FEATURES_PER_USER
    globals_list = raw_state[-2:]
    users_list = raw_state[:-2]

    # Pad to max_users
    padded_users = list(users_list)
    for _ in range(num_users, model.max_users):
        padded_users.extend([0.0] * per_user)

    padded_state = padded_users + globals_list
    arr = np.array(padded_state, dtype=np.float32).reshape(1, -1)

    # Scale using the trained scaler
    if hasattr(scaler, "feature_names_in_"):
        cols = list(scaler.feature_names_in_)
        arr_in = pd.DataFrame(arr, columns=cols)
    else:
        arr_in = arr

    scaled = scaler.transform(arr_in).copy()

    # Zero out inactive user slots
    for i in range(num_users, model.max_users):
        start_idx = i * per_user
        end_idx = start_idx + per_user
        scaled[0, start_idx:end_idx] = 0.0

    return scaled


def predict_components(
    model: MultiUserCompressionNet,
    scaler: StandardScaler,
    raw_state: list,
    num_users: int,
    device: str = "cpu",
) -> list:
    """Predict optimal component counts for each active user.

    Returns:
        List of component counts (one per active user).
    """
    scaled = _prepare_input(model, scaler, raw_state, num_users)
    x = torch.tensor(scaled, dtype=torch.float32).to(device)

    model.eval()
    with torch.no_grad():
        outputs = model(x)

    return [
        class_to_components(torch.argmax(outputs[i], dim=1).item())
        for i in range(num_users)
    ]


def predict_with_probabilities(
    model: MultiUserCompressionNet,
    scaler: StandardScaler,
    raw_state: list,
    num_users: int,
    device: str = "cpu",
) -> list:
    """Predict with full probability distributions for each active user.

    Returns:
        List of dicts, one per active user:
        {
            "optimal_components": int,
            "confidence": float,
            "probabilities": np.ndarray of shape (NUM_CLASSES,),
        }
    """
    scaled = _prepare_input(model, scaler, raw_state, num_users)
    x = torch.tensor(scaled, dtype=torch.float32).to(device)

    model.eval()
    with torch.no_grad():
        outputs = model(x)

    results = []
    for i in range(num_users):
        logits = outputs[i][0]
        probs = torch.softmax(logits, dim=0).cpu().numpy()
        pred_idx = int(probs.argmax())
        results.append({
            "optimal_components": class_to_components(pred_idx),
            "confidence": float(probs[pred_idx]),
            "probabilities": probs,
        })

    return results


# ---------------------------------------------------------------------------
# Train all configurations
# ---------------------------------------------------------------------------
def train_all(
    csv_path: str,
    epochs: int = 300,
    batch_size: int = 64,
    lr: float = 1e-3,
    test_size: float = 0.2,
    save_dir: str = "./models",
    device: str = "cpu",
) -> None:
    """Train on all user-count configurations combined."""
    df = pd.read_csv(csv_path)
    num_users_list = sorted(df["num_users"].unique().tolist())

    all_X, all_Y, all_M = [], [], []

    for n in num_users_list:
        if n > MAX_USERS:
            continue
        log.info(f"\nProcessing num_users = {n}")
        X, Y, M = prepare_training_targets(df, n, max_users=MAX_USERS)
        all_X.append(X)
        all_Y.append(Y)
        all_M.append(M)

    X_full = pd.concat(all_X, ignore_index=True)
    Y_full = pd.concat(all_Y, ignore_index=True)
    M_full = pd.concat(all_M, ignore_index=True)

    log.info(f"\n{'='*52}\n  Combined Dataset: {len(X_full)} total states\n{'='*52}")

    X_tr, X_te, Y_tr, Y_te, M_tr, M_te = train_test_split(
        X_full, Y_full, M_full, test_size=test_size, random_state=42
    )

    scaler = StandardScaler()
    X_tr_sc = pd.DataFrame(
        scaler.fit_transform(X_tr), columns=X_tr.columns, index=X_tr.index
    )
    X_te_sc = pd.DataFrame(
        scaler.transform(X_te), columns=X_te.columns, index=X_te.index
    )

    # Re-apply padding zeros for inactive users
    for i in range(MAX_USERS):
        mask_tr = M_tr[f"user{i}"] == 0.0
        mask_te = M_te[f"user{i}"] == 0.0
        feat_cols = [f"user{i}_mse_at_{cl}" for cl in CL_LEVELS] + [
            f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms",
            f"user{i}_buffer_bytes", f"user{i}_mcs_index",
        ]
        for col in feat_cols:
            X_tr_sc.loc[mask_tr, col] = 0.0
            X_te_sc.loc[mask_te, col] = 0.0

    model = train_model(
        X_tr_sc, Y_tr, M_tr, max_users=MAX_USERS,
        epochs=epochs, batch_size=batch_size, lr=lr, device=device,
    )
    evaluate_model(
        model, X_te_sc, Y_te, M_te, max_users=MAX_USERS, device=device
    )
    save_model(model, scaler, save_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    CSV_PATH = "../datasets/pca/dataset.csv"
    SAVE_DIR = "./models"
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    train_all(
        csv_path=CSV_PATH,
        epochs=300,
        batch_size=64,
        lr=1e-3,
        save_dir=SAVE_DIR,
        device=DEVICE,
    )