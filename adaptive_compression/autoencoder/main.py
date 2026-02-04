# autoencoder/main.py

import argparse
import logging
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from . import RANDOM_SEED, DEFAULT_LATENT_CHANNELS, DEFAULT_BATCH_SIZE, DEFAULT_NUM_EPOCHS, DEFAULT_LEARNING_RATE, DEFAULT_TRAIN_RATIO
from .data import FrameDataset, load_data
from .models import VariableRateAutoencoder
from .train import train_model
from .evaluate import evaluate_compression
from .utils import setup_logging, save_results, plot_results


def main() -> None:
    """Main function to run the autoencoder training and evaluation."""
    parser = argparse.ArgumentParser(description="Train and evaluate variable rate autoencoder for video compression")
    parser.add_argument("--video-path", type=Path, default=Path("../data/sintel_trailer-1080p.mp4"),
                        help="Path to the input video file")
    parser.add_argument("--latent-channels", type=int, default=DEFAULT_LATENT_CHANNELS,
                        help="Number of latent channels")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="Batch size for training")
    parser.add_argument("--num-epochs", type=int, default=DEFAULT_NUM_EPOCHS,
                        help="Number of training epochs")
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE,
                        help="Learning rate")
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO,
                        help="Ratio of frames for training")
    parser.add_argument("--output-csv", type=Path, default=Path("varrate_compression_results.csv"),
                        help="Output CSV file path")
    parser.add_argument("--output-plot", type=Path, default=Path("varrate_compression_analysis.png"),
                        help="Output plot file path")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")

    args = parser.parse_args()

    setup_logging(args.log_level)

    # Set random seeds for reproducibility
    np.random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)

    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logging.info(f"Using device: {device}")

    try:
        # Load data
        frames_train, frames_test = load_data(args.video_path, args.train_ratio)

        # Create dataset and dataloader
        dataset = FrameDataset(frames_train)
        dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True,
                               generator=torch.Generator().manual_seed(RANDOM_SEED))

        # Create model
        model = VariableRateAutoencoder(latent_channels=args.latent_channels)
        model.to(device)

        # Train model
        train_model(model, dataloader, device, args.num_epochs, args.learning_rate)

        # Evaluate compression
        results = evaluate_compression(model, frames_test, device)

        # Save results
        save_results(results, args.output_csv)

        # Create plots
        plot_results(results, args.output_plot)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()