# pca/utils.py
#
# Logging, CSV output, and plotting helpers.

import logging
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def save_results(results: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Save evaluation results to CSV.

    Columns
    -------
    frame            : int   – original frame index in the video
    components       : int   – PCA components used (0 = uncompressed baseline)
    mse              : float – pixel-domain MSE (scaled to [0, 255] range)
    pca_size_bytes   : int   – PCA compressed size (coefficients + amortised
                               model overhead in float32)
    encoded_size_bytes : int – per-frame encoded packet size from the original
                               h264/vp9 bitstream (varies per frame type)
    raw_size_bytes   : int   – decoded raw RGB size (H × W × 3, constant)
    pict_type        : str   – picture type from codec (I / P / B)
    explained_variance : float – cumulative explained variance ratio for
                               this component count (0–1 scale)
    """
    df = pd.DataFrame(results)
    df = df.sort_values(["frame", "components"], ascending=[True, False])
    df.to_csv(output_file, index=False)
    logging.info(f"Results saved to {output_file}")

    # Print summary by component count
    logging.info("\nSummary statistics by component count:")
    summary = (
        df[df["components"] > 0]
        .groupby("components")
        .agg(
            mse_mean=("mse", "mean"),
            mse_std=("mse", "std"),
            pca_size=("size_bytes", "first"),
            enc_size_mean=("frame_complexity", "mean"),
            expl_var=("explained_variance", "first"),
        )
        .round(4)
    )
    logging.info(summary.to_string())


def plot_results(results: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Create and save two-panel visualisation:
      1. MSE by frame for each component count
      2. Rate-distortion curve (PCA size vs mean MSE)
    """
    df = pd.DataFrame(results)
    components_list = sorted(df["components"].unique(), reverse=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # ---- Panel 1: MSE by frame ------------------------------------
    for n_comp in components_list:
        sub = df[df["components"] == n_comp]
        axes[0].plot(
            sub["frame"], sub["mse"],
            label=f"comp={n_comp}",
            marker="o", alpha=0.6, markersize=2,
        )

    axes[0].set_xlabel("Frame index")
    axes[0].set_ylabel("MSE (pixel domain)")
    axes[0].set_title("PCA Reconstruction Error by Frame")
    axes[0].legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=7)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_yscale("log")

    # ---- Panel 2: Rate-distortion ---------------------------------
    avg_mse = df.groupby("components")["mse"].mean()
    avg_size = df.groupby("components")["size_bytes"].first()

    sort_idx = avg_size.argsort()
    avg_size_sorted = avg_size.iloc[sort_idx]
    avg_mse_sorted = avg_mse.iloc[sort_idx]

    axes[1].plot(
        avg_size_sorted, avg_mse_sorted,
        marker="o", markersize=8, linewidth=2,
    )

    for i in range(len(avg_size_sorted)):
        n_comp = avg_size_sorted.index[i]
        axes[1].annotate(
            f"{n_comp}",
            (avg_size_sorted.iloc[i], avg_mse_sorted.iloc[i]),
            textcoords="offset points", xytext=(0, 10),
            ha="center", fontsize=8,
        )

    axes[1].set_xlabel("PCA size (bytes)")
    axes[1].set_ylabel("Average MSE (pixel domain)")
    axes[1].set_title("PCA Rate-Distortion Curve")
    axes[1].grid(True, alpha=0.3)
    axes[1].set_yscale("log")

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logging.info(f"Visualisation saved to {output_file}")
    plt.close()
