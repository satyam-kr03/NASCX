import pandas as pd

dataset_path = '/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv'
print(f"Loading {dataset_path}...")
df = pd.read_csv(dataset_path)

if 'error_at_80' in df.columns:
    print("Migrating global error_at_80 to per-user features...")
    for i in range(10):
        df[f'user{i}_error_at_80'] = df['error_at_80']
        df[f'user{i}_error_ratio'] = df['error_ratio']
    
    df.drop(columns=['error_at_80', 'error_ratio'], inplace=True)
    df.to_csv(dataset_path, index=False)
    print("Dataset updated successfully.")
else:
    print("Dataset already migrated.")
