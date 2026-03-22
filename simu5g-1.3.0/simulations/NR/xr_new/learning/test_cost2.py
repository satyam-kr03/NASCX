import pandas as pd
from lag_utils import add_lagged_delay

def test_cost():
    df = pd.read_csv("../datasets/pca/dataset.csv")
    for num_users in range(2, 11):
        df_n = df[df["num_users"] == num_users].copy()
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
        # Divide by maximum to keep it strictly bounded <= 1 without shifting zero
        df_n["total_error_scaled"] = df_n["total_error"] / (df_n["total_error"].max() + 1e-8)
        
        # Scale penalty so that 80^2 (6400) * penalty reaches ~1.0 for 10 users
        # 1.0 / 6400 = 0.00015
        # So we use a base multiplier
        base_mul = 1.0 / (80.0 ** 2)
        penalty_weight_new = base_mul * (max(0, num_users - 2) ** 3.0)
        
        df_n["new_cost"] = df_n["total_error_scaled"] + (penalty_weight_new * (avg_comps_per_user ** 2))

        # GROUPING
        df_n["error_at_80_bin"] = (df_n["error_at_80"] / 1000).round() * 1000
        df_n["error_ratio_bin"] = (df_n["error_ratio"] / 2.0).round() * 2.0
        df_n["avg_cqi_bin"] = (df_n[[f"user{i}_cqi" for i in range(num_users)]].mean(axis=1) / 2.0).round() * 2.0
        df_n["avg_fps_bin"] = (df_n[[f"user{i}_frame_rate" for i in range(num_users)]].mean(axis=1) / 10).round() * 10
        if num_users > 3:
            df_n["avg_delay_bin"] = (df_n[[f"prev_user{i}_delay_ms" for i in range(num_users)]].mean(axis=1) / 25).round() * 25
            group_cols = ["error_at_80_bin", "error_ratio_bin", "avg_cqi_bin", "avg_fps_bin", "avg_delay_bin"]
        else:
            group_cols = ["error_at_80_bin", "error_ratio_bin"]
            for i in range(num_users):
                df_n[f"prev_user{i}_delay_ms_bin"] = (df_n[f"prev_user{i}_delay_ms"] / 50).round() * 50
                group_cols += [f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms_bin"]

        opt_old_idx = df_n.groupby(group_cols)["old_cost"].idxmin().dropna()
        old_opt = df_n.loc[opt_old_idx]
        
        opt_new_idx = df_n.groupby(group_cols)["new_cost"].idxmin().dropna()
        new_opt = df_n.loc[opt_new_idx]
        
        print(f"[{num_users} users] old={old_opt[comp_cols].mean().mean():.2f} | new={new_opt[comp_cols].mean().mean():.2f}")

test_cost()
