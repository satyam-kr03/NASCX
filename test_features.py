import pandas as pd
import numpy as np

# Load dataset
df = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv")

# Load sweep
sweep = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/compression/traffic_files/pca/pca_sweep_summary_billiards.csv")
sweep_features = sweep[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates().rename(columns={'frame': 'frameNumber'})

# Merge
df = df.merge(sweep_features, on='frameNumber', how='inner')

for num_users in sorted(df['num_users'].dropna().unique()):
    num_users = int(num_users)
    print(f"\n--- Checking Num Users: {num_users} ---")
    df_u = df[df['num_users'] == num_users].copy()

    # Correlation checks
    for i in range(num_users):
        for feat in ['error_at_k80', 'error_ratio']:
            c = df_u[[feat, f"user{i}_components"]].corr().iloc[0, 1]
            if not pd.isna(c):
                bar = "█" * max(0, int(abs(c) * 50))
                sign = "+" if c >= 0 else "-"
                print(f"  {feat} ↔ components_u{i}: {sign}{abs(c):.3f}  {bar}")

    # State consistency check
    # State defined by: CQI, frame_rate, error_at_k80, error_ratio
    state_cols = []
    for i in range(num_users):
        state_cols += [f"user{i}_cqi", f"user{i}_frame_rate"]
    
    # We will bin error_at_k80 and error_ratio to allow consistency checking
    df_u['error_at_k80_bin'] = (df_u['error_at_k80'] / 2).round() * 2
    df_u['error_ratio_bin'] = (df_u['error_ratio'] / 2).round() * 2
    state_cols_ext = state_cols + ['error_at_k80_bin', 'error_ratio_bin']

    err_cols = [f"user{i}_effectiveError" for i in range(num_users)]
    df_u["total_error"] = df_u[err_cols].sum(axis=1)

    opt_idx = df_u.groupby(state_cols_ext)["total_error"].idxmin()
    opt_df = df_u.loc[opt_idx]
    print(f"  Unique states: {len(opt_df):,}")

    for i in range(num_users):
        col = f"user{i}_components"
        stats = df_u.groupby(state_cols_ext)[col].agg(["nunique","count"])
        multi = stats[stats["count"] > 1]
        if len(multi) == 0:
            print(f"  user{i}: no multi-row states")
            continue
        always_same = (multi["nunique"] == 1).mean() * 100
        avg_unique  = multi["nunique"].mean()
        print(f"  user{i}: {always_same:.1f}% of states → same k  (avg {avg_unique:.1f} distinct k per state)")

