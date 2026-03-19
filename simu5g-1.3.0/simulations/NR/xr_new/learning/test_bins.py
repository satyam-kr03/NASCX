import pandas as pd
import numpy as np

df = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv')
df = df[df['num_users'] == 2].copy()
df['total_error'] = df['user0_effectiveError'] + df['user1_effectiveError']

# Binning
df['error_at_80_bin'] = pd.cut(df['error_at_80'], bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
df['error_ratio_bin'] = pd.cut(df['error_ratio'], bins=[0, 0.25, 0.5, 0.75, 1.0])
df['cqi'] = df['user0_cqi']
df['fps'] = df['user0_frame_rate']
df['prev_user0_delay_ms'] = df.groupby('repetition')['user0_delay_ms'].shift(1)
df['prev_user0_delay_ms_bin'] = pd.cut(df['prev_user0_delay_ms'], bins=[-np.inf, 20, 50, 100, np.inf])

# Group by
groups = df.groupby(['error_at_80_bin', 'error_ratio_bin', 'cqi', 'fps', 'prev_user0_delay_ms_bin'])

count = 0
for name, group in groups:
    if len(group) > 5:  # Only show groups with multiple points
        print(f"Group: {name} (size {len(group)})")
        print(group[['user0_components', 'total_error']].head(20).to_string(index=False))
        print("-" * 50)
        count += 1
        if count >= 5:
            break
