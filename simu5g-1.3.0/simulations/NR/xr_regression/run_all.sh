#!/bin/bash
# Complete, fully functional script to run the XR simulation pipeline
# Derived from the provided outline.

# Exit immediately if a command exits with a non-zero status
set -e

# Change to the directory where the script is located
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo " Starting complete XR simulation pipeline"
echo "============================================================"

# 1. Generate Dataset
echo -e "\n---> [1/6] Generating dataset (10 repetitions)..."
cd "$BASE_DIR/dataset_generation"
# python generate_dataset.py --repetitions 10 # skip if already generated 

# 2. Clean Dataset
echo -e "\n---> [2/6] Cleaning dataset..."
cd "$BASE_DIR/datasets"
# python clean_dataset.py pca/dataset.csv pca/dataset.csv 

# 3. Join Datasets
echo -e "\n---> [3/6] Joining datasets..."
cd "$BASE_DIR"
# python join_datasets.py

# 4. Train Classifier
echo -e "\n---> [4/6] Training classifier models..."
cd "$BASE_DIR/learning"
python classifier.py

# 5. Start Model Server
echo -e "\n---> [5/6] Starting classifier model server in the background..."
cd "$BASE_DIR/learning"
# Start the FastAPI model server in the background
python classifier_model_server.py &
MODEL_SERVER_PID=$!

# Ensure the background server is cleanly terminated when this script exits
trap "echo -e '\nStopping model server (PID: $MODEL_SERVER_PID)...'; kill $MODEL_SERVER_PID 2>/dev/null || true" EXIT

# Wait for the server to be healthy (using the endpoint defined in classifier_model_server.py)
echo "Waiting for model server to initialize..."
# timeout 60 bash -c 'until curl -s http://localhost:8000/health > /dev/null; do sleep 2; done'
echo "Model server is up and healthy."

# 6. Run Multiuser Sweep
echo -e "\n---> [6/6] Running multiuser sweep for comparison..."
cd "$BASE_DIR/comparison"
bash run_multiuser_sweep.sh

echo -e "\n============================================================"
echo " Pipeline completed successfully!"
echo "============================================================"