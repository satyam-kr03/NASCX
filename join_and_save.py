import pandas as pd
import numpy as np

# Load dataset
ds_path = '/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv'
df = pd.read_csv(ds_path)

# Load sweep summary and get exactly error_at_k80 and error_ratio
sweep = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/compression/traffic_files/pca/pca_sweep_summary_billiards.csv')

# Note the requested feature name is 'error_at_80'
# The file has 'error_at_k80'
sweep_feats = sweep[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates()
sweep_feats = sweep_feats.rename(columns={'error_at_k80': 'error_at_80'})

# Join onto the dataset
df = df.merge(sweep_feats, left_on='frameNumber', right_on='frame', how='left')
df = df.drop(columns=['frame']) # from the merge

# Save dataset back
df.to_csv(ds_path, index=False)
print("Saved modified dataset with new features")
