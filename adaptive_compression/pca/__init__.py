# pca/__init__.py

__version__ = "1.0.0"

# Constants
RANDOM_SEED = 42
DEFAULT_IMG_SIZE = 224
DEFAULT_TRAIN_RATIO = 0.15

# Maximum components to fit
DEFAULT_MAX_COMPONENTS = 80

# Number of components to evaluate (5, 10, 15, ..., 80)
DEFAULT_COMPONENTS = list(range(80, 0, -5))  # [80, 75, 70, ..., 5]
