# autoencoder/__init__.py

__version__ = "1.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224  # working resolution (square); matches PCA pipeline
DEFAULT_TRAIN_RATIO = 0.20

# Default latent dimensions to evaluate: 4, 20, 36, ..., 228
DEFAULT_LATENT_DIMS = list(range(4, 373, 16))

# Training hyper-parameters
DEFAULT_EPOCHS = 50
DEFAULT_BATCH_SIZE = 32
DEFAULT_LR = 1e-3
DEFAULT_MAX_LATENT_DIM = 372
