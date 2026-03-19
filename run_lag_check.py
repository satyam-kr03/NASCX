import pandas as pd
from lag_utils import check_lag_quality

def check_feature_quality(df_feat: pd.DataFrame, num_users: int):
    print(f"  Feature quality ({len(df_feat):,} rows):")
    for i in range(num_users):
        c1 = (df_feat[[f"error_at_80", f"user{i}_components"]].corr().iloc[0, 1])
        c2 = (df_feat[[f"error_ratio", f"user{i}_components"]].corr().iloc[0, 1])
        b1 = "█" * max(0, int(abs(c1) * 50))
        b2 = "█" * max(0, int(abs(c2) * 50))
        s1 = "+" if c1 >= 0 else "-"
        s2 = "+" if c2 >= 0 else "-"
        print(f"    error_at_80 ↔ components_u{i}: {s1}{abs(c1):.3f}  {b1}")
        print(f"    error_ratio ↔ components_u{i}: {s2}{abs(c2):.3f}  {b2}")

    err_cols   = [f"user{i}_effectiveError" for i in range(num_users)]
    state_cols = []
    for i in range(num_users):
        state_cols += [f"user{i}_cqi", f"user{i}_frame_rate"]

    df_feat = df_feat.copy()
    df_feat["total_error"] = df_feat[err_cols].sum(axis=1)

    df_feat[f"error_at_80_bin"] = (df_feat["error_at_80"] / 50).round() * 50
    df_feat[f"error_ratio_bin"] = (df_feat["error_ratio"] / 0.1).round() * 0.1

    state_cols_ext = state_cols + ["error_at_80_bin", "error_ratio_bin"]

    opt_idx = df_feat.groupby(state_cols_ext)["total_error"].idxmin()
    opt_df  = df_feat.loc[opt_idx]
    print(f"  Unique (cqi, fps, err80_bin, errR_bin) states: {len(opt_df):,}")

    for i in range(num_users):
        col   = f"user{i}_components"
        stats = df_feat.groupby(state_cols_ext)[col].agg(["nunique","count"])
        multi = stats[stats["count"] > 1]
        if len(multi) == 0:
            print(f"  user{i}: no multi-row states"); continue
        always_same = (multi["nunique"] == 1).mean() * 100
        avg_unique  = multi["nunique"].mean()
        print(f"  user{i}: {always_same:.1f}% of states → same k  "
              f"(avg {avg_unique:.1f} distinct k per state)")


df = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv')
for u in sorted(df['num_users'].unique()):
    print(f"\n--- Checking features for {u} users ---")
    df_u = df[df['num_users'] == u].copy()
    check_feature_quality(df_u, u)

