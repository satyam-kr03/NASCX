#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting the data pipeline..."

# 1. Generate the dataset
python generate_dataset.py --repetitions 20

# 2. Clean the dataset
echo "Cleaning dataset..."
cd datasets
python clean_dataset.py
cd ..

# 3. Train models
echo "Training models..."
python model.py
python two_stage_model.py

# 4. Start the model server
# Running in background so the script can proceed to the comparison
echo "Starting model server..."
python model_server.py &
SERVER_PID=$!

# Brief pause to allow the server to initialize
sleep 2

# 5. Run comparison
echo "Running parallel comparisons..."
python run_comparison_parallel.py --num-users 5

# 6. Plot results
echo "Generating plots..."
python plot_comparison.py

# Cleanup: Stop the server process
kill $SERVER_PID

echo "Pipeline complete."