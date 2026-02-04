# autoencoder/utils.py

import logging
from pathlib import Path
from typing import List, Dict, Any

import matplotlib.pyplot as plt
import pandas as pd


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def save_results(results: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Save evaluation results to CSV.

    Args:
        results: List of result dictionaries
        output_file: Path to save CSV file
    """
    df = pd.DataFrame(results)
    df = df.sort_values(['frame', 'keep_ratio'], ascending=[True, False])
    
    # Map keep_ratio to "components" (1-16) for simu5g compatibility
    keep_ratios = sorted(df['keep_ratio'].unique())
    keep_ratio_to_level = {ratio: level for level, ratio in enumerate(keep_ratios, start=1)}
    df['components'] = df['keep_ratio'].map(keep_ratio_to_level)
    
    # Match PCA format exactly: frame, components, mse, size_bytes
    df_output = df[['frame', 'components', 'mse', 'size_bytes']]
    df_output.to_csv(output_file, index=False)
    logging.info(f"Results saved to {output_file}")

    # Print summary
    logging.info("\nFirst few rows:")
    logging.info(df_output.head(20).to_string())

    logging.info("\nSummary statistics by components:")
    summary = df.groupby('components').agg({
        'mse': ['mean', 'std'],
        'size_bytes': 'first'
    }).round(6)
    logging.info(summary.to_string())


def plot_results(results: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Create and save visualization plots.

    Args:
        results: List of result dictionaries
        output_file: Path to save plot image
    """
    df = pd.DataFrame(results)
    
    # Map keep_ratio to "components" (1-16) for simu5g compatibility
    keep_ratios = sorted(df['keep_ratio'].unique())
    keep_ratio_to_level = {ratio: level for level, ratio in enumerate(keep_ratios, start=1)}
    df['components'] = df['keep_ratio'].map(keep_ratio_to_level)
    
    components = sorted(df['components'].unique())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: MSE by frame
    for comp in components:
        data = df[df['components'] == comp]
        axes[0].plot(data['frame'], data['mse'],
                    label=f'comp={comp}',
                    marker='o', alpha=0.6, markersize=3)

    axes[0].set_xlabel('Frame')
    axes[0].set_ylabel('MSE')
    axes[0].set_title('Reconstruction Error by Frame')
    axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_yscale('log')

    # Plot 2: Rate-Distortion curve
    avg_mse = df.groupby('components')['mse'].mean()
    avg_size = df.groupby('components')['size_bytes'].first()

    # Sort by size for proper curve
    sort_idx = avg_size.argsort()
    avg_size_sorted = avg_size.iloc[sort_idx]
    avg_mse_sorted = avg_mse.iloc[sort_idx]

    axes[1].plot(avg_size_sorted, avg_mse_sorted, marker='o', markersize=10, linewidth=2)
    for i in range(len(avg_size_sorted)):
        comp = avg_size_sorted.index[i]
        axes[1].annotate(f'{comp}',
                         (avg_size_sorted.iloc[i], avg_mse_sorted.iloc[i]),
                         textcoords="offset points",
                         xytext=(0,10),
                         ha='center',
                         fontsize=8)

    axes[1].set_xlabel('Size (bytes)')
    axes[1].set_ylabel('Average MSE')
    axes[1].set_title('Rate-Distortion Curve (Variable Rate)')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_yscale('log')

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logging.info(f"Visualization saved to {output_file}")
    plt.close()