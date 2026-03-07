# pca/__init__.py

__version__ = "2.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224  # working resolution for PCA (matches autoencoder)
DEFAULT_TRAIN_RATIO = 0.30

# Maximum components to fit
DEFAULT_MAX_COMPONENTS = 400

# Number of components to evaluate: [80, 75, 70, ..., 5]
DEFAULT_COMPONENTS = list(range(400, 0, -25))
