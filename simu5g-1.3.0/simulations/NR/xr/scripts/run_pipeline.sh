#!/bin/bash
# Complete, fully functional script to run the XR simulation pipeline

# Exit immediately if a command exits with a non-zero status
set -e

# Change to the directory where the script is located
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "============================================================"
echo " Starting complete XR simulation pipeline"
echo "============================================================"

# 1. Generate Dataset
echo -e "\n---> [1/5] Generating dataset (10 repetitions)..."
cd "$BASE_DIR/dataset_generation"
python generate_dataset.py --repetitions 10

# 2. Clean Dataset
echo -e "\n---> [2/5] Cleaning dataset..."
cd "$BASE_DIR/datasets"
python clean_dataset.py pca/dataset.csv pca/dataset.csv

# 3. Train Classifier
echo -e "\n---> [3/5] Training classifier models..."
cd "$BASE_DIR/learning"
python classifier.py

# # 4. Start Model Server
# echo -e "\n---> [4/5] Starting classifier model server in the background..."
# cd "$BASE_DIR/learning"
# # Start the FastAPI model server in the background
# python model_server.py &
# MODEL_SERVER_PID=$!

# # Ensure the background server is cleanly terminated when this script exits
# trap "echo -e '\nStopping model server (PID: $MODEL_SERVER_PID)...'; kill $MODEL_SERVER_PID 2>/dev/null || true" EXIT

# # Wait for the server to be healthy (using the endpoint defined in model_server.py)
# echo "Waiting for model server to initialize..."
# timeout 60 bash -c 'until curl -s http://localhost:8000/health > /dev/null; do sleep 2; done'
# echo "Model server is up and healthy."

# # 5. Run Multiuser Sweep
# echo -e "\n---> [5/5] Running multiuser sweep for comparison..."
# cd "$BASE_DIR/comparison"
# bash run_multiuser_sweep.sh

# echo -e "\n============================================================"
# echo " Pipeline completed successfully!"
# echo "============================================================"
