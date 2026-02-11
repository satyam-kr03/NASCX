#!/usr/bin/env python3
"""
Dynamic Per-Frame Compression Model Training — Neural Network

This script trains a PyTorch neural network (MLP with residual connections)
that predicts per-frame compression levels based on frame-level features.
It is a drop-in replacement for train_dynamic_model.py which uses XGBoost.

Features:
  - num_users: Number of users in the cell
  - cqi: Channel Quality Indicator for the user
  - fps: Frame rate
  - frame_complexity: Frame size at max components (inherent difficulty)

Target:
  - optimal_compression: Per-frame optimal compression level

Architecture:
  - Multi-layer perceptron with residual (skip) connections
  - Batch normalization + dropout for regularization
  - GELU activations for smoother gradients
  - Learning rate scheduling with ReduceLROnPlateau

The saved model is wrapped in a sklearn-compatible predictor so it can be
loaded identically to the XGBoost version by model_server.py.

Usage:
    cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr
    python3 train_dynamic_model_nn.py
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
import joblib
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATASET_PATH = Path(__file__).parent / "datasets" / "per_frame_dataset.csv"
MODEL_PATH = Path(__file__).parent / "models" / "compression_model_dynamic.joblib"
VALID_COMPRESSION_LEVELS = np.array(
    [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
)

# Binning parameters (same as XGBoost version)
CQI_BIN_WIDTH = 0.5
COMPLEXITY_NUM_BINS = 10
RELIABILITY_THRESHOLD = 0.8

FEATURE_COLUMNS = ['num_users', 'cqi', 'fps', 'frame_complexity']

# Training hyper-parameters
HIDDEN_DIMS = [128, 256, 256, 128]   # MLP layer widths
DROPOUT = 0.25
BATCH_SIZE = 64
EPOCHS = 200
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE = 25  # Early-stopping patience (epochs)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------
class ResidualBlock(nn.Module):
    """A single residual block: Linear → BN → GELU → Dropout, with a skip."""

    def __init__(self, dim: int, dropout: float = 0.25):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )
        self.act = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.net(x) + x)  # skip connection


class CompressionMLP(nn.Module):
    """
    Multi-layer perceptron with residual connections for compression prediction.

    Input  →  Linear(in→h₁)  →  [ResidualBlock(h)]* per hidden dim
           →  Linear(h_last→1)  →  scalar output
    """

    def __init__(
        self,
        in_features: int = 4,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.25,
    ):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [128, 256, 256, 128]

        layers: list[nn.Module] = []

        # Input projection
        prev_dim = in_features
        for h_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, h_dim))
            layers.append(nn.BatchNorm1d(h_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
            # Add a residual block at this width
            layers.append(ResidualBlock(h_dim, dropout))
            prev_dim = h_dim

        self.backbone = nn.Sequential(*layers)
        self.head = nn.Linear(prev_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.backbone(x)).squeeze(-1)


# ---------------------------------------------------------------------------
# Sklearn-compatible wrapper (so model_server.py can call .predict())
# ---------------------------------------------------------------------------
class TorchPredictor:
    """Wraps a PyTorch model to expose a sklearn-style .predict(X) method."""

    def __init__(self, model: nn.Module, device: torch.device):
        self.model = model
        self.device = device

    def predict(self, X: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            tensor = torch.tensor(X, dtype=torch.float32, device=self.device)
            preds = self.model(tensor).cpu().numpy()
        return preds


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def snap_to_compression_level(pred: float) -> int:
    """Snap regression output to nearest valid compression level."""
    idx = np.abs(VALID_COMPRESSION_LEVELS - pred).argmin()
    return int(VALID_COMPRESSION_LEVELS[idx])


def find_per_frame_optimal(group):
    """Find optimal compression for a group of similar frames.

    Among compression levels with on-time rate >= threshold, select the one
    with lowest MSE (best quality). If none meet the threshold, pick the one
    with highest on-time rate.
    """
    stats = group[['compression_level', 'on_time_rate', 'avg_mse']].copy()
    reliable = stats[stats['on_time_rate'] >= RELIABILITY_THRESHOLD]

    if len(reliable) > 0:
        return int(reliable.loc[reliable['avg_mse'].idxmin(), 'compression_level'])
    else:
        return int(stats.loc[stats['on_time_rate'].idxmax(), 'compression_level'])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("DYNAMIC PER-FRAME COMPRESSION MODEL TRAINING  [Neural Net]")
    print("=" * 60)
    print(f"Device: {DEVICE}")

    # ------------------------------------------------------------------
    # 1. Load & prepare dataset (identical logic to XGBoost version)
    # ------------------------------------------------------------------
    print(f"\nLoading per-frame dataset from {DATASET_PATH}...")
    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} per-frame samples")
    print(f"Columns: {list(df.columns)}")

    df = df[df['compression_level'] > 0].copy()
    print(f"After filtering lost frames: {len(df)} samples")

    print(f"\nData Statistics:")
    print(f"  CQI range:          {df['avg_cqi'].min():.2f} - {df['avg_cqi'].max():.2f}")
    print(f"  FPS values:         {sorted(df['fps'].unique())}")
    print(f"  Num users range:    {df['num_users'].min()} - {df['num_users'].max()}")
    print(f"  Frame complexity:   {df['frame_complexity'].min():.0f} - {df['frame_complexity'].max():.0f} bytes")
    print(f"  Compression levels: {sorted(df['compression_level'].unique())}")
    print(f"  Overall on-time:    {df['received_on_time'].mean()*100:.1f}%")

    # CQI bins
    cqi_min, cqi_max = df['avg_cqi'].min(), df['avg_cqi'].max()
    cqi_bins = np.arange(
        np.floor(cqi_min * 2) / 2,
        np.ceil(cqi_max * 2) / 2 + CQI_BIN_WIDTH,
        CQI_BIN_WIDTH,
    )
    df['cqi_bin'] = pd.cut(df['avg_cqi'], bins=cqi_bins, include_lowest=True)

    # Frame complexity bins
    df['complexity_bin'] = pd.qcut(
        df['frame_complexity'], q=COMPLEXITY_NUM_BINS, duplicates='drop'
    )

    print(f"\nCreating feature bins...")
    print(f"  CQI bins: {len(cqi_bins)-1} bins (width={CQI_BIN_WIDTH})")
    print(f"  Complexity bins: {df['complexity_bin'].nunique()} bins (quantile-based)")

    # Aggregate
    group_cols = ['num_users', 'cqi_bin', 'fps', 'complexity_bin', 'compression_level']
    scenario_agg = df.groupby(group_cols, observed=True).agg(
        on_time_rate=('received_on_time', 'mean'),
        avg_mse=('mse', 'mean'),
        avg_cqi=('avg_cqi', 'mean'),
        avg_complexity=('frame_complexity', 'mean'),
        sample_count=('received_on_time', 'count'),
    ).reset_index()

    print(f"\nAggregated scenarios: {len(scenario_agg)}")

    # Find optimal compression per scenario
    label_group_cols = ['num_users', 'cqi_bin', 'fps', 'complexity_bin']
    training_rows = []
    for group_key, group in scenario_agg.groupby(label_group_cols, observed=True):
        optimal_comp = find_per_frame_optimal(group)
        training_rows.append({
            'num_users': group_key[0],
            'cqi': group['avg_cqi'].mean(),
            'fps': group_key[2],
            'frame_complexity': group['avg_complexity'].mean(),
            'optimal_compression': optimal_comp,
        })

    train_df = pd.DataFrame(training_rows)
    print(f"Training scenarios: {len(train_df)}")
    print(f"\nOptimal compression distribution:")
    print(train_df['optimal_compression'].value_counts().sort_index())

    # ------------------------------------------------------------------
    # 2. Features & scaling
    # ------------------------------------------------------------------
    X = train_df[FEATURE_COLUMNS].values.astype(np.float32)
    y = train_df['optimal_compression'].values.astype(np.float32)

    print(f"\nFeatures: {FEATURE_COLUMNS}")
    print(f"Feature matrix shape: {X.shape}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X).astype(np.float32)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )

    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set:     {len(X_test)} samples")

    # ------------------------------------------------------------------
    # 3. Weighted sampling for class balance
    # ------------------------------------------------------------------
    sample_weights = compute_sample_weight('balanced', y_train)
    sample_weights_t = torch.tensor(sample_weights, dtype=torch.float32)
    sampler = WeightedRandomSampler(
        weights=sample_weights_t, num_samples=len(sample_weights_t), replacement=True
    )

    train_ds = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32),
    )
    test_ds = TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(y_test, dtype=torch.float32),
    )

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, sampler=sampler)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)

    # ------------------------------------------------------------------
    # 4. Build model, optimiser, scheduler
    # ------------------------------------------------------------------
    model = CompressionMLP(
        in_features=len(FEATURE_COLUMNS),
        hidden_dims=HIDDEN_DIMS,
        dropout=DROPOUT,
    ).to(DEVICE)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nModel Architecture:")
    print(model)
    print(f"\nTotal parameters:     {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")

    criterion = nn.SmoothL1Loss()  # Huber loss — robust to outliers
    optimizer = optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=10, verbose=False
    )

    # ------------------------------------------------------------------
    # 5. Training loop with early stopping
    # ------------------------------------------------------------------
    print(f"\nTraining for up to {EPOCHS} epochs (patience={PATIENCE})...")
    print(f"{'Epoch':>6s}  {'Train Loss':>11s}  {'Val Loss':>11s}  {'Val MAE':>8s}  {'LR':>10s}")
    print("-" * 55)

    best_val_loss = float('inf')
    best_model_state = None
    patience_counter = 0

    for epoch in range(1, EPOCHS + 1):
        # — Training —
        model.train()
        train_loss_sum, train_n = 0.0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss_sum += loss.item() * len(xb)
            train_n += len(xb)

        train_loss = train_loss_sum / train_n

        # — Validation —
        model.eval()
        val_loss_sum, val_n = 0.0, 0
        val_preds, val_targets = [], []
        with torch.no_grad():
            for xb, yb in test_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                pred = model(xb)
                loss = criterion(pred, yb)
                val_loss_sum += loss.item() * len(xb)
                val_n += len(xb)
                val_preds.append(pred.cpu().numpy())
                val_targets.append(yb.cpu().numpy())

        val_loss = val_loss_sum / val_n
        val_preds_np = np.concatenate(val_preds)
        val_targets_np = np.concatenate(val_targets)
        val_mae = mean_absolute_error(val_targets_np, val_preds_np)
        current_lr = optimizer.param_groups[0]['lr']

        scheduler.step(val_loss)

        # Print progress every 10 epochs, plus the first and last
        if epoch <= 5 or epoch % 10 == 0 or epoch == EPOCHS:
            print(f"{epoch:6d}  {train_loss:11.4f}  {val_loss:11.4f}  {val_mae:8.2f}  {current_lr:10.6f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\nEarly stopping at epoch {epoch} (best val loss: {best_val_loss:.4f})")
                break

    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f"Restored best model (val loss: {best_val_loss:.4f})")

    # ------------------------------------------------------------------
    # 6. Evaluation
    # ------------------------------------------------------------------
    model.eval()
    with torch.no_grad():
        X_test_t = torch.tensor(X_test, dtype=torch.float32, device=DEVICE)
        y_pred_raw = model(X_test_t).cpu().numpy()

    y_pred_snapped = np.array([snap_to_compression_level(p) for p in y_pred_raw])

    mae = mean_absolute_error(y_test, y_pred_snapped)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred_snapped))
    r2 = r2_score(y_test, y_pred_snapped)

    exact_match = np.mean(y_pred_snapped == y_test)
    within_5 = np.mean(np.abs(y_pred_snapped - y_test) <= 5)
    within_10 = np.mean(np.abs(y_pred_snapped - y_test) <= 10)

    print(f"\n{'='*60}")
    print("MODEL EVALUATION (Test Set)")
    print(f"{'='*60}")
    print(f"MAE:  {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R²:   {r2:.3f}")
    print(f"\nAccuracy Metrics:")
    print(f"  Exact match: {exact_match*100:.1f}%")
    print(f"  Within ±5:   {within_5*100:.1f}%")
    print(f"  Within ±10:  {within_10*100:.1f}%")

    # Sample predictions
    print(f"\nSample predictions:")
    X_test_orig = scaler.inverse_transform(X_test)
    for i in range(min(10, len(X_test))):
        print(
            f"  Users={int(X_test_orig[i,0])}, CQI={X_test_orig[i,1]:.1f}, "
            f"FPS={int(X_test_orig[i,2])}, Complexity={X_test_orig[i,3]:.0f}B -> "
            f"Pred={y_pred_snapped[i]}, Actual={int(y_test[i])}"
        )

    # ------------------------------------------------------------------
    # 7. Adaptivity analysis
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("ADAPTIVITY ANALYSIS")
    print(f"{'='*60}")

    test_complexities = np.linspace(
        X_test_orig[:, 3].min(), X_test_orig[:, 3].max(), 8
    )
    fixed_users = 5
    fixed_cqi = X_test_orig[:, 1].mean()
    fixed_fps = 60

    print(
        f"\nPredicted compression at fixed conditions "
        f"(users={fixed_users}, CQI={fixed_cqi:.1f}, FPS={fixed_fps}):"
    )
    print(f"  {'Complexity (bytes)':>20s} -> {'Compression':>12s}")

    for comp in test_complexities:
        features = np.array([[fixed_users, fixed_cqi, fixed_fps, comp]], dtype=np.float32)
        features_scaled = scaler.transform(features)
        with torch.no_grad():
            t = torch.tensor(features_scaled, dtype=torch.float32, device=DEVICE)
            pred_raw = model(t).cpu().item()
        pred = snap_to_compression_level(pred_raw)
        print(f"  {comp:>20.0f} -> {pred:>12d}")

    # Prediction distribution
    print(f"\nPrediction distribution (test set):")
    unique, counts = np.unique(y_pred_snapped, return_counts=True)
    for u, c in zip(unique, counts):
        print(f"  Compression {int(u):3d}: {c} predictions")

    # ------------------------------------------------------------------
    # 8. Save model (same format as XGBoost for model_server.py compat)
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")

    # Move model to CPU for portable inference
    model.cpu()
    predictor = TorchPredictor(model, device=torch.device("cpu"))

    print(f"Saving model to {MODEL_PATH}...")
    joblib.dump(
        {
            'model': predictor,          # sklearn-compatible .predict()
            'scaler': scaler,
            'feature_columns': FEATURE_COLUMNS,
            'valid_compression_levels': VALID_COMPRESSION_LEVELS.tolist(),
            'model_type': 'per_frame_nn',
            'architecture': {
                'type': 'CompressionMLP',
                'hidden_dims': HIDDEN_DIMS,
                'dropout': DROPOUT,
                'total_params': total_params,
            },
        },
        MODEL_PATH,
    )
    print("Model saved successfully!")

    print(f"\n{'='*60}")
    print("TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\nTo use the model:")
    print(f"  model_data = joblib.load('{MODEL_PATH}')")
    print(f"  model = model_data['model']")
    print(f"  scaler = model_data['scaler']")
    print(f"  X = [[num_users, cqi, fps, frame_complexity]]")
    print(f"  X_scaled = scaler.transform(X)")
    print(f"  pred = snap_to_compression_level(model.predict(X_scaled)[0])")


if __name__ == "__main__":
    main()
