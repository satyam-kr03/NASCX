#!/usr/bin/env python3
"""
Improved Compression Model Training Script

This script trains an XGBoost regressor with improvements:
1. Includes new features: FPS and traffic profile characteristics
2. Coarser CQI bins (0.5 instead of 0.05) for more samples per bin
3. Sample weighting to balance compression level distribution
4. Outputs the trained model to compression_model.joblib

Usage:
    cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr
    python3 train_improved_model.py
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
DATASET_PATH = Path(__file__).parent / "compression_dataset.csv"
MODEL_PATH = Path(__file__).parent / "compression_model.joblib"
SCALER_PATH = Path(__file__).parent / "compression_scaler.joblib"
VALID_COMPRESSION_LEVELS = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80])

# Improved: Use coarser bins for grouping
CQI_BIN_WIDTH = 0.5  # Was 0.05 - increased for more samples per bin
FPS_BINS = [60, 72, 90, 120]  # Distinct FPS values
SIZE_BIN_WIDTH = 20  # KB - for grouping traffic profiles

RELIABILITY_THRESHOLD = 0.8  # 80% delay reliability threshold

# Feature columns for ML model
FEATURE_COLUMNS = ['num_users', 'cqi_midpoint', 'fps', 'size_mean_kb', 'size_std_kb']


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
        best_row = group.loc[group['delay_reliability'].idxmax()]
    
    return best_row['compression_level']


def create_feature_bins(df):
    """Create bins for CQI and traffic size to group similar scenarios."""
    # CQI bins
    cqi_min, cqi_max = df['avg_cqi'].min(), df['avg_cqi'].max()
    cqi_bins = np.arange(np.floor(cqi_min * 2) / 2, np.ceil(cqi_max * 2) / 2 + CQI_BIN_WIDTH, CQI_BIN_WIDTH)
    cqi_labels = [f"{cqi_bins[i]:.1f}-{cqi_bins[i+1]:.1f}" for i in range(len(cqi_bins)-1)]
    df['cqi_bin'] = pd.cut(df['avg_cqi'], bins=cqi_bins, labels=cqi_labels, include_lowest=True)
    
    # Size bins for traffic profile grouping
    size_min, size_max = df['size_mean_kb'].min(), df['size_mean_kb'].max()
    size_bins = np.arange(np.floor(size_min / SIZE_BIN_WIDTH) * SIZE_BIN_WIDTH,
                          np.ceil(size_max / SIZE_BIN_WIDTH) * SIZE_BIN_WIDTH + SIZE_BIN_WIDTH,
                          SIZE_BIN_WIDTH)
    size_labels = [f"{int(size_bins[i])}-{int(size_bins[i+1])}" for i in range(len(size_bins)-1)]
    df['size_bin'] = pd.cut(df['size_mean_kb'], bins=size_bins, labels=size_labels, include_lowest=True)
    
    return df, cqi_bins, size_bins


def main():
    print("=" * 60)
    print("IMPROVED COMPRESSION MODEL TRAINING")
    print("(with FPS and Traffic Profile Features)")
    print("=" * 60)
    
    # Load dataset
    print(f"\nLoading dataset from {DATASET_PATH}...")
    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} samples")
    print(f"Columns: {list(df.columns)}")
    
    # Data statistics
    print(f"\nData Statistics:")
    print(f"  CQI range: {df['avg_cqi'].min():.2f} - {df['avg_cqi'].max():.2f}")
    print(f"  FPS values: {sorted(df['fps'].unique())}")
    print(f"  Size mean range: {df['size_mean_kb'].min():.1f} - {df['size_mean_kb'].max():.1f} KB")
    print(f"  Compression levels: {sorted(df['compression_level'].unique())}")
    
    # Create feature bins
    df, cqi_bins, size_bins = create_feature_bins(df)
    
    print(f"\nCQI bin width: {CQI_BIN_WIDTH}")
    print(f"Size bin width: {SIZE_BIN_WIDTH} KB")
    print(f"CQI bin distribution:\n{df['cqi_bin'].value_counts().sort_index()}")
    print(f"\nFPS distribution:\n{df['fps'].value_counts().sort_index()}")
    print(f"\nSize bin distribution:\n{df['size_bin'].value_counts().sort_index()}")
    
    # Aggregate by (num_users, cqi_bin, fps, size_bin, compression_level)
    # This groups similar network/traffic scenarios together
    agg_cols = ['num_users', 'cqi_bin', 'fps', 'size_bin', 'compression_level']
    scenario_agg = df.groupby(agg_cols, observed=True).agg({
        'delay_reliability': 'mean',
        'avg_mse': 'mean',
        'avg_cqi': 'mean',
        'size_mean_kb': 'first',  # Same within size_bin
        'size_std_kb': 'first',   # Same within size_bin
        'run_id': 'count'
    }).rename(columns={'run_id': 'sample_count'}).reset_index()
    
    print(f"\nAggregated scenarios: {len(scenario_agg)}")
    
    # Find optimal compression per (num_users, cqi_bin, fps, size_bin)
    group_cols = ['num_users', 'cqi_bin', 'fps', 'size_bin']
    optimal_map = {}
    
    for group_key, group in scenario_agg.groupby(group_cols, observed=True):
        optimal_comp = find_optimal_compression(group)
        cqi_midpoint = group['avg_cqi'].mean()
        size_mean = group['size_mean_kb'].iloc[0]
        size_std = group['size_std_kb'].iloc[0]
        
        optimal_map[group_key] = {
            'num_users': group_key[0],
            'cqi_midpoint': cqi_midpoint,
            'fps': group_key[2],
            'size_mean_kb': size_mean,
            'size_std_kb': size_std,
            'optimal_compression': optimal_comp
        }
    
    print(f"Optimal compression computed for {len(optimal_map)} scenarios")
    
    # Build training dataset
    train_df = pd.DataFrame(list(optimal_map.values()))
    
    print(f"\nTraining dataset size: {len(train_df)}")
    print(f"Optimal compression distribution:\n{train_df['optimal_compression'].value_counts().sort_index()}")
    
    # Prepare features and target
    X = train_df[FEATURE_COLUMNS].values
    y = train_df['optimal_compression'].values
    
    print(f"\nFeatures: {FEATURE_COLUMNS}")
    print(f"Feature matrix shape: {X.shape}")
    
    # Scale features for better model performance
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=None
    )
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Calculate sample weights to balance compression distribution
    from sklearn.utils.class_weight import compute_sample_weight
    sample_weights = compute_sample_weight('balanced', y_train)
    
    print(f"Sample weights: min={sample_weights.min():.2f}, max={sample_weights.max():.2f}")
    
    # Train XGBoost with improved hyperparameters
    model = XGBRegressor(
        n_estimators=150,
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
        print(f"  {feat}: {imp:.4f}")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='neg_mean_absolute_error')
    print(f"\nCross-validation MAE: {-cv_scores.mean():.2f} (+/- {cv_scores.std() * 2:.2f})")
    
    # Evaluate on test set
    y_pred_raw = model.predict(X_test)
    y_pred_snapped = np.array([snap_to_compression_level(p) for p in y_pred_raw])
    
    mae = mean_absolute_error(y_test, y_pred_snapped)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred_snapped))
    r2 = r2_score(y_test, y_pred_snapped)
    
    # Accuracy metrics
    exact_match = np.mean(y_pred_snapped == y_test)
    within_5 = np.mean(np.abs(y_pred_snapped - y_test) <= 5)
    within_10 = np.mean(np.abs(y_pred_snapped - y_test) <= 10)
    
    print(f"\n{'='*60}")
    print("MODEL EVALUATION (Test Set)")
    print(f"{'='*60}")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R² Score: {r2:.3f}")
    print(f"\nAccuracy Metrics:")
    print(f"  Exact match: {exact_match*100:.1f}%")
    print(f"  Within ±5: {within_5*100:.1f}%")
    print(f"  Within ±10: {within_10*100:.1f}%")
    
    # Show sample predictions
    print(f"\nSample predictions:")
    # Unscale for display
    X_test_orig = scaler.inverse_transform(X_test)
    for i in range(min(10, len(X_test))):
        print(f"  Users={int(X_test_orig[i,0])}, CQI={X_test_orig[i,1]:.1f}, "
              f"FPS={int(X_test_orig[i,2])}, Size={X_test_orig[i,3]:.0f}KB -> "
              f"Pred={y_pred_snapped[i]}, Actual={y_test[i]}")
    
    # Show prediction distribution
    print(f"\nPrediction distribution:")
    unique, counts = np.unique(y_pred_snapped, return_counts=True)
    for u, c in zip(unique, counts):
        print(f"  Compression {int(u)}: {c} predictions")
    
    # Save model and scaler
    print(f"\nSaving model to {MODEL_PATH}...")
    joblib.dump({
        'model': model,
        'scaler': scaler,
        'feature_columns': FEATURE_COLUMNS,
        'valid_compression_levels': VALID_COMPRESSION_LEVELS.tolist()
    }, MODEL_PATH)
    print("Model and scaler saved successfully!")
    
    # Also save scaler separately for compatibility
    joblib.dump(scaler, SCALER_PATH)
    
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\nTo use the model:")
    print(f"  model_data = joblib.load('{MODEL_PATH}')")
    print(f"  model = model_data['model']")
    print(f"  scaler = model_data['scaler']")
    print(f"  X = [[num_users, cqi, fps, size_mean_kb, size_std_kb]]")
    print(f"  X_scaled = scaler.transform(X)")
    print(f"  pred = model.predict(X_scaled)")


if __name__ == "__main__":
    main()
