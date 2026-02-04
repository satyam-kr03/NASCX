# autoencoder/__init__.py

__version__ = "1.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224
DEFAULT_LATENT_CHANNELS = 128
DEFAULT_BATCH_SIZE = 16
DEFAULT_NUM_EPOCHS = 100  # Increased from 40 for better convergence
DEFAULT_LEARNING_RATE = 0.001
DEFAULT_TRAIN_RATIO = 0.5  # Increased from 0.15 for more training data

# Keep ratios from 0.0625 (1/16) to 1.0 (full fidelity)
# This gives 16 evenly spaced evaluation points matching PCA's 16 component levels
DEFAULT_KEEP_RATIOS = [(i + 1) / 16 for i in range(16)]  # [0.0625, 0.125, ..., 1.0]