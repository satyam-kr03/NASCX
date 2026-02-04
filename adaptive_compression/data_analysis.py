#!/usr/bin/env python3
"""
Data Analysis Script for Compression Results

Analyzes PCA and Autoencoder compression results CSVs to provide
insights about compression performance including mean size, MSE statistics,
rate-distortion curves, and comparison between methods.
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def load_compression_data(csv_path: Path) -> pd.DataFrame:
    """Load compression results from CSV file."""
    return pd.read_csv(csv_path)


def compute_summary_statistics(df: pd.DataFrame, method_name: str, level_col: str) -> pd.DataFrame:
    """
    Compute summary statistics for compression results.
    
    Args:
        df: DataFrame with compression results
        method_name: Name of the compression method
        level_col: Column name for compression level ('components' or 'keep_ratio')
    
    Returns:
        Summary DataFrame
    """
    summary = df.groupby(level_col).agg({
        'mse': ['mean', 'std', 'min', 'max', 'median'],
        'size_bytes': 'first'
    }).round(4)
    
    summary.columns = ['mse_mean', 'mse_std', 'mse_min', 'mse_max', 'mse_median', 'size_bytes']
    summary['method'] = method_name
    summary = summary.reset_index()
    
    # Add PSNR (Peak Signal-to-Noise Ratio) - assuming 8-bit images (max value 255)
    # PSNR = 10 * log10(255^2 / MSE)
    summary['psnr_mean'] = 10 * np.log10(255**2 / summary['mse_mean'])
    
    # Add bits per pixel (assuming 224x224 image)
    img_pixels = 224 * 224 * 3  # 3 channels
    summary['bpp'] = (summary['size_bytes'] * 8) / img_pixels
    
    # Add compression ratio (relative to uncompressed size)
    uncompressed_size = img_pixels  # 1 byte per pixel value
    summary['compression_ratio'] = uncompressed_size / summary['size_bytes']
    
    return summary


def print_summary_table(summary: pd.DataFrame, method_name: str, level_col: str):
    """Print formatted summary table."""
    print(f"\n{'='*80}")
    print(f" {method_name.upper()} COMPRESSION ANALYSIS")
    print(f"{'='*80}")
    
    print(f"\n--- Summary by {level_col} ---")
    cols = [level_col, 'size_bytes', 'mse_mean', 'mse_std', 'psnr_mean', 'bpp', 'compression_ratio']
    print(summary[cols].to_string(index=False))
    
    print(f"\n--- Overall Statistics ---")
    print(f"  Total frames analyzed: {summary['mse_mean'].count() * len(summary)}")
    print(f"  Best MSE (mean): {summary['mse_mean'].min():.4f} at {level_col}={summary.loc[summary['mse_mean'].idxmin(), level_col]}")
    print(f"  Worst MSE (mean): {summary['mse_mean'].max():.4f} at {level_col}={summary.loc[summary['mse_mean'].idxmax(), level_col]}")
    print(f"  Best PSNR: {summary['psnr_mean'].max():.2f} dB")
    print(f"  Size range: {summary['size_bytes'].min()} - {summary['size_bytes'].max()} bytes")
    print(f"  Compression ratio range: {summary['compression_ratio'].min():.2f}x - {summary['compression_ratio'].max():.2f}x")


def plot_comparison(pca_summary: pd.DataFrame, ae_summary: pd.DataFrame, output_path: Path):
    """Create comparison plots between PCA and autoencoder."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Rate-Distortion curves (MSE vs Size)
    ax = axes[0, 0]
    ax.plot(pca_summary['size_bytes'], pca_summary['mse_mean'], 'o-', label='PCA', markersize=6)
    ax.plot(ae_summary['size_bytes'], ae_summary['mse_mean'], 's-', label='Autoencoder', markersize=6)
    ax.set_xlabel('Size (bytes)')
    ax.set_ylabel('Mean MSE')
    ax.set_title('Rate-Distortion Curve (MSE)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    
    # Plot 2: Rate-Distortion curves (PSNR vs BPP)
    ax = axes[0, 1]
    ax.plot(pca_summary['bpp'], pca_summary['psnr_mean'], 'o-', label='PCA', markersize=6)
    ax.plot(ae_summary['bpp'], ae_summary['psnr_mean'], 's-', label='Autoencoder', markersize=6)
    ax.set_xlabel('Bits Per Pixel (BPP)')
    ax.set_ylabel('PSNR (dB)')
    ax.set_title('Rate-Distortion Curve (PSNR)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: MSE Standard Deviation comparison
    ax = axes[1, 0]
    bar_width = 0.35
    x_pca = np.arange(len(pca_summary))
    x_ae = np.arange(len(ae_summary))
    
    # Normalize x-axis by size for fair comparison
    ax.scatter(pca_summary['size_bytes'], pca_summary['mse_std'], s=50, label='PCA', alpha=0.7)
    ax.scatter(ae_summary['size_bytes'], ae_summary['mse_std'], s=50, label='Autoencoder', alpha=0.7)
    ax.set_xlabel('Size (bytes)')
    ax.set_ylabel('MSE Standard Deviation')
    ax.set_title('MSE Variability Across Frames')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    
    # Plot 4: Compression ratio vs PSNR
    ax = axes[1, 1]
    ax.plot(pca_summary['compression_ratio'], pca_summary['psnr_mean'], 'o-', label='PCA', markersize=6)
    ax.plot(ae_summary['compression_ratio'], ae_summary['psnr_mean'], 's-', label='Autoencoder', markersize=6)
    ax.set_xlabel('Compression Ratio')
    ax.set_ylabel('PSNR (dB)')
    ax.set_title('Compression Efficiency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nComparison plot saved to: {output_path}")
    plt.close()


def analyze_per_frame_variation(df: pd.DataFrame, method_name: str, level_col: str):
    """Analyze per-frame variation in MSE."""
    print(f"\n--- Per-Frame Analysis for {method_name} ---")
    
    # Find frames with highest and lowest MSE at each compression level
    frame_stats = df.groupby('frame')['mse'].agg(['mean', 'std']).reset_index()
    
    best_frame = frame_stats.loc[frame_stats['mean'].idxmin()]
    worst_frame = frame_stats.loc[frame_stats['mean'].idxmax()]
    
    print(f"  Best compressed frame: {int(best_frame['frame'])} (avg MSE: {best_frame['mean']:.4f})")
    print(f"  Worst compressed frame: {int(worst_frame['frame'])} (avg MSE: {worst_frame['mean']:.4f})")
    print(f"  MSE variability across frames: std={frame_stats['mean'].std():.4f}")


def main():
    parser = argparse.ArgumentParser(description="Analyze compression results")
    parser.add_argument("--pca-csv", type=Path, default=Path("pca/pca_compression_results.csv"),
                        help="Path to PCA compression results CSV")
    parser.add_argument("--ae-csv", type=Path, default=Path("autoencoder/varrate_compression_results.csv"),
                        help="Path to autoencoder compression results CSV")
    parser.add_argument("--output-plot", type=Path, default=Path("compression_comparison.png"),
                        help="Output path for comparison plot")
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print(" COMPRESSION METHODS DATA ANALYSIS")
    print("="*80)
    
    # Load data
    pca_df = None
    ae_df = None
    
    if args.pca_csv.exists():
        pca_df = load_compression_data(args.pca_csv)
        print(f"\nLoaded PCA data: {len(pca_df)} records from {args.pca_csv}")
    else:
        print(f"\nWarning: PCA CSV not found at {args.pca_csv}")
    
    if args.ae_csv.exists():
        ae_df = load_compression_data(args.ae_csv)
        print(f"Loaded Autoencoder data: {len(ae_df)} records from {args.ae_csv}")
    else:
        print(f"Warning: Autoencoder CSV not found at {args.ae_csv}")
    
    # Analyze PCA results
    pca_summary = None
    if pca_df is not None:
        pca_summary = compute_summary_statistics(pca_df, "PCA", "components")
        print_summary_table(pca_summary, "PCA", "components")
        analyze_per_frame_variation(pca_df, "PCA", "components")
    
    # Analyze Autoencoder results
    ae_summary = None
    if ae_df is not None:
        # The autoencoder CSV may use 'keep_ratio' or 'components' - check the columns
        level_col = 'components' if 'components' in ae_df.columns else 'keep_ratio'
        ae_summary = compute_summary_statistics(ae_df, "Autoencoder", level_col)
        print_summary_table(ae_summary, "Autoencoder", level_col)
        analyze_per_frame_variation(ae_df, "Autoencoder", level_col)
    
    # Create comparison plot if both datasets are available
    if pca_summary is not None and ae_summary is not None:
        plot_comparison(pca_summary, ae_summary, args.output_plot)
        
        # Print comparison summary
        print(f"\n{'='*80}")
        print(" COMPARISON SUMMARY")
        print(f"{'='*80}")
        
        # Compare at similar sizes (find closest matching sizes)
        print("\n--- Method Comparison at Similar Sizes ---")
        for pca_size in pca_summary['size_bytes'].unique()[:5]:  # First 5 levels
            pca_row = pca_summary[pca_summary['size_bytes'] == pca_size].iloc[0]
            # Find closest AE size
            ae_idx = (ae_summary['size_bytes'] - pca_size).abs().idxmin()
            ae_row = ae_summary.iloc[ae_idx]
            
            print(f"  Size ~{pca_size} bytes:")
            print(f"    PCA:        MSE={pca_row['mse_mean']:.2f}, PSNR={pca_row['psnr_mean']:.2f}dB")
            print(f"    Autoencoder: MSE={ae_row['mse_mean']:.2f}, PSNR={ae_row['psnr_mean']:.2f}dB")
    
    print("\n" + "="*80)
    print(" Analysis Complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
