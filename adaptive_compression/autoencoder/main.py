# autoencoder/main.py
#
# CLI entry-point for autoencoder-based video compression analysis.

import argparse
import gc
import logging
from pathlib import Path

import numpy as np
import torch

from . import (
    RANDOM_SEED,
    DEFAULT_TRAIN_RATIO,
    DEFAULT_LATENT_DIMS,
    DEFAULT_MAX_LATENT_DIM,
    DEFAULT_EPOCHS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_LR,
    DEFAULT_IMG_SIZE,
)
from .data import get_video_info, get_encoded_frame_sizes, sample_training_frames, get_dataloader
from .models import AutoencoderCompressor
from .evaluate import evaluate_compression
from .utils import setup_logging, save_results, plot_results


def main() -> None:
    """Main function to run autoencoder compression evaluation."""
    parser = argparse.ArgumentParser(
        description="Autoencoder-based video compression analysis"
    )
    parser.add_argument(
        "--video-path", type=Path,
        default=Path("../data/yt360-videos/minecraft.mp4"),
        help="Path to the input video file",
    )
    parser.add_argument(
        "--max-latent-dim", type=int, default=DEFAULT_MAX_LATENT_DIM,
        help="Maximum latent dimension; filters DEFAULT_LATENT_DIMS",
    )
    parser.add_argument(
        "--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO,
        help="Fraction of frames used for training",
    )
    parser.add_argument(
        "--epochs", type=int, default=DEFAULT_EPOCHS,
        help="Training epochs per model",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help="Mini-batch size for training",
    )
    parser.add_argument(
        "--lr", type=float, default=DEFAULT_LR,
        help="Adam optimiser learning rate",
    )
    parser.add_argument(
        "--img-size", type=int, default=DEFAULT_IMG_SIZE,
        help="Working resolution (frames resized to square)",
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Device: 'cuda' or 'cpu' (auto-detect if omitted)",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=Path("ae_compression_results.csv"),
        help="Output CSV file path",
    )
    parser.add_argument(
        "--output-plot", type=Path,
        default=Path("ae_compression_analysis.png"),
        help="Output plot file path",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    np.random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)

    # Auto-detect device
    if args.device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    logging.info("Autoencoder Video Compression Analysis")
    logging.info("=" * 60)
    logging.info(f"Device: {device}")

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

        # 4. Build DataLoader
        _, dataloader = get_dataloader(
            train_frames,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=2,
        )

        # 5. Determine latent dimensions to train/evaluate
        latent_dims = [d for d in DEFAULT_LATENT_DIMS if d <= args.max_latent_dim]
        logging.info(f"Latent dimensions: {latent_dims}")

        # 6. Train autoencoders (one per latent dim, warm-started)
        compressor = AutoencoderCompressor(
            latent_dims=latent_dims,
            img_size=args.img_size,
            device=device,
        )
        compressor.fit(dataloader, epochs=args.epochs, lr=args.lr)

        # Free training data
        del train_frames, dataloader
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # 7. Streaming evaluation
        results = evaluate_compression(
            compressor, args.video_path, test_indices,
            encoded_sizes, latent_dims,
            img_size=args.img_size,
            total_frames=total_frames,
        )

        # 8. Save & plot
        save_results(results, args.output_csv)
        plot_results(results, args.output_plot)

        logging.info("=" * 60)
        logging.info("Analysis complete!")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
