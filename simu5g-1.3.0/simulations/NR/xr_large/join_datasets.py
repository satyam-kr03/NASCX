import pandas as pd

# Paths to the datasets
dataset_path = '/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_large/datasets/pca/dataset.csv'
summary_path = '/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_large/compression/traffic_files/pca/pca_sweep_summary_billiards.csv'

print(f"Loading {dataset_path}...")
df_dataset = pd.read_csv(dataset_path)

print(f"Loading {summary_path}...")
df_summary = pd.read_csv(summary_path)

# Extract only the unique frame-level errors from the summary
# Since error_at_k80 and error_ratio are independent of components per frame, we drop duplicates based on frame
df_summary_unique = df_summary[['frame', 'error_at_k80', 'error_ratio']].drop_duplicates(subset=['frame'])

# Rename columns to match what the classifier expects (error_at_80)
df_summary_unique = df_summary_unique.rename(columns={'error_at_k80': 'error_at_80'})

print("Merging datasets on frameNumber == frame...")
# Merge the dataset with the summary where frameNumber matches frame
# We use a left join to preserve all rows in the dataset
df_merged = df_dataset.merge(df_summary_unique, left_on='frameNumber', right_on='frame', how='left')

# Drop the redundant 'frame' column if it exists after merge
if 'frame' in df_merged.columns:
    df_merged = df_merged.drop(columns=['frame'])

# Save the merged dataset
print(f"Saving merged dataset back to {dataset_path}...")
df_merged.to_csv(dataset_path, index=False)

print("Merge completed successfully! The dataset now contains the additional required columns (error_at_80, error_ratio).")
