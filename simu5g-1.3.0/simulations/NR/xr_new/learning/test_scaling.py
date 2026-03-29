import pandas as pd
from classifier import train_all, prepare_training_targets, MAX_USERS
from sklearn.model_selection import train_test_split

df = pd.read_csv("../datasets/pca/dataset.csv")
num_users_list = sorted(df["num_users"].unique().tolist())
all_X = []
all_Y = []
all_M = []
for n in num_users_list:
    if n > MAX_USERS: continue
    X, Y, M = prepare_training_targets(df, n)
    all_X.append(X)
    all_Y.append(Y)
    all_M.append(M)
    
X_full = pd.concat(all_X, ignore_index=True)
Y_full = pd.concat(all_Y, ignore_index=True)
M_full = pd.concat(all_M, ignore_index=True)

X_tr, X_te, Y_tr, Y_te, M_tr, M_te = train_test_split(
    X_full, Y_full, M_full, test_size=0.2, random_state=42
)
X_tr_sc = X_tr.copy()
for c in X_tr.columns:
    valid_train = X_tr[c][X_tr[c] != 0.0]
    if len(valid_train) > 0:
        mean, std = valid_train.mean(), valid_train.std()
        if pd.isna(std): std = 1.0
        if std == 0.0: std = 1.0
        X_tr_sc[c] = X_tr_sc[c].apply(lambda v: (v - mean) / std if v != 0.0 else 0.0)

print("NaNs in X_tr_sc:", X_tr_sc.isna().sum().sum())
print("Is any valid_train std NaN? let's check:")
for c in X_tr.columns:
    valid_train = X_tr[c][X_tr[c] != 0.0]
    if len(valid_train) > 0:
        std = valid_train.std()
        if pd.isna(std):
            print(f"Col {c} has NaN std, len={len(valid_train)}")

