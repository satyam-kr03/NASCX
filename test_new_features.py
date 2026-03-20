import pandas as pd
import numpy as np

df = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv")

# We assume video_type is available or we just use billiards
frames_df_billiards = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/compression/traffic_files/pca/pca_sweep_summary_billiards.csv")
frames_df_billiards = frames_df_billiards[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates()

# Assuming dataset has a 'frameNumber' column and it maps directly. We might need to join for each user or just frameNumber.
print("Dataset columns:", df.columns.tolist())
