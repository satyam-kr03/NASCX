#!/usr/bin/env python3
"""
Multi-Output Surrogate Neural Network for XR Compression.

Architecture (one model per N):
    Input  : [cqi_0, fps_0, complexity_0, cl_0,
               cqi_1, fps_1, complexity_1, cl_1,
               ...
               cqi_N, fps_N, complexity_N, cl_N]   shape: (N*4,)
    Hidden : shared MLP layers  (128 → 64 → 32)
    Output : [mse_0, mse_1, ..., mse_N]             shape: (N,)

At inference time:
    - Fix the observed state (cqi, fps, complexity per user)
    - Sweep candidate compression level combinations
    - Pick the joint assignment minimising sum of predicted MSEs

Key data decisions:
    - Rows where compression_level == 0 are dropped
      (these are unscheduled frames — no meaningful action was taken)
    - MSE target is log-transformed to compress the 14–1433 range
      and reduce the dominance of the 1000-penalty outliers
    - All inputs are standardised (zero mean, unit variance)
    - 80/20 train/val split, stratified by compression_level bins
      to ensure all compression levels appear in both splits
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib

# ── Configuration ─────────────────────────────────────────────────────────────

COMPRESSION_LEVELS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]

# Features used per user (in this exact order)
PER_USER_FEATURES = ['avg_cqi', 'fps', 'frame_complexity', 'compression_level']

# Targets per user
PER_USER_TARGETS = ['mse']

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_and_pivot(csv_path: Path, num_users: int) -> pd.DataFrame:
    """
    Load CSV. Handles two formats:
      A) Wide format (one row per frame, already pivoted)
         — output of generate_surrogate_dataset.py
         — columns: fps_0, avg_cqi_0, ..., mse_0, fps_1, ...
      B) Long format (one row per user per frame)
         — original per_frame_dataset.csv
         — columns: user_id, fps, avg_cqi, ..., mse
    Auto-detects format from column names.
    """
    df = pd.read_csv(csv_path)

    # Detect format
    if f'fps_0' in df.columns:
        # Already wide — just filter to correct num_users
        if 'num_users' in df.columns:
            df = df[df['num_users'] == num_users].copy()
        print(f"  Wide format detected. {len(df)} rows after filtering num_users={num_users}.")
        return df

    # Long format — pivot
    print("  Long format detected. Pivoting...")
    sub = df[df['num_users'] == num_users].copy()
    run_id = int(sub['run_id'].iloc[0])
    sub = sub[sub['run_id'] == run_id].copy()

    counts   = sub.groupby('frame_number')['user_id'].nunique()
    complete = counts[counts == num_users].index
    sub      = sub[sub['frame_number'].isin(complete)]

    rows = []
    for fn, grp in sub.groupby('frame_number'):
        grp = grp.set_index('user_id')
        row: Dict = {'run_id': run_id, 'num_users': num_users, 'frame_number': fn}
        for i in range(num_users):
            if i not in grp.index:
                continue
            u = grp.loc[i]
            row[f'fps_{i}']               = u['fps']
            row[f'avg_cqi_{i}']           = u['avg_cqi']
            row[f'frame_complexity_{i}']  = u['frame_complexity']
            row[f'compression_level_{i}'] = u['compression_level']
            row[f'mse_{i}']               = u['mse']
            row[f'delay_ms_{i}']          = u['delay_ms']
            row[f'received_on_time_{i}']  = u['received_on_time']
        rows.append(row)

    wide = pd.DataFrame(rows)
    print(f"  Pivoted to {len(wide)} frame snapshots.")
    return wide


def clean(df: pd.DataFrame, num_users: int) -> pd.DataFrame:
    """
    Drop rows where ANY user has compression_level == 0.
    These are unscheduled / lost frames where no compression
    decision was actually made — not meaningful training samples.
    Also drop rows where frame_complexity == 0 for any user
    (frames that were never generated in the traffic file).
    """
    before = len(df)
    for u in range(num_users):
        df = df[df[f'compression_level_{u}'] != 0]
        df = df[df[f'frame_complexity_{u}']  != 0]
    print(f"  Cleaned: {before} → {len(df)} rows "
          f"(dropped {before - len(df)} unscheduled/empty frames)")
    return df.reset_index(drop=True)


def build_arrays(df: pd.DataFrame, num_users: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build input matrix X  (n_samples, num_users * 4)
    and target matrix  y  (n_samples, num_users)

    Input features per user: [avg_cqi, fps, frame_complexity, compression_level]
    Target per user:          log(mse)   — log-transform to compress scale
    """
    X_parts, y_parts = [], []
    for u in range(num_users):
        feats = df[[f'avg_cqi_{u}', f'fps_{u}',
                    f'frame_complexity_{u}', f'compression_level_{u}']].values
        X_parts.append(feats)

        mse = df[f'mse_{u}'].values
        y_parts.append(np.log1p(mse).reshape(-1, 1))   # log(1+mse) for stability

    X = np.hstack(X_parts).astype(np.float32)          # (N, num_users*4)
    y = np.hstack(y_parts).astype(np.float32)          # (N, num_users)
    return X, y


