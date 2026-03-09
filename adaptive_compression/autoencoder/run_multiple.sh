#!/bin/bash
# Script to run autoencoder  compression analysis on multiple videos
# Usage: ./run_multiple.sh

set -e

VIDEOS=(
  "/home/teaching/Projects/NASCX/data/yt360-videos/minecraft.mp4"
  "/home/teaching/Projects/NASCX/data/yt360-videos/elevator.mp4"
  "/home/teaching/Projects/NASCX/data/yt360-videos/pacman.mp4"
  "/home/teaching/Projects/NASCX/data/yt360-videos/slide.mp4"
  "/home/teaching/Projects/NASCX/data/yt360-videos/tunnel.mp4"
)

for vid in "${VIDEOS[@]}"; do
  # extract base name without extension
  name=$(basename "$vid" .mp4)
  out_csv="ae_sweep_summary_${name}.csv"

  echo "Running autoencoder analysis for $vid -> $out_csv"
  # execute the ae module directly; it now uses package imports
  python -m adaptive_compression.ae \
    --video-path "$vid" \
    --output-csv "$out_csv"

  echo "Finished $name"
  echo

done
