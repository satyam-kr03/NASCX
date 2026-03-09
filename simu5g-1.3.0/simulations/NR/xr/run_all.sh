#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# determine mode (pca or ae) from first argument
MODE=${1:-pca}
if [[ "$MODE" != "pca" && "$MODE" != "ae" ]]; then
    echo "Invalid mode '$MODE' (use 'pca' or 'ae')" >&2
    exit 1
fi

echo "Starting the data pipeline (mode=$MODE)..."

datadir="datasets_${MODE}"

# 1. Generate the dataset
# python generate_dataset.py --repetitions 3 --mode $MODE

# 2. Clean the dataset
if [[ -d "$datadir" ]]; then
    echo "Cleaning dataset in $datadir..."
    pushd "$datadir" >/dev/null
    # supply both input and output paths so the script can write the
    # cleaned CSV; by convention we append ``_clean`` to the filename.
    python clean_dataset.py random_cl_dataset.csv random_cl_dataset_clean.csv
    popd >/dev/null
else
    echo "Warning: directory $datadir" does not exist, skipping clean
fi

# 3. Train models
echo "Training models..."
python stage_one_model.py --mode $MODE
python stage_two_model.py --mode $MODE

# 4. Start the model server
# Running in background so the script can proceed to the comparison
echo "Starting model server..."
python model_server.py --mode $MODE &
SERVER_PID=$!

# Brief pause to allow the server to initialize
sleep 2

# 5. Run comparison
echo "Running parallel comparisons..."
python run_comparison_parallel.py --num-users 10 --mode $MODE

# 6. Plot results
echo "Generating plots..."
python plot_comparison.py --mode $MODE

# Cleanup: Stop the server process
kill $SERVER_PID

echo "Pipeline complete."
