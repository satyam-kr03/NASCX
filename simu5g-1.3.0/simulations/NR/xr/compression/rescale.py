#!/usr/bin/env python3
"""
Rescale PCA traffic file bitstream sizes to match a target data rate.

When adding a new video to the pipeline, raw PCA sweep summaries will have
arbitrary byte sizes depending on the original video resolution and codec.
This script applies z-score standardisation followed by linear rescaling
to bring the size_bytes column in line with a target bitrate.

Method:
    1. Compute z-scores of all size_bytes values.
    2. Determine a scaling factor so that the mean size at the reference
       compression level equals the target bytes/frame.
    3. Rescale all values to the new distribution.

Usage:
    python rescale.py --input traffic_files/pca/pca_sweep_summary_vietnam.csv \\
                      --target-mbps 60 --fps 60 --reference-cl 80

    python rescale.py --help
"""

import argparse
from pathlib import Path

import pandas as pd


def rescale_traffic(
    input_path: Path,
    output_path: Path,
    target_mbps: float,
    fps: int,
    reference_cl: int,
) -> None:
    """Rescale size_bytes to match a target bitrate at *reference_cl*."""
    df = pd.read_csv(input_path)

    if "size_bytes" not in df.columns:
        raise ValueError(f"'size_bytes' column not found in {input_path}")
    if "components" not in df.columns:
        raise ValueError(f"'components' column not found in {input_path}")

    # Target bytes per frame at the reference compression level
    target_bytes = (target_mbps * 1e6) / (fps * 8)

    # Current statistics
    mu_old = df["size_bytes"].mean()
    sigma_old = df["size_bytes"].std()
    size_ref_old = df.loc[df["components"] == reference_cl, "size_bytes"].mean()

    if pd.isna(size_ref_old) or size_ref_old == 0:
        raise ValueError(
            f"No data found for components={reference_cl} in {input_path}"
        )

    # Z-score standardisation
    z_scores = (df["size_bytes"] - mu_old) / sigma_old

    # Linear rescaling: scale so that reference CL maps to target_bytes
    scaling_factor = target_bytes / size_ref_old
    mu_new = mu_old * scaling_factor
    sigma_new = sigma_old * scaling_factor
    df["size_bytes"] = ((sigma_new * z_scores) + mu_new).astype(int)

    # Verification
    summary = df.groupby("components")["size_bytes"].mean().reset_index()
    print("Rescaled size_bytes summary:")
    print(summary.to_string(index=False))

    df.to_csv(output_path, index=False)
    print(f"\nSaved rescaled data to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescale PCA traffic file sizes to a target data rate"
    )
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to the input PCA sweep summary CSV",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path (default: overwrite input file)",
    )
    parser.add_argument(
        "--target-mbps", type=float, default=60.0,
        help="Target bitrate in Mbps (default: 60)",
    )
    parser.add_argument(
        "--fps", type=int, default=60,
        help="Frame rate in fps (default: 60)",
    )
    parser.add_argument(
        "--reference-cl", type=int, default=80,
        help="Compression level whose mean size should equal the target "
             "bytes/frame (default: 80, i.e. max components)",
    )
    args = parser.parse_args()

    output = args.output if args.output is not None else args.input
    rescale_traffic(args.input, output, args.target_mbps, args.fps, args.reference_cl)


if __name__ == "__main__":
    main()
