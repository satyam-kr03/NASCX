"""
Multi-user compression level classifier  (Transformer edition)
===============================================================
Discrete output: 16 classes → components in {5, 10, 15, ..., 80}
Single unified model for all num_users configurations (2–10).

Architecture
------------
Each user's 5-dim feature vector is treated as a *token* in a sequence
of length N_max = 10.  A lightweight Pre-LN Transformer encoder learns
inter-user interference patterns via self-attention, and a shared
classification head maps every token to 16 component-class logits.

Key design choices for small-data regime (~500–1000 unique states):
  • Pre-Layer-Norm (norm_first=True) — stabilises training without warmup hacks
  • Per-user MLP encoder — richer token embeddings before attention
  • 2 encoder layers, 2 heads, d_model=32 — capacity matched to data
  • LR warmup + cosine decay — prevents early divergence
  • Gradient clipping (max_norm=1.0)
  • Augmentation std=0.25
  • Ordinal soft labels + masked KL loss (unchanged from MLP version)
"""

import os
import math
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
MAX_USERS        = 10      # Max users network can handle
NUM_CLASSES      = 16      # classes 0..15 → components 5, 10, ..., 80
COMP_STEP        = 5
COMP_OFFSET      = 1       # class = (components / COMP_STEP) - COMP_OFFSET
FEATURES_PER_USER = 5      # error_at_80, error_ratio, cqi, frame_rate, prev_delay_ms

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
            state_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms"]
            group_cols += [f"user{i}_error_at_80_bin", f"user{i}_error_ratio_bin"]
    else:

        group_cols = []
        for i in range(num_users):
            state_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms"]
            group_cols += [f"user{i}_error_at_80_bin", f"user{i}_error_ratio_bin", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms_bin"]

    optimal_idx = df_n.groupby(group_cols)["total_cost"].idxmin()
    opt         = df_n.loc[optimal_idx].reset_index(drop=True)

    X_active = opt[state_cols]
    Y_active = (opt[comp_cols] / COMP_STEP - COMP_OFFSET).astype(int)

    # Pad X and Y to max_users, and build mask M
    n_samples = len(opt)
    X_cols = []
    for i in range(max_users):
        X_cols += [f"user{i}_error_at_80", f"user{i}_error_ratio", f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms"]

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
        
        Y[f"user{i}"] = Y_active[f"user{i}_components"]
        M[f"user{i}"] = 1.0

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
        m = self.M[idx]
        if self.augment_std > 0.0:
            # Only augment active features (where the corresponding user mask is 1)
            # Expand mask from (max_users,) to (5*max_users,) to match feature dims
            feat_mask = m.repeat_interleave(FEATURES_PER_USER)  # (5*max_users,)
            noise = torch.randn_like(x) * self.augment_std * feat_mask
            x = x + noise
        return x, self.Y[idx], m


# ---------------------------------------------------------------------------
# Model  — Transformer encoder for inter-user attention
# ---------------------------------------------------------------------------
class MultiUserCompressionNet(nn.Module):
    """
    Lightweight Pre-LN Transformer for multi-user compression classification.

    Architecture:
      1. Shared per-user MLP encoder  (5 → d_model)
      2. Learnable positional embedding
      3. Pre-LN Transformer encoder   (self-attention for cross-user patterns)
      4. Shared classification head    (d_model → 16)

    Input  : x    — (B, 5*max_users) padded interleaved features
             mask — (B, max_users)    1.0 = active, 0.0 = padded  [optional]
    Output : list of max_users tensors, each (B, NUM_CLASSES)
    """

    def __init__(
        self,
        max_users:   int = MAX_USERS,
        num_classes: int = NUM_CLASSES,
        d_model:     int = 32,
        nhead:       int = 2,
        num_layers:  int = 2,
        dim_ff:      int = 64,
        dropout:     float = 0.15,
    ):
        super().__init__()
        self.max_users   = max_users
        self.num_classes = num_classes
        self.d_model     = d_model

        # Per-user feature encoder (shared across all user slots)
        # A small MLP gives richer token embeddings before attention,
        # compared to a single Linear projection.
        self.user_encoder = nn.Sequential(
            nn.Linear(FEATURES_PER_USER, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
        )

        # Learnable positional embedding (one per user slot)
        self.pos_embed = nn.Parameter(torch.randn(1, max_users, d_model) * 0.02)

        # Pre-LN Transformer encoder for cross-user interaction
        # norm_first=True is CRITICAL: Post-LN Transformers are extremely
        # hard to train from scratch with small data.
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_ff,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,        # ← Pre-LN for stable training
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers,
        )

        # Shared classification head applied to each user token
        self.cls_head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, num_classes),
        )

        # Initialise weights
        self._init_weights()

    def _init_weights(self):
        """Xavier init for linear layers, zeros for biases."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor, mask: torch.Tensor = None):
        """
        Parameters
        ----------
        x    : (B, 5*max_users)
        mask : (B, max_users)  — 1.0 = active user, 0.0 = padding

        Returns
        -------
        list of max_users tensors, each (B, NUM_CLASSES)  — compatible with
        the existing training loop.
        """
        B = x.size(0)

        # Reshape flat vector → sequence of user tokens: (B, N, 5)
        tokens = x.view(B, self.max_users, FEATURES_PER_USER)

        # Per-user MLP encoding + positional embedding
        tokens = self.user_encoder(tokens) + self.pos_embed     # (B, N, d)

        # Build padding mask for the Transformer (True = IGNORE)
        pad_mask = None
        if mask is not None:
            pad_mask = (mask == 0.0)  # (B, N), True where padded

        # Self-attention across users
        encoded = self.encoder(tokens, src_key_padding_mask=pad_mask)  # (B, N, d)

        # Shared classification head
        logits = self.cls_head(encoded)  # (B, N, C)

        # Return as list[Tensor(B,C)] for backward-compat with training loop
        return logits.unbind(dim=1)


# ---------------------------------------------------------------------------
# LR schedule: linear warmup + cosine decay
# ---------------------------------------------------------------------------
def _warmup_cosine_schedule(optimizer, warmup_steps, total_steps):
    """Returns a LambdaLR scheduler with linear warmup then cosine decay."""
    def lr_lambda(step):
        if step < warmup_steps:
            return float(step) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
        return 0.5 * (1.0 + math.cos(math.pi * progress))
    return optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


# ---------------------------------------------------------------------------
# Training  — masked KL loss with warmup + gradient clipping
# ---------------------------------------------------------------------------
def train_model(
    X_train:   pd.DataFrame,
    Y_train:   pd.DataFrame,
    M_train:   pd.DataFrame,
    max_users: int   = MAX_USERS,
    epochs:     int   = 500,
    batch_size: int   = 64,
    lr:         float = 5e-4,
    device:     str   = "cpu",
) -> MultiUserCompressionNet:

    ds     = CompressionDataset(X_train, Y_train, M_train, augment_std=0.25)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)

    model     = MultiUserCompressionNet(max_users).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    total_steps  = epochs * len(loader)
    warmup_steps = min(len(loader) * 30, total_steps // 5)  # ~30 epoch warmup or 20% of total
    scheduler = _warmup_cosine_schedule(optimizer, warmup_steps, total_steps)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Training Transformer ({param_count:,} params)  "
          f"({len(ds):,} samples, {epochs} epochs, warmup={warmup_steps} steps)...")

    global_step = 0
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for bX, bY, bM in loader:
            bX, bY, bM = bX.to(device), bY.to(device), bM.to(device)
            optimizer.zero_grad()
            outputs = model(bX, bM)

            loss = 0.0
            total_active = bM.sum().item() + 1e-8  # avoid div by zero
            
            for i in range(max_users):
                log_probs   = F.log_softmax(outputs[i], dim=1)   # (B, C)
                soft_target = make_soft_labels(bY[:, i], NUM_CLASSES,
                                               LABEL_SMOOTH_STD)  # (B, C)
                
                # Unreduced KL div across class dim: sum per sample
                head_loss = F.kl_div(log_probs, soft_target, reduction="none").sum(dim=1)  # (B,)
                
                # Apply mask: only active slots contribute to gradient
                masked_loss = (head_loss * bM[:, i]).sum()
                loss += masked_loss

            # Normalize loss to the number of active sample heads
            loss = loss / total_active
            
            loss.backward()
            # Gradient clipping — prevents attention weight explosions
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            global_step += 1
            total_loss += loss.item()

        if epoch % 50 == 0 or epoch == 1:
            current_lr = optimizer.param_groups[0]['lr']
            print(f"  Epoch {epoch:4d}/{epochs} | loss={total_loss/len(loader):.4f} | lr={current_lr:.2e}")

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
            outputs = model(bX, bM)
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
    raw_state: list,     # un-scaled [e80_0, er_0, cqi0, fps0, prev_delay0, e80_1, er_1, cqi1, fps1, prev_delay1, ...]
    num_users: int,
    device:    str = "cpu",
) -> list:
    """Returns component counts for each active user given a raw (un-normalised) state."""
    model.eval()
    
    # Pad input to max_users
    padded_state = raw_state.copy()
    for _ in range(num_users, model.max_users):
        padded_state.extend([0.0, 0.0, 0.0, 0.0, 0.0])
        
    arr    = np.array(padded_state, dtype=np.float32).reshape(1, -1)
    
    # Note: Only scale the active features, keep padded features 0
    scaled = np.zeros_like(arr)
    active_features = scaler.transform(arr[:, :5*num_users])
    scaled[:, :5*num_users] = active_features
    
    x      = torch.tensor(scaled, dtype=torch.float32).to(device)

    # Build user mask: 1 for active, 0 for padded
    mask_np = np.zeros((1, model.max_users), dtype=np.float32)
    mask_np[0, :num_users] = 1.0
    mask = torch.tensor(mask_np, dtype=torch.float32).to(device)

    with torch.no_grad():
        outputs = model(x, mask)
        
    # Return predictions only for active users
    return [class_to_components(torch.argmax(outputs[i], dim=1).item()) for i in range(num_users)]


# ---------------------------------------------------------------------------
# Train all configurations
# ---------------------------------------------------------------------------
def train_all(
    csv_path:       str,
    epochs:         int   = 500,
    batch_size:     int   = 64,
    lr:             float = 5e-4,
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
    
    # Scale each feature column independently, preserving 0s (padding)
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
            
    # For compatibility, store a standard scaler fitted globally
    # (the server uses it for inference scaling)
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
        epochs         = 500,
        batch_size     = 64,
        lr             = 5e-4,
        save_dir       = SAVE_DIR,
        device         = DEVICE,
    )