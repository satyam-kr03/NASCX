#!/usr/bin/env python3
"""
Generate Synthetic Traffic Profiles

Creates multiple XR traffic CSV files with varying frame size distributions
by scaling the original pca_sweep_summary_scaled.csv data.

Traffic Profiles:
- traffic_45kb.csv: Mean ~45 KB (low bandwidth)
- traffic_65kb.csv: Mean ~65 KB (baseline/original)
- traffic_80kb.csv: Mean ~80 KB (medium-high bandwidth)
- traffic_95kb.csv: Mean ~95 KB (high bandwidth)
- traffic_120kb.csv: Mean ~120 KB (very high bandwidth)
"""

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

SIMULATION_DIR = Path(__file__).parent
SOURCE_FILE = SIMULATION_DIR / "pca_sweep_summary_scaled.csv"

# Traffic profile configurations: (target_mean_kb, name)
TRAFFIC_PROFILES = [
    (45, "traffic_45kb.csv"),
    (65, "traffic_65kb.csv"),
    (80, "traffic_80kb.csv"),
    (95, "traffic_95kb.csv"),
    (120, "traffic_120kb.csv"),
]


def load_source_data() -> Tuple[List[Dict], float, float, float, float]:
    """Load source PCA data and compute statistics."""
    rows = []
    sizes = []
    
    with open(SOURCE_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                'frame': int(row['frame']),
                'components': int(row['components']),
                'mse': float(row['mse']),
                'size_bytes': float(row['size_bytes'])
            })
            sizes.append(float(row['size_bytes']))
    
    sizes = np.array(sizes)
    return rows, sizes.mean(), sizes.std(), sizes.min(), sizes.max()


def generate_profile(rows: List[Dict], source_mean: float, source_std: float,
                    target_mean_kb: float, output_file: Path) -> Dict:
    """
    Generate a traffic profile by scaling frame sizes.
    
    Scaling approach:
    - Use linear transformation: new_size = scale * original_size + offset
    - Preserve relative variation between compression levels
    """
    target_mean_bytes = target_mean_kb * 1024
    
    # Scale factor to achieve target mean
    scale = target_mean_bytes / source_mean
    
    # Generate new data
    new_rows = []
    new_sizes = []
    
    for row in rows:
        new_size = row['size_bytes'] * scale
        # Ensure minimum size of 1KB
        new_size = max(new_size, 1024)
        
        # Adjust MSE proportionally (higher compression = higher MSE)
        # When size decreases, MSE increases (inverse relationship)
        if scale < 1.0:
            mse_factor = 1.0 / scale  # More compression = more error
        else:
            mse_factor = 1.0 / scale  # Less compression = less error
        new_mse = row['mse'] * mse_factor
        
        new_rows.append({
            'frame': row['frame'],
            'components': row['components'],
            'mse': new_mse,
            'size_bytes': new_size
        })
        new_sizes.append(new_size)
    
    # Write output file
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['frame', 'components', 'mse', 'size_bytes'])
        writer.writeheader()
        for row in new_rows:
            writer.writerow(row)
    
    # Compute and return statistics
    new_sizes = np.array(new_sizes)
    return {
        'file': output_file.name,
        'mean_kb': new_sizes.mean() / 1024,
        'std_kb': new_sizes.std() / 1024,
        'min_kb': new_sizes.min() / 1024,
        'max_kb': new_sizes.max() / 1024,
        'num_rows': len(new_rows)
    }


def main():
    print("=== Generating Synthetic Traffic Profiles ===\n")
    
    # Load source data
    print(f"Loading source: {SOURCE_FILE}")
    rows, source_mean, source_std, source_min, source_max = load_source_data()
    print(f"  Rows: {len(rows)}")
    print(f"  Mean: {source_mean/1024:.1f} KB")
    print(f"  Std:  {source_std/1024:.1f} KB")
    print(f"  Min:  {source_min/1024:.1f} KB")
    print(f"  Max:  {source_max/1024:.1f} KB")
    print()
    
    # Generate each profile
    profiles_metadata = []
    for target_mean_kb, filename in TRAFFIC_PROFILES:
        output_path = SIMULATION_DIR / filename
        print(f"Generating {filename} (target mean: {target_mean_kb} KB)...")
        
        stats = generate_profile(rows, source_mean, source_std, target_mean_kb, output_path)
        profiles_metadata.append(stats)
        
        print(f"  Created: {output_path}")
        print(f"  Actual Mean: {stats['mean_kb']:.1f} KB, Std: {stats['std_kb']:.1f} KB")
        print(f"  Range: {stats['min_kb']:.1f} - {stats['max_kb']:.1f} KB")
        print()
    
    # Write metadata file for use by dataset generator
    metadata_file = SIMULATION_DIR / "traffic_profiles_metadata.csv"
    with open(metadata_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['file', 'mean_kb', 'std_kb', 'min_kb', 'max_kb', 'num_rows'])
        writer.writeheader()
        for profile in profiles_metadata:
            writer.writerow(profile)
    
    print(f"=== Generated {len(profiles_metadata)} traffic profiles ===")
    print(f"Metadata saved to: {metadata_file}")


if __name__ == "__main__":
    main()
