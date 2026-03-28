import pandas as pd
from classifier import prepare_training_targets, MAX_USERS

df = pd.read_csv('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/dataset_full.csv')
X, Y, M = prepare_training_targets(df, num_users=2, max_users=MAX_USERS)
print(X.shape, Y.shape, M.shape)
print("X cols:", X.columns.tolist()[:10])
