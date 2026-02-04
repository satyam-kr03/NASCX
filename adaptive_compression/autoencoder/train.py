# autoencoder/train.py

import logging
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from . import DEFAULT_NUM_EPOCHS, DEFAULT_LEARNING_RATE


def train_model(model: nn.Module, dataloader: DataLoader, device: torch.device,
                num_epochs: int = DEFAULT_NUM_EPOCHS, learning_rate: float = DEFAULT_LEARNING_RATE) -> None:
    """
    Train the autoencoder model.

    Args:
        model: The model to train
        dataloader: Training data loader
        device: Device to train on
        num_epochs: Number of training epochs
        learning_rate: Learning rate for optimizer
    """
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

    logging.info(f"Training autoencoder for {num_epochs} epochs on {device}")
    logging.info("=" * 60)

    model.train()
    for epoch in range(num_epochs):
        total_loss = 0.0
        for batch in dataloader:
            batch = batch.to(device)

            reconstructed, _ = model(batch)
            loss = criterion(reconstructed, batch)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)
        scheduler.step(avg_loss)

        if (epoch + 1) % 5 == 0:
            logging.info(f'Epoch [{epoch+1}/{num_epochs}], Loss: {avg_loss:.6f}, LR: {optimizer.param_groups[0]["lr"]:.6f}')

    logging.info("Training complete!")