def split_data(X: np.ndarray, y: np.ndarray, df: pd.DataFrame,
               num_users: int, val_frac: float = 0.2, seed: int = 42):
    """
    80/20 split stratified on compression_level bins.
    We bin user 0's compression level to ensure all levels appear in both
    train and val — important since with limited data, random splits
    might leave some levels only in one partition.
    """
    cl_bins = pd.cut(df['compression_level_0'], bins=4, labels=False)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=val_frac, random_state=seed, stratify=cl_bins
    )
    print(f"  Train: {len(X_train)} samples | Val: {len(X_val)} samples")
    return X_train, X_val, y_train, y_val


def augment_user_permutations(X: np.ndarray, y: np.ndarray,
                               num_users: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Augment training data by permuting user positions.
    For N=3 users this generates 3! = 6 versions of each sample
    (including the identity).  This removes positional bias —
    the model learns that user slot 0 vs 1 vs 2 is arbitrary.
    """
    from itertools import permutations
    n_feat = len(PER_USER_FEATURES)               # 4
    perms  = list(permutations(range(num_users)))

    X_aug, y_aug = [], []
    for perm in perms:
        x_blocks = [X[:, u * n_feat:(u + 1) * n_feat] for u in perm]
        X_aug.append(np.hstack(x_blocks))
        y_aug.append(y[:, list(perm)])

    X_out = np.vstack(X_aug).astype(np.float32)
    y_out = np.vstack(y_aug).astype(np.float32)
    print(f"  Augmented: {len(X)} → {len(X_out)} samples "
          f"({len(perms)} user permutations)")
    return X_out, y_out


# ── Dataset ───────────────────────────────────────────────────────────────────

class SurrogateDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.from_numpy(X)
        self.y = torch.from_numpy(y)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# ── Model ─────────────────────────────────────────────────────────────────────

class SurrogateNet(nn.Module):
    """
    Multi-output MLP surrogate.

    Architecture:
        Input (num_users * 4)
            ↓
        Linear(input_dim, 128) + BatchNorm + ReLU + Dropout
            ↓
        Linear(128, 64) + BatchNorm + ReLU + Dropout
            ↓
        Linear(64, 32) + BatchNorm + ReLU
            ↓
        Linear(32, num_users)   ← one output per user (log-MSE)

    BatchNorm helps stabilise training when input features have very
    different scales (CQI ~14, fps ~60-120, complexity ~80k-180k).
    Dropout provides regularisation given the limited dataset size.
    """
    def __init__(self, num_users: int, dropout: float = 0.2):
        super().__init__()
        input_dim  = num_users * 4
        output_dim = num_users

        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),

            nn.Linear(32, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ── Training ──────────────────────────────────────────────────────────────────

def train(model: nn.Module,
          train_loader: DataLoader,
          val_loader: DataLoader,
          epochs: int,
          lr: float,
          patience: int,
          device: torch.device,
          save_path: Path) -> Dict:

    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimiser, mode='min', factor=0.5, patience=patience // 3
    )
    criterion = nn.HuberLoss(delta=1.0)  # Robust to outliers in log-MSE space

    best_val_loss  = float('inf')
    no_improve     = 0
    history        = {'train_loss': [], 'val_loss': []}

    print(f"\n{'Epoch':>6}  {'Train Loss':>12}  {'Val Loss':>12}  {'LR':>10}")
    print("-" * 48)

    for epoch in range(1, epochs + 1):
        # ── Train ──
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimiser.zero_grad()
            pred = model(X_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimiser.step()
            train_loss += loss.item() * len(X_batch)
        train_loss /= len(train_loader.dataset)

        # ── Validate ──
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                pred     = model(X_batch)
                val_loss += criterion(pred, y_batch).item() * len(X_batch)
        val_loss /= len(val_loader.dataset)

        scheduler.step(val_loss)
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        lr_now = optimiser.param_groups[0]['lr']

        if epoch % 10 == 0 or epoch == 1:
            print(f"{epoch:>6}  {train_loss:>12.6f}  {val_loss:>12.6f}  {lr_now:>10.2e}")

        # ── Early stopping ──
        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            no_improve    = 0
            torch.save(model.state_dict(), save_path)
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"\n  Early stopping at epoch {epoch} "
                      f"(no improvement for {patience} epochs)")
                break

    print(f"\n  Best val loss: {best_val_loss:.6f}  →  saved to {save_path}")
    return history


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(model: nn.Module, val_loader: DataLoader,
             scaler_y: StandardScaler, device: torch.device,
             num_users: int) -> None:
    """
    Report per-user MAE in original MSE space (after inverting log transform).
    This gives an intuitive sense of prediction quality.
    """
    model.eval()
    preds_log, targets_log = [], []

    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            preds_log.append(model(X_batch.to(device)).cpu().numpy())
            targets_log.append(y_batch.numpy())

    preds_scaled   = np.vstack(preds_log)
    targets_scaled = np.vstack(targets_log)

    # Inverse target standardisation, then invert log1p
    if scaler_y is not None:
        preds_log   = scaler_y.inverse_transform(preds_scaled)
        targets_log = scaler_y.inverse_transform(targets_scaled)
    else:
        preds_log, targets_log = preds_scaled, targets_scaled

    preds_mse   = np.expm1(preds_log)
    targets_mse = np.expm1(targets_log)

    print("\n=== Per-User Evaluation (original MSE scale) ===")
    for u in range(num_users):
        mae  = np.mean(np.abs(preds_mse[:, u] - targets_mse[:, u]))
        rmse = np.sqrt(np.mean((preds_mse[:, u] - targets_mse[:, u]) ** 2))
        # Correlation between predicted and actual MSE
        corr = np.corrcoef(preds_mse[:, u], targets_mse[:, u])[0, 1]
        print(f"  User {u}: MAE = {mae:7.2f}  RMSE = {rmse:7.2f}  Corr = {corr:.4f}")


# ── Inference demo ────────────────────────────────────────────────────────────

def demo_inference(model: nn.Module, scaler_X: StandardScaler,
                   scaler_y: StandardScaler,
                   num_users: int, device: torch.device,
                   example_state: List[Dict]) -> None:
    """
    Show how inference works at decision time.

    example_state: list of dicts, one per user, with keys:
        avg_cqi, fps, frame_complexity
    (compression_level is swept — that's the decision variable)
    """
    model.eval()
    print("\n=== Inference Demo ===")
    print("State:", [{k: v for k, v in u.items()} for u in example_state])
    print(f"Sweeping all {len(COMPRESSION_LEVELS)} compression levels per user...")

    best_total_mse = float('inf')
    best_assignment = None

    # For N=3: 16^3 = 4096 forward passes
    # Vectorised: build all combinations at once for efficiency
    from itertools import product
    combos = list(product(COMPRESSION_LEVELS, repeat=num_users))

    # Build input matrix: (n_combos, num_users * 4)
    rows = []
    for combo in combos:
        row = []
        for u in range(num_users):
            row += [
                example_state[u]['avg_cqi'],
                example_state[u]['fps'],
                example_state[u]['frame_complexity'],
                combo[u],                              # compression level being tested
            ]
        rows.append(row)

    X_all = np.array(rows, dtype=np.float32)
    X_all = scaler_X.transform(X_all)
    X_tensor = torch.from_numpy(X_all).to(device)

    with torch.no_grad():
        pred_scaled = model(X_tensor).cpu().numpy()  # (n_combos, num_users)

    # Inverse target standardisation, then invert log1p
    if scaler_y is not None:
        pred_log = scaler_y.inverse_transform(pred_scaled)
    else:
        pred_log = pred_scaled
    pred_mse   = np.expm1(pred_log)                # back to MSE scale
    total_mse  = pred_mse.sum(axis=1)              # sum across users
    best_idx   = np.argmin(total_mse)
    best_combo = combos[best_idx]

    print(f"\n  Optimal compression assignment:")
    for u in range(num_users):
        print(f"    User {u}: level={best_combo[u]:2d}  "
              f"(predicted MSE = {pred_mse[best_idx, u]:.2f})")
    print(f"  Total predicted MSE: {total_mse[best_idx]:.2f}")

    # Also show top-5 assignments
    top5_idx = np.argsort(total_mse)[:5]
    print(f"\n  Top-5 joint assignments by total MSE:")
    for rank, idx in enumerate(top5_idx, 1):
        levels = combos[idx]
        print(f"    #{rank}: levels={levels}  total_MSE={total_mse[idx]:.2f}  "
              f"per-user={[f'{pred_mse[idx,u]:.1f}' for u in range(num_users)]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Train surrogate NN for XR compression"
    )
    parser.add_argument("--data",       type=Path, required=True,
                        help="Path to dataset CSV (wide or long format)")
    parser.add_argument("--num-users",  type=int,  default=3)
    parser.add_argument("--epochs",     type=int,  default=300)
    parser.add_argument("--batch-size", type=int,  default=128)
    parser.add_argument("--lr",         type=float, default=3e-3)
    parser.add_argument("--dropout",    type=float, default=0.15)
    parser.add_argument("--patience",   type=int,  default=50)
    parser.add_argument("--seed",       type=int,  default=42)
    parser.add_argument("--out-dir",    type=Path, default=Path("models"))
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model_path  = args.out_dir / f"surrogate_n{args.num_users}.pt"
    scaler_path = args.out_dir / f"scaler_n{args.num_users}.pkl"

    # ── Load & prepare data ──
    print(f"\n[1/7] Loading data from {args.data}")
    df = load_and_pivot(args.data, args.num_users)

    print(f"\n[2/7] Cleaning")
    df = clean(df, args.num_users)

    print(f"\n[3/7] Building arrays")
    X, y = build_arrays(df, args.num_users)
    print(f"  X shape: {X.shape}  (input_dim = {args.num_users}×4 = {args.num_users*4})")
    print(f"  y shape: {y.shape}  (output_dim = {args.num_users})")
    print(f"  y (log-MSE) range: [{y.min():.3f}, {y.max():.3f}]")

    # Split BEFORE scaling (avoids data leakage)
    X_train, X_val, y_train, y_val = split_data(X, y, df, args.num_users)

    # Normalise inputs — fit on train only
    scaler_X = StandardScaler()
    X_train = scaler_X.fit_transform(X_train).astype(np.float32)
    X_val   = scaler_X.transform(X_val).astype(np.float32)
    joblib.dump(scaler_X, scaler_path)
    print(f"  Input scaler saved → {scaler_path}")

    # Normalise targets — fit on train only
    scaler_y = StandardScaler()
    y_train = scaler_y.fit_transform(y_train).astype(np.float32)
    y_val   = scaler_y.transform(y_val).astype(np.float32)
    scaler_y_path = args.out_dir / f"scaler_y_n{args.num_users}.pkl"
    joblib.dump(scaler_y, scaler_y_path)
    print(f"  Target scaler saved → {scaler_y_path}")

    # Augment training data with user permutations
    print(f"\n[4/7] Augmenting training data")
    X_train, y_train = augment_user_permutations(X_train, y_train, args.num_users)

    train_ds = SurrogateDataset(X_train, y_train)
    val_ds   = SurrogateDataset(X_val,   y_val)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=args.batch_size)

    # ── Build model ──
    print(f"\n[5/7] Training  (epochs={args.epochs}, lr={args.lr}, "
          f"patience={args.patience})")
    model = SurrogateNet(args.num_users, dropout=args.dropout).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Parameters: {total_params:,}")
    print(f"  Architecture: {args.num_users*4} → 128 → 64 → 32 → {args.num_users}")

    history = train(model, train_dl, val_dl,
                    args.epochs, args.lr, args.patience,
                    device, model_path)

    # ── Evaluate ──
    print(f"\n[6/7] Evaluation")
    model.load_state_dict(torch.load(model_path, map_location=device))
    evaluate(model, val_dl, scaler_y, device, args.num_users)

    # ── Inference demo ──
    # Use the first complete frame from validation set as example
    demo_state = []
    for u in range(args.num_users):
        demo_state.append({
            'avg_cqi':          float(df[f'avg_cqi_{u}'].iloc[0]),
            'fps':              float(df[f'fps_{u}'].iloc[0]),
            'frame_complexity': float(df[f'frame_complexity_{u}'].iloc[0]),
        })
    # ── Inference demo ──
    print(f"\n[7/7] Inference demo")
    demo_inference(model, scaler_X, scaler_y, args.num_users, device, demo_state)

    # Save loss history
    history_path = args.out_dir / f"history_n{args.num_users}.csv"
    pd.DataFrame(history).to_csv(history_path, index=False)
    print(f"\nLoss history → {history_path}")
    print(f"Done.")


if __name__ == "__main__":
    main()