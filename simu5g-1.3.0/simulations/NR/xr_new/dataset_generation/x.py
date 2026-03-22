import pandas as pd
import sys

# Add custom module path
sys.path.append("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning")
from lag_utils import add_lagged_delay

# Load the dataset
df = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv")

# Filter for 10 users and apply delay function
df_n = df[df["num_users"] == 10].copy()
df_n = add_lagged_delay(df_n, 10)

# Bin the delay data for all 10 users into 50ms buckets
for i in range(10):
    df_n[f"prev_user{i}_delay_ms_bin"] = (df_n[f"prev_user{i}_delay_ms"] / 50).round() * 50

# Create additional bins for error metrics
df_n["error_at_80_bin"] = (df_n["error_at_80"] / 1000).round() * 1000
df_n["error_ratio_bin"] = (df_n["error_ratio"] / 2.0).round() * 2.0

# Define columns for grouping
group_cols = ["error_at_80_bin", "error_ratio_bin"]
for i in range(10):
    group_cols += [
        f"user{i}_cqi", 
        f"user{i}_frame_rate",
        f"prev_user{i}_delay_ms_bin"
    ]

# Calculate group sizes
sizes = df_n.groupby(group_cols).size()

# Print the final statistics
print(f"Total rows: {len(df_n)}")
print(f"Total groups: {len(sizes)}")
print(f"Groups of size 1: {(sizes == 1).sum()} ({(sizes == 1).sum() / len(sizes) * 100:.2f}%)")