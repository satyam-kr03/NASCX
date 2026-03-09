# pca/main.py
#
# CLI entry-point for PCA-based video compression analysis.

import argparse
import logging
from pathlib import Path

import numpy as np

from . import RANDOM_SEED, DEFAULT_TRAIN_RATIO, DEFAULT_COMPONENTS, DEFAULT_MAX_COMPONENTS, DEFAULT_IMG_SIZE
from .data import get_video_info, get_encoded_frame_sizes, sample_training_frames
from .models import PCACompressor
from .evaluate import evaluate_compression
from .utils import setup_logging, save_results, plot_results


def main() -> None:
    """Main function to run PCA compression evaluation."""
    parser = argparse.ArgumentParser(
        description="PCA-based video compression analysis"
    )
    parser.add_argument(
        "--video-path", type=Path,
        default=Path("../data/yt360-videos/dino.mp4"),
        help="Path to the input video file",
    )
    parser.add_argument(
        "--max-components", type=int, default=DEFAULT_MAX_COMPONENTS,
        help="Maximum number of PCA components",
    )
    parser.add_argument(
        "--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO,
        help="Ratio of frames for PCA fitting",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=Path("pca_sweep_summary.csv"),
        help="Output CSV file path",
    )
    parser.add_argument(
        "--output-plot", type=Path,
        default=Path("pca_compression_analysis.png"),
        help="Output plot file path",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--img-size", type=int, default=DEFAULT_IMG_SIZE,
        help="Working resolution (square) for PCA. Frames are resized to "
             "(img_size, img_size) before PCA operations. Default 224 matches "
             "the autoencoder pipeline.",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    np.random.seed(RANDOM_SEED)

    logging.info("PCA Video Compression Analysis")
    logging.info("=" * 60)

    try:
        # 1. Video metadata
        total_frames, height, width = get_video_info(args.video_path)
        logging.info(
            f"Video: {args.video_path.name}  "
            f"({width}x{height}, {total_frames} frames)"
        )

        # 2. Per-frame encoded sizes from ffprobe
        logging.info("Extracting per-frame encoded sizes (ffprobe)...")
        encoded_sizes = get_encoded_frame_sizes(args.video_path)
        logging.info(f"  Got encoded sizes for {len(encoded_sizes)} frames")

        # 3. Load training frames (streaming decode, only train subset held)
        train_frames, train_indices, test_indices = sample_training_frames(
            args.video_path, total_frames, args.train_ratio,
            img_size=args.img_size,
        )

        # 4. Fit PCA
        logging.info(f"Fitting PCA with max {args.max_components} components...")
        compressor = PCACompressor(n_components=args.max_components)
        compressor.fit(train_frames)
        del train_frames  # free training data
        logging.info("PCA fitting complete!")

        # 5. Components to evaluate
        components_list = [c for c in DEFAULT_COMPONENTS if c <= args.max_components]

        # 6. Streaming evaluation
        results = evaluate_compression(
            compressor, args.video_path, test_indices,
            encoded_sizes, components_list,
            img_size=args.img_size,
            total_frames=total_frames,
        )

        # 7. Save & plot
        save_results(results, args.output_csv)
        plot_results(results, args.output_plot)

        logging.info("=" * 60)
        logging.info("Analysis complete!")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
