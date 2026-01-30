#!/usr/bin/env python3
"""
Improved Compression Model Training Script

This script trains an XGBoost regressor with improvements:
1. Coarser CQI bins (0.5 instead of 0.05) for more samples per bin
2. Sample weighting to balance compression level distribution
3. Outputs the trained model to compression_model.joblib

Usage:
    cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr
    python3 train_improved_model.py
"""

import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from pathlib import Path

# Configuration
DATASET_PATH = Path(__file__).parent / "compression_dataset.csv"
MODEL_PATH = Path(__file__).parent / "compression_model.joblib"
VALID_COMPRESSION_LEVELS = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80])

# Improved: Use coarser CQI bins (0.5 instead of 0.05)
CQI_BIN_WIDTH = 0.5  # Was 0.05 - increased for more samples per bin

RELIABILITY_THRESHOLD = 0.8  # 80% delay reliability threshold


def snap_to_compression_level(pred: float) -> int:
    """Snap regression output to nearest valid compression level."""
    idx = np.abs(VALID_COMPRESSION_LEVELS - pred).argmin()
    return int(VALID_COMPRESSION_LEVELS[idx])


def find_optimal_compression(group):
    """Find optimal compression for a group: lowest MSE among those meeting reliability threshold."""
    # First, filter for rows meeting reliability threshold
    valid_rows = group[group['delay_reliability'] >= RELIABILITY_THRESHOLD]
    
    if len(valid_rows) > 0:
        # Among reliable compressions, find the one with lowest MSE
        best_row = valid_rows.loc[valid_rows['avg_mse'].idxmin()]
    else:
        # No compression meets threshold, pick highest reliability
        # (to encourage the model to prefer higher reliability)
        best_row = group.loc[group['delay_reliability'].idxmax()]
    
    return best_row['compression_level']


def main():
    print("=" * 60)
    print("IMPROVED COMPRESSION MODEL TRAINING")
    print("=" * 60)
    
    # Load dataset
    print(f"\nLoading dataset from {DATASET_PATH}...")
    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} samples")
    print(f"Columns: {list(df.columns)}")
    print(f"CQI range: {df['avg_cqi'].min():.2f} - {df['avg_cqi'].max():.2f}")
    
    # Create CQI bins with IMPROVED width (0.5 instead of 0.05)
    cqi_min = df['avg_cqi'].min()
    cqi_max = df['avg_cqi'].max()
    
    cqi_bins = np.arange(np.floor(cqi_min * 2) / 2, np.ceil(cqi_max * 2) / 2 + CQI_BIN_WIDTH, CQI_BIN_WIDTH)
    cqi_labels = [f"{cqi_bins[i]:.1f}-{cqi_bins[i+1]:.1f}" for i in range(len(cqi_bins)-1)]
    
    df['cqi_bin'] = pd.cut(df['avg_cqi'], bins=cqi_bins, labels=cqi_labels, include_lowest=True)
    
    print(f"\nCQI bin width: {CQI_BIN_WIDTH} (improved from 0.05)")
    print(f"CQI bin edges: {cqi_bins}")
    print(f"CQI bin distribution:\n{df['cqi_bin'].value_counts().sort_index()}")
    
    # Aggregate by (num_users, cqi_bin, compression_level)
    scenario_agg = df.groupby(['num_users', 'cqi_bin', 'compression_level'], observed=True).agg({
        'delay_reliability': 'mean',
        'avg_mse': 'mean',
        'avg_cqi': 'mean',
        'run_id': 'count'
    }).rename(columns={'run_id': 'sample_count'}).reset_index()
    
    print(f"\nAggregated scenarios: {len(scenario_agg)}")
    
    # Find optimal compression per (num_users, cqi_bin)
    optimal_map = {}
    
    for (num_users, cqi_bin), group in scenario_agg.groupby(['num_users', 'cqi_bin'], observed=True):
        optimal_comp = find_optimal_compression(group)
        cqi_midpoint = group['avg_cqi'].mean()
        optimal_map[(num_users, cqi_bin)] = {
            'optimal_compression': optimal_comp,
            'cqi_midpoint': cqi_midpoint,
            'num_users': num_users
        }
    
    print(f"\nOptimal compression computed for {len(optimal_map)} (num_users, cqi_bin) combinations")
    
    # Build training dataset
    training_data = []
    for key, val in optimal_map.items():
        training_data.append({
            'num_users': val['num_users'],
            'cqi_midpoint': val['cqi_midpoint'],
            'optimal_compression': val['optimal_compression']
        })
    
    train_df = pd.DataFrame(training_data)
    
    print(f"\nTraining dataset size: {len(train_df)}")
    print(f"Optimal compression distribution:\n{train_df['optimal_compression'].value_counts().sort_index()}")
    
    # Prepare features and target
    X = train_df[['num_users', 'cqi_midpoint']].values
    y = train_df['optimal_compression'].values
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # IMPROVED: Calculate sample weights to balance compression distribution
    from sklearn.utils.class_weight import compute_sample_weight
    sample_weights = compute_sample_weight('balanced', y_train)
    
    print(f"\nSample weights computed (min: {sample_weights.min():.2f}, max: {sample_weights.max():.2f})")
    
    # Train XGBoost with sample weights
    model = XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1
    )
    
    print("\nTraining XGBoost with sample weighting...")
    model.fit(X_train, y_train, sample_weight=sample_weights)
    print("Model trained successfully!")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='neg_mean_absolute_error')
    print(f"Cross-validation MAE: {-cv_scores.mean():.2f} (+/- {cv_scores.std() * 2:.2f})")
    
    # Evaluate on test set
    y_pred_raw = model.predict(X_test)
    y_pred_snapped = np.array([snap_to_compression_level(p) for p in y_pred_raw])
    
    mae = mean_absolute_error(y_test, y_pred_snapped)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred_snapped))
    r2 = r2_score(y_test, y_pred_snapped)
    
    print(f"\n{'='*60}")
    print("MODEL EVALUATION (Test Set)")
    print(f"{'='*60}")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R² Score: {r2:.3f}")
    
    # Show sample predictions
    print(f"\nSample predictions:")
    for i in range(min(10, len(X_test))):
        print(f"  Users={int(X_test[i,0])}, CQI={X_test[i,1]:.2f} -> Predicted={y_pred_snapped[i]}, Actual={y_test[i]}")
    
    # Show prediction distribution
    print(f"\nPrediction distribution:")
    unique, counts = np.unique(y_pred_snapped, return_counts=True)
    for u, c in zip(unique, counts):
        print(f"  Compression {int(u)}: {c} predictions")
    
    # Save model
    print(f"\nSaving model to {MODEL_PATH}...")
    joblib.dump(model, MODEL_PATH)
    print("Model saved successfully!")
    
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
