#!/usr/bin/env python3
"""
Dynamic Per-Frame Compression Model Training

This script trains an XGBoost model that predicts per-frame compression levels
based on frame-level features, unlike the static model which predicts one
compression level per user session.

Features:
  - num_users: Number of users in the cell
  - cqi: Channel Quality Indicator for the user
  - fps: Frame rate
  - frame_complexity: Frame size at max components (inherent difficulty)

Target:
  - optimal_compression: Per-frame optimal compression level

The model learns that large/complex frames need more aggressive compression
to meet delivery deadlines, while simpler frames can afford less compression
(higher quality).

Usage:
    cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr
    python3 train_dynamic_model.py
"""

import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path

# Configuration
DATASET_PATH = Path(__file__).parent / "datasets" / "per_frame_dataset.csv"
MODEL_PATH = Path(__file__).parent / "models" / "compression_model_dynamic.joblib"
VALID_COMPRESSION_LEVELS = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80])

# Binning parameters
CQI_BIN_WIDTH = 0.5
COMPLEXITY_NUM_BINS = 10  # Quantile-based bins for frame complexity

RELIABILITY_THRESHOLD = 0.8  # 80% on-time rate to consider a compression reliable

# Feature columns for the dynamic model
FEATURE_COLUMNS = ['num_users', 'cqi', 'fps', 'frame_complexity']


def snap_to_compression_level(pred: float) -> int:
    """Snap regression output to nearest valid compression level."""
    idx = np.abs(VALID_COMPRESSION_LEVELS - pred).argmin()
    return int(VALID_COMPRESSION_LEVELS[idx])


def find_per_frame_optimal(group):
    """Find optimal compression for a group of similar frames.
    
    The input `group` is a sub-DataFrame of scenario_agg, which already has
    one row per compression_level with columns: on_time_rate, avg_mse, etc.
    
    Among compression levels with on-time rate >= threshold,
    select the one with lowest MSE (best quality).
    If none meet the threshold, pick the one with highest on-time rate.
    """
    # group already has one row per compression_level from scenario_agg
    stats = group[['compression_level', 'on_time_rate', 'avg_mse']].copy()
    
    # Filter: must meet reliability threshold
    reliable = stats[stats['on_time_rate'] >= RELIABILITY_THRESHOLD]
    
    if len(reliable) > 0:
        # Best quality among reliable options (lowest MSE)
        return int(reliable.loc[reliable['avg_mse'].idxmin(), 'compression_level'])
    else:
        # Fallback: pick the compression level with highest on-time rate
        return int(stats.loc[stats['on_time_rate'].idxmax(), 'compression_level'])


