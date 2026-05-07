# compression/constants.py
#
# Shared constants for the PCA compression pipeline.

# Random seed for reproducibility across train/test splits
RANDOM_SEED = 42

# Fraction of video frames used for PCA fitting (remainder for evaluation)
DEFAULT_TRAIN_RATIO = 0.3

# Maximum PCA components to retain during fitting
DEFAULT_MAX_COMPONENTS = 80

# Working image resolution (frames are resized to this square size)
DEFAULT_IMG_SIZE = 224

# Component counts to evaluate in the sweep
DEFAULT_COMPONENTS = list(range(5, 81, 5))  # [5, 10, 15, ..., 80]
