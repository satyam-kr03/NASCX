import pandas as pd
from lag_utils import add_lagged_delay

def test_cost(pw):
    df = pd.read_csv("../datasets/pca/dataset.csv")
    num_users = 10
    df_n = df[df["num_users"] == 10].copy()
    df_n = add_lagged_delay(df_n, num_users)
    err_cols  = [f"user{i}_effectiveError" for i in range(num_users)]
    comp_cols = [f"user{i}_components" for i in range(num_users)]
    df_n["total_error"] = df_n[err_cols].sum(axis=1)
    df_n["total_components"] = df_n[comp_cols].sum(axis=1)
    
    # OLD COST
    avg_comps_per_user = df_n["total_components"] / num_users
    penalty_weight_old = 0.8 * (max(0, num_users - 2) ** 3.0)
    df_n["old_cost"] = df_n["total_error"] + (penalty_weight_old * (avg_comps_per_user ** 2))

    # NEW COST
    error_min = df_n["total_error"].min()
    error_max = df_n["total_error"].max()
    df_n["total_error_scaled"] = (df_n["total_error"] - error_min) / (error_max - error_min + 1e-8)
    
    comp_min = avg_comps_per_user.min()
    comp_max = avg_comps_per_user.max()
    avg_comps_scaled = (avg_comps_per_user - comp_min) / (comp_max - comp_min + 1e-8)
    
    df_n["new_cost"] = df_n["total_error_scaled"] + (pw * (avg_comps_scaled ** 2))

    # GROUPING
    df_n["error_at_80_bin"] = (df_n["error_at_80"] / 1000).round() * 1000
    df_n["error_ratio_bin"] = (df_n["error_ratio"] / 2.0).round() * 2.0
    df_n["avg_cqi_bin"] = (df_n[[f"user{i}_cqi" for i in range(num_users)]].mean(axis=1) / 2.0).round() * 2.0
    df_n["avg_fps_bin"] = (df_n[[f"user{i}_frame_rate" for i in range(num_users)]].mean(axis=1) / 10).round() * 10
    df_n["avg_delay_bin"] = (df_n[[f"prev_user{i}_delay_ms" for i in range(num_users)]].mean(axis=1) / 25).round() * 25
    group_cols = ["error_at_80_bin", "error_ratio_bin", "avg_cqi_bin", "avg_fps_bin", "avg_delay_bin"]

    opt_old_idx = df_n.groupby(group_cols)["old_cost"].idxmin().dropna()
    old_opt = df_n.loc[opt_old_idx]
    
    opt_new_idx = df_n.groupby(group_cols)["new_cost"].idxmin().dropna()
    new_opt = df_n.loc[opt_new_idx]
    
    print(f"pw={pw:.2f} | old={old_opt[comp_cols].mean().mean():.2f} | new={new_opt[comp_cols].mean().mean():.2f}")

for p in [0.0, 0.1, 1.0, 10.0, 400.0, 10000.0]:
    test_cost(p)
