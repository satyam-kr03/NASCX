# pca/utils.py

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
    df = df.sort_values(['frame', 'components'], ascending=[True, False])
    df.to_csv(output_file, index=False)
    logging.info(f"Results saved to {output_file}")

    # Print summary
    logging.info("\nFirst few rows:")
    logging.info(df.head(20).to_string())

    logging.info("\nSummary statistics by component count:")
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
    components_list = sorted(df['components'].unique(), reverse=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: MSE by frame
    for n_components in components_list:
        data = df[df['components'] == n_components]
        axes[0].plot(data['frame'], data['mse'],
                    label=f'comp={n_components}',
                    marker='o', alpha=0.6, markersize=3)

    axes[0].set_xlabel('Frame')
    axes[0].set_ylabel('MSE')
    axes[0].set_title('PCA Reconstruction Error by Frame')
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
        n_comp = avg_size_sorted.index[i]
        axes[1].annotate(f'{n_comp}',
                         (avg_size_sorted.iloc[i], avg_mse_sorted.iloc[i]),
                         textcoords="offset points",
                         xytext=(0,10),
                         ha='center',
                         fontsize=8)

    axes[1].set_xlabel('Size (bytes)')
    axes[1].set_ylabel('Average MSE')
    axes[1].set_title('PCA Rate-Distortion Curve')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_yscale('log')

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logging.info(f"Visualization saved to {output_file}")
    plt.close()
