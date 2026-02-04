# pca/main.py

import argparse
import logging
from pathlib import Path

import numpy as np

from . import RANDOM_SEED, DEFAULT_IMG_SIZE, DEFAULT_TRAIN_RATIO, DEFAULT_COMPONENTS, DEFAULT_MAX_COMPONENTS
from .data import load_data
from .models import PCACompressor
from .evaluate import evaluate_compression
from .utils import setup_logging, save_results, plot_results


def main() -> None:
    """Main function to run PCA compression evaluation."""
    parser = argparse.ArgumentParser(description="PCA-based video compression analysis")
    parser.add_argument("--video-path", type=Path, default=Path("../../data/sintel_trailer-1080p.mp4"),
                        help="Path to the input video file")
    parser.add_argument("--max-components", type=int, default=DEFAULT_MAX_COMPONENTS,
                        help="Maximum number of PCA components")
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO,
                        help="Ratio of frames for PCA fitting")
    parser.add_argument("--output-csv", type=Path, default=Path("pca_compression_results.csv"),
                        help="Output CSV file path")
    parser.add_argument("--output-plot", type=Path, default=Path("pca_compression_analysis.png"),
                        help="Output plot file path")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")

    args = parser.parse_args()

    setup_logging(args.log_level)

    # Set random seeds for reproducibility
    np.random.seed(RANDOM_SEED)

    logging.info("PCA Video Compression Analysis")
    logging.info("=" * 60)

    try:
        # Load data
        frames_train, frames_test = load_data(args.video_path, args.train_ratio)

        # Create and fit PCA compressor
        logging.info(f"Fitting PCA with max {args.max_components} components...")
        compressor = PCACompressor(n_components=args.max_components, img_size=DEFAULT_IMG_SIZE)
        compressor.fit(frames_train)
        logging.info("PCA fitting complete!")

        # Define components to evaluate (5, 10, 15, ..., max_components)
        components_list = [c for c in range(args.max_components, 0, -5)]

        # Evaluate compression
        results = evaluate_compression(compressor, frames_test, components_list)

        # Save results
        save_results(results, args.output_csv)

        # Create plots
        plot_results(results, args.output_plot)

        logging.info("=" * 60)
        logging.info("Analysis complete!")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
