import pandas as pd
import sys

def augment_csv(input_file, output_file):
    df = pd.read_csv(input_file)
    
    # Extract the mse at components = 80 and 5 for each frame
    error_80 = df[df['components'] == 80].set_index('frame')['mse']
    error_5 = df[df['components'] == 5].set_index('frame')['mse']
    
    # Create the new columns
    df['error_at_k80'] = df['frame'].map(error_80)
    df['error_ratio'] = df['frame'].map(error_5) / df['error_at_k80']
    
    # Save the updated dataframe
    df.to_csv(output_file, index=False)
    print(f"Successfully processed {input_file} and saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    else:
        input_csv = 'pca_sweep_summary.csv'
        
    augment_csv(input_csv, input_csv)
