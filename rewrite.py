import re

with open("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py", "r") as f:
    text = f.read()

old_block = re.search(r"def prepare_training_targets\(df: pd\.DataFrame, num_users: int\):.*?return X, pd\.DataFrame\(\{\"target\": Y\}\)", text, re.DOTALL)

new_block = """def prepare_training_targets(df: pd.DataFrame, num_users: int):
    \"\"\"
    Finds the JOINT configuration that minimized total error, and then
    melts those optimal rows into individual user targets to train the
    single-user model to act cooperatively.
    \"\"\"
    df_n = df[df["num_users"] == num_users].copy()
    df_n = add_lagged_delay(df_n, num_users)

    # Bin global states to identify repeated scenarios
    df_n["error_at_80_bin"] = (df_n["error_at_80"] / 1000).round() * 1000
    df_n["error_ratio_bin"] = (df_n["error_ratio"] / 2.0).round() * 2.0
    
    # Calculate total error for joint optimality
    err_cols = [f"user{i}_effectiveError" for i in range(num_users)]
    df_n["total_error"] = df_n[err_cols].sum(axis=1)

    # Joint state groups
    group_cols = ["error_at_80_bin", "error_ratio_bin"]
    for i in range(num_users):
        df_n[f"prev_user{i}_delay_ms_bin"] = (df_n[f"prev_user{i}_delay_ms"] / 50).round() * 50
        group_cols += [f"user{i}_cqi", f"user{i}_frame_rate", f"prev_user{i}_delay_ms_bin"]

    # 1. Find the scenario that minimized TOTAL cell error
    optimal_idx = df_n.groupby(group_cols)["total_error"].idxmin()
    opt_joint = df_n.loc[optimal_idx].reset_index(drop=True)

    # 2. Melt these optimally cooperative rows into single-user views
    melted_rows = []
    for _, row in opt_joint.iterrows():
        err80 = row["error_at_80"]
        errRat = row["error_ratio"]
        
        all_cqi = [row[f"user{i}_cqi"] for i in range(num_users)]
        all_fps = [row[f"user{i}_frame_rate"] for i in range(num_users)]
        
        for i in range(num_users):
            my_cqi = row[f"user{i}_cqi"]
            my_fps = row[f"user{i}_frame_rate"]
            my_delay = row[f"prev_user{i}_delay_ms"]
            my_comp = row[f"user{i}_components"]
            
            other_cqi_mean = (sum(all_cqi) - my_cqi) / max((num_users - 1), 1)
            other_fps_sum  = sum(all_fps) - my_fps
            
            melted_rows.append({
                "error_at_80": err80,
                "error_ratio": errRat,
                "my_cqi": my_cqi,
                "my_fps": my_fps,
                "my_delay": my_delay,
                "other_cqi_mean": other_cqi_mean,
                "other_fps_sum": other_fps_sum,
                "target_components": my_comp
            })

    opt_melt = pd.DataFrame(melted_rows)
    
    state_cols = ["error_at_80", "error_ratio", "my_cqi", "my_fps", "my_delay", "other_cqi_mean", "other_fps_sum"]
    X = opt_melt[state_cols].copy()
    Y = (opt_melt["target_components"] / COMP_STEP - COMP_OFFSET).astype(int)
    
    print(f"  [{num_users} users] {len(X)} cooperative single-user states "
          f"(from {len(opt_joint):,} optimal joint states)")
          
    return X, pd.DataFrame({"target": Y})"""

if old_block:
    new_text = text[:old_block.start()] + new_block + text[old_block.end():]
    with open("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py", "w") as f:
        f.write(new_text)
    print("Replaced!")
else:
    print("Could not find block.")
