import pandas as pd
import numpy as np
import os
import sys
sys.path.append("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning")
from lag_utils import check_lag_quality

# Load dataset
dataset_path = "/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv"
df = pd.read_csv(dataset_path)

# Load pca sweep
pca_sweep_path = "/home/teaching/Projects/NASCX/adaptive_compression/pca_sweep_summary_billiards.csv" # wait, which sweep file?
if not os.path.exists(pca_sweep_path):
    print("PCA sweep not found at", pca_sweep_path)

