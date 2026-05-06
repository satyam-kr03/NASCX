import pandas as pd

file_path = '/home/teaching/Projects/NASCX/adaptive_compression/pca_sweep_summary_best_rescaled.csv'
df = pd.read_csv(file_path)

df['frame_complexity'] = 124228
df.to_csv(file_path, index=False)
print("CSV updated successfully.")
