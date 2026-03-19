import pandas as pd
import numpy as np
from lag_utils import add_lagged_delay

df = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv')
num_users = df['num_users'].iloc[0] # assuming single num_users for test, wait dataset.csv might have multiple

sweep = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/compression/traffic_files/pca/pca_sweep_summary_billiards.csv')
sweep_feats = sweep[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates()

df = df.merge(sweep_feats, left_on='frameNumber', right_on='frame', how='left')

for u in [2, 4, 6]:
    df_u = df[df['num_users'] == u].copy()
    if len(df_u) == 0: continue
    
    # We want to run check_lag_quality on these two features alone
    
    err_cols   = [f"user{i}_effectiveError" for i in range(u)]
    state_cols = []
    for i in range(u):
        state_cols += [f"user{i}_cqi", f"user{i}_frame_rate"]
        
    df_u["total_error"] = df_u[err_cols].sum(axis=1)
    
    # state consistency based on these two features alone!
    # Let's bin error_at_k80 and error_ratio
    
    # Let's print the unique states
    # bin error_at_k80 by 50, error_ratio by 0.1
    # Actually, they are continuous, maybe binning them?
    # Let's see how they should be binned.
    pass

