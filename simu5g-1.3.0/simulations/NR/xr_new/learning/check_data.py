import pandas as pd
df = pd.read_csv("../datasets/pca/dataset.csv")
df_n = df[df["num_users"] == 10]
comp_cols = [f"user{i}_components" for i in range(10)]
df_n["total_components"] = df_n[comp_cols].sum(axis=1)
print(df_n["total_components"].describe())
print(df_n[comp_cols[0]].value_counts())
