#!/bin/bash

# Script to generate surrogate datasets and train neural network models
# for XR compression optimization across different numbers of users (2 to 10).

# Activate the conda environment
source /home/teaching/miniconda3/etc/profile.d/conda.sh
conda activate mlc

# Change to the simulation directory
cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr

# Loop over number of users from 2 to 10
for num_users in {5..10}
do
    echo "=========================================="
    echo "Processing num_users = $num_users"
    echo "=========================================="

    # Generate the surrogate dataset
    echo "Generating dataset for $num_users users..."
    python generate_per_frame_dataset.py --num-users $num_users --runs 10 --workers 32

    # Check if dataset was created successfully
    if [ ! -f "datasets/surrogate_n${num_users}.csv" ]; then
        echo "Error: Dataset file not found for num_users=$num_users. Skipping training."
        continue
    fi

    # Train the neural network model
    echo "Training model for $num_users users..."
    python train_nn.py --data datasets/surrogate_n${num_users}.csv --num-users $num_users --epochs 200

    echo "Completed processing for num_users = $num_users"
    echo ""
done

echo "All tasks completed."