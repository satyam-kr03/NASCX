import pandas as pd
import numpy as np

def run_test():
    # Load dataset
    df = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv')
    
    # Load sweep summary and get exactly error_at_k80 and error_ratio
    sweep = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/compression/traffic_files/pca/pca_sweep_summary_billiards.csv')
    sweep_feats = sweep[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates()
    
    # Join onto the dataset
    df = df.merge(sweep_feats, left_on='frameNumber', right_on='frame', how='left')
    
    # We will test on num_users=4 for a representative sample, or test all groups
    for num_users in sorted(df['num_users'].unique()):
        print(f"--- Users: {num_users} ---")
        df_u = df[df['num_users'] == num_users].copy()
        
        # We replace the old prev_delay usage with our new features
        # Just as in check_lag_quality:
        print(f"  Feature quality ({len(df_u):,} rows):")
        for i in range(int(num_users)):
            c1 = df_u[['error_at_k80', f"user{i}_components"]].corr().iloc[0, 1]
            c2 = df_u[['error_ratio', f"user{i}_components"]].corr().iloc[0, 1]
            print(f"    error_at_k80 ↔ components_u{i}: {c1:+.3f}")
            print(f"    error_ratio  ↔ components_u{i}: {c2:+.3f}")

        # Binning for state consistency test
        df_u["total_error"] = df_u[[f"user{i}_effectiveError" for i in range(int(num_users))]].sum(axis=1)
        
        # Define bins: e.g., 50 increments for error_at_k80 and 0.1 for error_ratio
        df_u["error_at_k80_bin"] = (df_u["error_at_k80"] / 50).round() * 50
        df_u["error_ratio_bin"] = (df_u["error_ratio"] / 0.1).round() * 0.1
        
        state_cols = []
        for i in range(int(num_users)):
            state_cols += [f"user{i}_cqi", f"user{i}_frame_rate"]
            
        state_cols_ext = state_cols + ["error_at_k80_bin", "error_ratio_bin"]
        
        opt_idx = df_u.groupby(state_cols_ext)["total_error"].idxmin()
        opt_df  = df_u.loc[opt_idx]
        print(f"  Unique (cqi, fps, error_80_bin, error_ratio_bin) states: {len(opt_df):,}")

        for i in range(int(num_users)):
            col   = f"user{i}_components"
            stats = df_u.groupby(state_cols_ext)[col].agg(["nunique","count"])
            multi = stats[stats["count"] > 1]
            if len(multi) == 0:
                print(f"  user{i}: no multi-row states"); continue
            always_same = (multi["nunique"] == 1).mean() * 100
            avg_unique  = multi["nunique"].mean()
            print(f"  user{i}: {always_same:.1f}% of states → same k  "
                  f"(avg {avg_unique:.1f} distinct k per state)")

if __name__ == '__main__':
    run_test()
