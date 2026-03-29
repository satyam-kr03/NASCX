import pandas as pd
from classifier import train_all, prepare_training_targets, MAX_USERS

df = pd.read_csv("../datasets/pca/dataset.csv")
num_users_list = sorted(df["num_users"].unique().tolist())
for n in num_users_list:
    if n > MAX_USERS: continue
    X, Y, M = prepare_training_targets(df, n)
    if X.isna().sum().sum() > 0:
        print(f"NaNs found in X for num_users={n}")
    if Y.isna().sum().sum() > 0:
        print(f"NaNs found in Y for num_users={n}")
