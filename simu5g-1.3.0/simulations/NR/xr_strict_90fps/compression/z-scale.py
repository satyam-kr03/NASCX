import pandas as pd

# 1. Load the original data
df = pd.read_csv('traffic_files/pca/pca_sweep_summary_vietnam.csv')

# 2. Define the target parameters
fps = 60
target_mbps = 60

# Calculate the target bytes for 40 components
# 30 Mbps = 30,000,000 bits/sec
# Target bytes per frame = (30,000,000 bits/sec / 60 frames/sec) / 8 bits/byte
target_bytes_40_comp = (target_mbps * 1e6) / (fps * 8) 

# 3. Get current statistics from the entire dataset
mu_old = df['size_bytes'].mean()
sigma_old = df['size_bytes'].std()

# Get the original mean size specifically for 40 components
size_40_old = df[df['components'] == 80]['size_bytes'].mean()

# 4. Z-score Standardization
# Formula: Z = (X - μ) / σ
df['z_score_size'] = (df['size_bytes'] - mu_old) / sigma_old

# 5. Linear Rescaling
# Determine the scaling factor to match the 40-component target
scaling_factor = target_bytes_40_comp / size_40_old
    
# Scale the mean and standard deviation proportionally
mu_new = mu_old * scaling_factor
sigma_new = sigma_old * scaling_factor

# Apply linear rescaling formula: S_new = (σ_new * Z) + μ_new
df['size_bytes_rescaled'] = (sigma_new * df['z_score_size']) + mu_new
df['size_bytes'] = df['size_bytes_rescaled'].astype(int)


# --- Verification & Output ---

# Group by components to verify the new sizes
summary_df = df.groupby('components')[['size_bytes', 'size_bytes_rescaled']].mean().reset_index()
print("Verification Summary:")
print(summary_df)

df.drop(columns=['size_bytes_rescaled'], inplace=True)
df.drop(columns=['z_score_size'], inplace=True)

# 6. Save the rescaled data to a new CSV file
output_filename = 'traffic_files/pca/pca_sweep_summary_vietnam.csv'
df.to_csv(output_filename, index=False)
print(f"\nSuccessfully saved rescaled dataset to {output_filename}")