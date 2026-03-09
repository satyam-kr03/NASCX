# autoencoder/utils.py
#
# Logging standardisation, CSV output, and dual-panel visualisation
# for the autoencoder compression pipeline.

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
    frame              : int   – original frame index in the video
    latent_dim         : int   – bottleneck dimension (0 = uncompressed baseline)
    mse                : float – pixel-domain MSE (scaled to [0, 255] range)
    ae_size_bytes      : int   – latent vector + amortised model weight cost
    encoded_size_bytes : int   – per-frame encoded packet size from the
                                 original codec bitstream
    raw_size_bytes     : int   – decoded raw RGB size (H × W × 3, constant)
    pict_type          : str   – picture type from codec (I / P / B)
    """
    df = pd.DataFrame(results)
    df = df.sort_values(["frame", "latent_dim"], ascending=[True, True])
    df.to_csv(output_file, index=False)
    logging.info(f"Results saved to {output_file}")

    # Print summary by latent dimension
    logging.info("\nSummary statistics by latent dimension:")
    summary = (
        df[df["latent_dim"] > 0]
        .groupby("latent_dim")
        .agg(
            mse_mean=("mse", "mean"),
            mse_std=("mse", "std"),
            ae_size=("ae_size_bytes", "first"),
            enc_size_mean=("encoded_size_bytes", "mean"),
        )
        .round(4)
    )
    logging.info(summary.to_string())


def plot_results(results: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Create and save a dual-panel visualisation:

      1. Frame-by-frame reconstruction error (MSE, log-scale) per frame
         index for each latent dimension.
      2. Rate-distortion curve: average MSE (log-scale) vs ae_size_bytes,
         annotated with latent dimension labels.
    """
    df = pd.DataFrame(results)
    latent_dims = sorted(
        [d for d in df["latent_dim"].unique() if d > 0]
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # ---- Panel 1: MSE by frame ----------------------------------------
    for dim in latent_dims:
        sub = df[df["latent_dim"] == dim]
        axes[0].plot(
            sub["frame"], sub["mse"],
            label=f"d={dim}",
            marker="o", alpha=0.6, markersize=2,
        )

    axes[0].set_xlabel("Frame index")
    axes[0].set_ylabel("MSE (pixel domain)")
    axes[0].set_title("Autoencoder Reconstruction Error by Frame")
    axes[0].legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=7)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_yscale("log")

    # ---- Panel 2: Rate-distortion -------------------------------------
    compressed = df[df["latent_dim"] > 0]
    avg_mse = compressed.groupby("latent_dim")["mse"].mean()
    avg_size = compressed.groupby("latent_dim")["ae_size_bytes"].first()

    sort_idx = avg_size.argsort()
    avg_size_sorted = avg_size.iloc[sort_idx]
    avg_mse_sorted = avg_mse.iloc[sort_idx]

    axes[1].plot(
        avg_size_sorted, avg_mse_sorted,
        marker="o", markersize=8, linewidth=2,
    )

    for i in range(len(avg_size_sorted)):
        dim = avg_size_sorted.index[i]
        axes[1].annotate(
            f"{dim}",
            (avg_size_sorted.iloc[i], avg_mse_sorted.iloc[i]),
            textcoords="offset points", xytext=(0, 10),
            ha="center", fontsize=8,
        )

    axes[1].set_xlabel("AE size (bytes)")
    axes[1].set_ylabel("Average MSE (pixel domain)")
    axes[1].set_title("Autoencoder Rate-Distortion Curve")
    axes[1].grid(True, alpha=0.3)
    axes[1].set_yscale("log")

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logging.info(f"Visualisation saved to {output_file}")
    plt.close()
