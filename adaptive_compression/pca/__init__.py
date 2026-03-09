# pca/__init__.py

__version__ = "2.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224  # working resolution for PCA (matches autoencoder)
DEFAULT_TRAIN_RATIO = 0.20

# Maximum components to fit
DEFAULT_MAX_COMPONENTS = 200

# Number of components to evaluate: 200, 195, 190, ..., 10, 5
DEFAULT_COMPONENTS = list(range(200, 0, -5))
