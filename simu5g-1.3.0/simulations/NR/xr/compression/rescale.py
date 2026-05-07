#!/usr/bin/env python3
"""
Rescale PCA traffic size estimates to match a target bitrate.

This performs a z-score normalization of size_bytes and then linearly
rescales the distribution so that a reference compression level matches
a target Mbps rate.
"""

import argparse
import logging
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rescale PCA sweep sizes to a target bitrate"
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Input PCA sweep CSV (e.g., traffic_files/pca/pca_sweep_summary_video.csv)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output CSV path (default: overwrite input)",
    )
    parser.add_argument(
        "--target-mbps", type=float, required=True,
        help="Target bitrate in Mbps",
    )
    parser.add_argument(
        "--fps", type=float, default=60.0,
        help="Frames per second for the target video (default: 60)",
    )
    parser.add_argument(
        "--reference-cl", type=int, default=80,
        help="Compression level used as the bitrate reference (default: 80)",
    )
    return parser.parse_args()


def rescale_sizes(
    df: pd.DataFrame,
    target_mbps: float,
    fps: float,
    reference_cl: int,
) -> pd.DataFrame:
    if "size_bytes" not in df.columns or "components" not in df.columns:
        raise ValueError("Input CSV must contain 'size_bytes' and 'components' columns.")

    target_bytes_ref = (target_mbps * 1e6) / (fps * 8)

    mu_old = df["size_bytes"].mean()
    sigma_old = df["size_bytes"].std()

    ref_mask = df["components"] == reference_cl
    if not ref_mask.any():
        raise ValueError(
            f"Reference compression level {reference_cl} not found in CSV."
        )

    size_ref_old = df.loc[ref_mask, "size_bytes"].mean()

    df = df.copy()
    df["z_score_size"] = (df["size_bytes"] - mu_old) / sigma_old

    scaling_factor = target_bytes_ref / size_ref_old
    mu_new = mu_old * scaling_factor
    sigma_new = sigma_old * scaling_factor

    df["size_bytes_rescaled"] = (sigma_new * df["z_score_size"]) + mu_new
    df["size_bytes"] = df["size_bytes_rescaled"].astype(int)

    df.drop(columns=["size_bytes_rescaled", "z_score_size"], inplace=True)
    return df


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve() if args.output else input_path

    logging.info(f"Loading {input_path}")
    df = pd.read_csv(input_path)

    df_rescaled = rescale_sizes(
        df,
        target_mbps=args.target_mbps,
        fps=args.fps,
        reference_cl=args.reference_cl,
    )

    logging.info("Verification summary (mean size_bytes by components):")
    summary = (
        df_rescaled.groupby("components")["size_bytes"]
        .mean()
        .reset_index()
    )
    logging.info("\n" + summary.to_string(index=False))

    df_rescaled.to_csv(output_path, index=False)
    logging.info(f"Saved rescaled dataset to {output_path}")


if __name__ == "__main__":
    main()
