# compression/__init__.py

__version__ = "2.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224  # working resolution for PCA (matches autoencoder)
DEFAULT_TRAIN_RATIO = 0.10

# Maximum components to fit
DEFAULT_MAX_COMPONENTS = 80

# Number of components to evaluate: 80, 75, 70, ..., 5
DEFAULT_COMPONENTS = list(range(80, 0, -5))
