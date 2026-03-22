import pandas as pd
df = pd.read_csv("../datasets/pca/dataset.csv")
num_users = 10
df_n = df[df["num_users"] == 10].copy()
err_cols  = [f"user{i}_effectiveError" for i in range(num_users)]
comp_cols = [f"user{i}_components" for i in range(num_users)]
df_n["total_error"] = df_n[err_cols].sum(axis=1)

print("Total elements:", len(df_n))
print("NaNs in total_error:", df_n["total_error"].isna().sum())

# min-max scaling across dataset
error_min = df_n["total_error"].min()
error_max = df_n["total_error"].max()
df_n["total_error_scaled"] = (df_n["total_error"] - error_min) / (error_max - error_min + 1e-8)

print("NaNs in total_error_scaled:", df_n["total_error_scaled"].isna().sum())