def main():
    print("=" * 60)
    print("DYNAMIC PER-FRAME COMPRESSION MODEL TRAINING")
    print("=" * 60)
    
    # Load dataset
    print(f"\nLoading per-frame dataset from {DATASET_PATH}...")
    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} per-frame samples")
    print(f"Columns: {list(df.columns)}")
    
    # Filter out lost frames (components=0) — they don't have valid compression info
    df = df[df['compression_level'] > 0].copy()
    print(f"After filtering lost frames: {len(df)} samples")
    
    # Data statistics
    print(f"\nData Statistics:")
    print(f"  CQI range:          {df['avg_cqi'].min():.2f} - {df['avg_cqi'].max():.2f}")
    print(f"  FPS values:         {sorted(df['fps'].unique())}")
    print(f"  Num users range:    {df['num_users'].min()} - {df['num_users'].max()}")
    print(f"  Frame complexity:   {df['frame_complexity'].min():.0f} - {df['frame_complexity'].max():.0f} bytes")
    print(f"  Compression levels: {sorted(df['compression_level'].unique())}")
    print(f"  Overall on-time:    {df['received_on_time'].mean()*100:.1f}%")
    
    # Create bins for grouping similar frames
    print(f"\nCreating feature bins...")
    
    # CQI bins  
    cqi_min, cqi_max = df['avg_cqi'].min(), df['avg_cqi'].max()
    cqi_bins = np.arange(
        np.floor(cqi_min * 2) / 2,
        np.ceil(cqi_max * 2) / 2 + CQI_BIN_WIDTH,
        CQI_BIN_WIDTH
    )
    df['cqi_bin'] = pd.cut(df['avg_cqi'], bins=cqi_bins, include_lowest=True)
    
    # Frame complexity bins (quantile-based for balanced coverage)
    df['complexity_bin'] = pd.qcut(df['frame_complexity'], q=COMPLEXITY_NUM_BINS,
                                    duplicates='drop')
    
    print(f"  CQI bins: {len(cqi_bins)-1} bins (width={CQI_BIN_WIDTH})")
    print(f"  Complexity bins: {df['complexity_bin'].nunique()} bins (quantile-based)")
    print(f"\n  CQI bin distribution:\n{df['cqi_bin'].value_counts().sort_index().head(10)}")
    print(f"\n  Complexity bin distribution:\n{df['complexity_bin'].value_counts().sort_index().head(10)}")
    
    # Group by (num_users, cqi_bin, fps, complexity_bin, compression_level)
    # and compute on-time rate and avg MSE per group
    group_cols = ['num_users', 'cqi_bin', 'fps', 'complexity_bin', 'compression_level']
    scenario_agg = df.groupby(group_cols, observed=True).agg(
        on_time_rate=('received_on_time', 'mean'),
        avg_mse=('mse', 'mean'),
        avg_cqi=('avg_cqi', 'mean'),
        avg_complexity=('frame_complexity', 'mean'),
        sample_count=('received_on_time', 'count')
    ).reset_index()
    
    print(f"\nAggregated scenarios: {len(scenario_agg)}")
    
    # Find optimal compression per (num_users, cqi_bin, fps, complexity_bin)
    label_group_cols = ['num_users', 'cqi_bin', 'fps', 'complexity_bin']
    
    training_rows = []
    for group_key, group in scenario_agg.groupby(label_group_cols, observed=True):
        optimal_comp = find_per_frame_optimal(group)
        
        training_rows.append({
            'num_users': group_key[0],
            'cqi': group['avg_cqi'].mean(),
            'fps': group_key[2],
            'frame_complexity': group['avg_complexity'].mean(),
            'optimal_compression': optimal_comp
        })
    
    train_df = pd.DataFrame(training_rows)
    print(f"Training scenarios: {len(train_df)}")
    print(f"\nOptimal compression distribution:")
    print(train_df['optimal_compression'].value_counts().sort_index())
    
    # Prepare features and target
    X = train_df[FEATURE_COLUMNS].values
    y = train_df['optimal_compression'].values
    
    print(f"\nFeatures: {FEATURE_COLUMNS}")
    print(f"Feature matrix shape: {X.shape}")
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Sample weights to balance compression distribution
    from sklearn.utils.class_weight import compute_sample_weight
    sample_weights = compute_sample_weight('balanced', y_train)
    print(f"Sample weights: min={sample_weights.min():.2f}, max={sample_weights.max():.2f}")
    
    # Train XGBoost
    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.08,
        min_child_weight=2,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    
    print("\nTraining XGBoost with sample weighting...")
    model.fit(X_train, y_train, sample_weight=sample_weights)
    print("Model trained successfully!")
    
    # Feature importance
    print(f"\nFeature Importance:")
    for feat, imp in zip(FEATURE_COLUMNS, model.feature_importances_):
        bar = "█" * int(imp * 40)
        print(f"  {feat:25s}: {imp:.4f} {bar}")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='neg_mean_absolute_error')
    print(f"\nCross-validation MAE: {-cv_scores.mean():.2f} (+/- {cv_scores.std() * 2:.2f})")
    
    # Evaluate on test set
    y_pred_raw = model.predict(X_test)
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
    
    # Show sample predictions
    print(f"\nSample predictions:")
    X_test_orig = scaler.inverse_transform(X_test)
    for i in range(min(10, len(X_test))):
        print(f"  Users={int(X_test_orig[i,0])}, CQI={X_test_orig[i,1]:.1f}, "
              f"FPS={int(X_test_orig[i,2])}, Complexity={X_test_orig[i,3]:.0f}B -> "
              f"Pred={y_pred_snapped[i]}, Actual={y_test[i]}")
    
    # Analyze: does the model compress more for complex frames?
    print(f"\n{'='*60}")
    print("ADAPTIVITY ANALYSIS")
    print(f"{'='*60}")
    
    # Create test scenarios with varying complexity at fixed conditions
    test_complexities = np.linspace(X_test_orig[:, 3].min(), X_test_orig[:, 3].max(), 8)
    fixed_users = 5
    fixed_cqi = X_test_orig[:, 1].mean()
    fixed_fps = 60
    
    print(f"\nPredicted compression at fixed conditions "
          f"(users={fixed_users}, CQI={fixed_cqi:.1f}, FPS={fixed_fps}):")
    print(f"  {'Complexity (bytes)':>20s} -> {'Compression':>12s}")
    
    for comp in test_complexities:
        features = np.array([[fixed_users, fixed_cqi, fixed_fps, comp]])
        features_scaled = scaler.transform(features)
        pred = snap_to_compression_level(model.predict(features_scaled)[0])
        print(f"  {comp:>20.0f} -> {pred:>12d}")
    
    # Prediction distribution
    print(f"\nPrediction distribution (test set):")
    unique, counts = np.unique(y_pred_snapped, return_counts=True)
    for u, c in zip(unique, counts):
        print(f"  Compression {int(u):3d}: {c} predictions")
    
    # Save model
    print(f"\n{'='*60}")
    print(f"Saving model to {MODEL_PATH}...")
    joblib.dump({
        'model': model,
        'scaler': scaler,
        'feature_columns': FEATURE_COLUMNS,
        'valid_compression_levels': VALID_COMPRESSION_LEVELS.tolist(),
        'model_type': 'per_frame'
    }, MODEL_PATH)
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
