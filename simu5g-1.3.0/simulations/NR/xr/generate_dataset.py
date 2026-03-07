#!/usr/bin/env python3
"""
Dataset Generation Script for XR Streaming Simulation.

Generates an ML training dataset by running simu5g simulations with random
per-frame compression levels. Each user is assigned a video stream (PCA file),
and the simulation randomly selects compression levels per frame.

Usage:
    python generate_dataset.py [--dry-run] [--repetitions N] [--sim-time S]

Output:
    datasets/random_cl_dataset.csv
"""

import os
import sys
import csv
import glob
import shutil
import random
import argparse
import subprocess
import tempfile
import json
from pathlib import Path
from multiprocessing import Pool, cpu_count
from itertools import product

import pandas as pd
import numpy as np

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
TRAFFIC_DIR = SCRIPT_DIR / "traffic_files"
RESULTS_DIR = SCRIPT_DIR / "results"
DATASET_DIR = SCRIPT_DIR / "datasets"
TRIMMED_DIR = TRAFFIC_DIR / "trimmed"

# PCA sweep summary files (one per video)
PCA_FILES = sorted(TRAFFIC_DIR.glob("pca_sweep_summary_*.csv"))

MAX_FRAMES = 1000      # Only use first 2000 frames per video
FPS = 60               # Frames per second (default)
FPS_OPTIONS = [45, 60, 72, 90, 120]  # Per-user frame rate choices
SIM_TIME_LIMIT = 35    # seconds (>= 2000/60 ≈ 33.33s, with margin)
DEADLINE_MS = 5.0      # Frame deadline in ms
NUM_USERS_SWEEP = list(range(2, 11))  # 2..10 users

# Parallelism
MAX_WORKERS = min(cpu_count(), 32)


# ─── Step 1: Pre-compute frame complexity statistics ─────────────────────────

def compute_complexity_stats():
    """Compute mean and std of frame_complexity for each video.
    
    Returns dict: video_name -> {mean_traffic_size, std_traffic_size, complexity_per_frame}
    """
    stats = {}
    for pca_path in PCA_FILES:
        video_name = pca_path.stem.replace("pca_sweep_summary_", "")
        df = pd.read_csv(pca_path)
        
        # Get one row per frame (frame_complexity is same across all comp levels)
        frame_df = df.drop_duplicates(subset="frame")[["frame", "frame_complexity"]].copy()
        frame_df = frame_df.sort_values("frame").reset_index(drop=True)
        
        # Trim to MAX_FRAMES
        frame_df = frame_df.head(MAX_FRAMES)
        
        mean_fc = float(frame_df["frame_complexity"].mean())
        std_fc = float(frame_df["frame_complexity"].std())
        
        # Store per-frame complexity indexed by frame number
        complexity_map = dict(zip(frame_df["frame"].astype(int), frame_df["frame_complexity"].astype(float)))
        
        stats[video_name] = {
            "path": str(pca_path),
            "mean_traffic_size": mean_fc,
            "std_traffic_size": std_fc,
            "num_frames": len(frame_df),
            "complexity_per_frame": complexity_map,
        }
        print(f"  {video_name}: {len(frame_df)} frames, "
              f"mean_complexity={mean_fc:.2f}, std_complexity={std_fc:.2f}")
    
    return stats


# ─── Step 2: Trim PCA CSV files to first MAX_FRAMES ─────────────────────────

def trim_pca_files():
    """Create trimmed versions of PCA files with only first MAX_FRAMES frames."""
    TRIMMED_DIR.mkdir(parents=True, exist_ok=True)
    trimmed_paths = {}
    
    for pca_path in PCA_FILES:
        video_name = pca_path.stem.replace("pca_sweep_summary_", "")
        df = pd.read_csv(pca_path)
        
        # Get sorted unique frame numbers
        unique_frames = sorted(df["frame"].unique())
        keep_frames = set(unique_frames[:MAX_FRAMES])
        
        # Filter to only those frames
        trimmed = df[df["frame"].isin(keep_frames)].copy()
        
        out_path = TRIMMED_DIR / pca_path.name
        trimmed.to_csv(out_path, index=False)
        trimmed_paths[video_name] = out_path
        
        print(f"  {video_name}: {len(keep_frames)} frames, "
              f"{len(trimmed)} total rows -> {out_path.name}")
    
    return trimmed_paths


# ─── Step 3: Assign videos to users ─────────────────────────────────────────

def assign_videos(num_users, video_names, seed=42):
    """Assign videos to users. Cycles through available videos."""
    rng = random.Random(seed)
    shuffled = list(video_names)
    rng.shuffle(shuffled)
    assignments = [shuffled[i % len(shuffled)] for i in range(num_users)]
    return assignments


def assign_fps(num_users, seed=42):
    """Assign a random frame rate to each user from FPS_OPTIONS."""
    rng = random.Random(seed)
    return [rng.choice(FPS_OPTIONS) for _ in range(num_users)]


# ─── Step 4: Run a single simulation ────────────────────────────────────────

def run_simulation(args):
    """Run one simulation for a given (num_users, repetition) pair.
    
    This function is called by the multiprocessing pool.
    """
    num_users, repetition, video_assignments, fps_assignments, trimmed_paths, run_dir, sim_time = args
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "simu5g",
        "omnetpp.ini",
        "-u", "Cmdenv",
        "-c", "XR-DL-RandomCL",
        f"--sim-time-limit={sim_time}s",
        f"--seed-set={repetition}",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
    ]
    
    # Add per-user overrides
    for i in range(num_users):
        video = video_assignments[i]
        fps = fps_assignments[i]
        pca_rel = os.path.relpath(trimmed_paths[video], SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")
        # String values must be quoted for OMNeT++ command-line parsing
        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")
    
    log_file = run_dir / "sim.log"
    
    try:
        with open(log_file, "w") as log_f:
            result = subprocess.run(
                cmd,
                cwd=str(SCRIPT_DIR),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=6000,  # 10 min timeout per sim
            )
        
        if result.returncode != 0:
            print(f"  [WARN] Sim n={num_users} r={repetition} returned code {result.returncode}")
            return None
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Sim n={num_users} r={repetition} timed out")
        return None
    except Exception as e:
        print(f"  [ERROR] Sim n={num_users} r={repetition}: {e}")
        return None
    
    return {
        "num_users": num_users,
        "repetition": repetition,
        "run_dir": str(run_dir),
        "video_assignments": video_assignments,
        "fps_assignments": fps_assignments,
    }


# ─── Step 5: Collect results from a simulation run ──────────────────────────

def collect_run_results(run_info, complexity_stats):
    """Collect per-frame data from a single simulation run.
    
    Produces rows matching the desired dataset format:
        frameNumber, user0_meantrafficsize, user0_stdtrafficsize, 
        user0_components, user0_effectiveError, user0_frameComplexity,
        user0_delay_ms, user0_cqi, ..., num_users
    """
    num_users = run_info["num_users"]
    run_dir = Path(run_info["run_dir"])
    video_assignments = run_info["video_assignments"]
    fps_assignments = run_info["fps_assignments"]
    
    # Read per-user result CSVs
    user_data = {}
    
    for i in range(num_users):
        csv_path = run_dir / f"user_{i}.csv"
        
        if not csv_path.exists():
            print(f"  [WARN] Missing {csv_path}")
            return []
        
        # Read per-frame results (now includes per-frame 'cqi' column)
        df = pd.read_csv(csv_path)
        user_data[i] = df
    
    # Build dataset rows (each row = one frame number across all users)
    # Only include frames where ALL users have data
    frame_numbers = sorted(user_data[0]["frameNumber"].unique())
    
    # Filter to only actual transmitted frames (not lost/padding rows)
    rows = []
    for frame_num in frame_numbers:
        if frame_num < 1 or frame_num > MAX_FRAMES:
            continue
        
        row = {"frameNumber": frame_num}
        skip_frame = False
        
        for i in range(num_users):
            video = video_assignments[i]
            stats = complexity_stats[video]
            prefix = f"user{i}_"
            
            # Get this user's data for this frame
            frame_df = user_data[i][user_data[i]["frameNumber"] == frame_num]
            
            if frame_df.empty:
                skip_frame = True
                break
            
            frame_row = frame_df.iloc[0]
            
            # Pre-computed complexity stats for this user's video
            row[prefix + "meantrafficsize"] = stats["mean_traffic_size"]
            row[prefix + "stdtrafficsize"] = stats["std_traffic_size"]
            
            # Per-frame data from simulation
            row[prefix + "components"] = int(frame_row["components"])
            row[prefix + "effectiveError"] = float(frame_row["effectiveError"])
            
            # Frame complexity from PCA file
            fc = stats["complexity_per_frame"].get(frame_num, 0.0)
            row[prefix + "frameComplexity"] = fc
            
            # Delay  
            row[prefix + "delay_ms"] = float(frame_row["delay_ms"])
            
            # Per-frame CQI (instantaneous DL CQI at frame reception time)
            row[prefix + "cqi"] = int(frame_row["cqi"]) if "cqi" in frame_row.index else 0
            
            # Frame rate assigned to this user
            row[prefix + "frame_rate"] = fps_assignments[i]
        
        if not skip_frame:
            row["num_users"] = num_users
            rows.append(row)
    
    return rows


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate XR streaming dataset")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only prepare files, don't run simulations")
    parser.add_argument("--repetitions", type=int, default=3,
                        help="Number of repetitions per user count (default: 3)")
    parser.add_argument("--sim-time", type=int, default=SIM_TIME_LIMIT,
                        help=f"Simulation time limit in seconds (default: {SIM_TIME_LIMIT})")
    parser.add_argument("--seed", type=int, default=42,
                        help="Base random seed for video assignments")
    args = parser.parse_args()
    
    sim_time = args.sim_time
    
    print(f"=" * 60)
    print(f"XR Dataset Generation")
    print(f"  Videos: {len(PCA_FILES)}")
    print(f"  Max frames: {MAX_FRAMES}")
    print(f"  User sweep: {NUM_USERS_SWEEP}")
    print(f"  Repetitions: {args.repetitions}")
    print(f"  Sim time: {sim_time}s")
    print(f"  Workers: {MAX_WORKERS}")
    print(f"=" * 60)
    
    # Step 1: Compute complexity stats
    print("\n[1/5] Computing frame complexity statistics...")
    complexity_stats = compute_complexity_stats()
    
    # Save stats to JSON for reference
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    stats_file = DATASET_DIR / "complexity_stats.json"
    stats_for_json = {
        k: {kk: vv for kk, vv in v.items() if kk != "complexity_per_frame"}
        for k, v in complexity_stats.items()
    }
    with open(stats_file, "w") as f:
        json.dump(stats_for_json, f, indent=2)
    print(f"  Saved to {stats_file}")
    
    # Step 2: Trim PCA files
    print(f"\n[2/5] Trimming PCA files to first {MAX_FRAMES} frames...")
    trimmed_paths = trim_pca_files()
    
    if args.dry_run:
        print("\n[DRY RUN] Stopping before simulations.")
        print("Trimmed files at:", TRIMMED_DIR)
        print("Complexity stats at:", stats_file)
        return
    
    # Step 3: Prepare simulation jobs
    print("\n[3/5] Preparing simulation jobs...")
    video_names = list(complexity_stats.keys())
    
    jobs = []
    for num_users in NUM_USERS_SWEEP:
        for rep in range(args.repetitions):
            run_seed = args.seed + num_users * 100 + rep
            video_assignments = assign_videos(num_users, video_names, seed=run_seed)
            fps_assignments = assign_fps(num_users, seed=run_seed + 1000)
            
            run_dir = RESULTS_DIR / f"dataset_n{num_users}_r{rep}"

            jobs.append((
                num_users, rep, video_assignments, fps_assignments,
                {v: trimmed_paths[v] for v in video_names},
                str(run_dir),
                sim_time,
            ))
    
    total_jobs = len(jobs)
    print(f"  Total simulation jobs: {total_jobs}")
    print(f"  Using {MAX_WORKERS} parallel workers")
    
    # Step 4: Run simulations in parallel
    print(f"\n[4/5] Running {total_jobs} simulations...")
    
    completed_runs = []
    with Pool(processes=MAX_WORKERS) as pool:
        for i, result in enumerate(pool.imap_unordered(run_simulation, jobs)):
            pct = (i + 1) / total_jobs * 100
            if result is not None:
                completed_runs.append(result)
                print(f"  [{i+1}/{total_jobs}] ({pct:.0f}%) "
                      f"n={result['num_users']} r={result['repetition']} ✓")
            else:
                print(f"  [{i+1}/{total_jobs}] ({pct:.0f}%) FAILED")
    
    print(f"\n  Completed: {len(completed_runs)}/{total_jobs}")
    
    # Step 5: Collect and assemble dataset
    print("\n[5/5] Collecting results and assembling dataset...")
    
    all_rows = []
    for run_info in completed_runs:
        rows = collect_run_results(run_info, complexity_stats)
        all_rows.extend(rows)
        print(f"  n={run_info['num_users']} r={run_info['repetition']}: "
              f"{len(rows)} rows")
    
    if not all_rows:
        print("[ERROR] No data collected!")
        return
    
    # Build DataFrame
    dataset = pd.DataFrame(all_rows)
    
    # Reorder columns: frameNumber, then user columns in order, then num_users
    user_cols = []
    max_users = max(r["num_users"] for r in completed_runs)
    for i in range(max_users):
        for suffix in ["meantrafficsize", "stdtrafficsize", "components",
                        "effectiveError", "frameComplexity", "delay_ms", "cqi",
                        "frame_rate"]:
            col = f"user{i}_{suffix}"
            if col in dataset.columns:
                user_cols.append(col)
    
    col_order = ["frameNumber"] + user_cols + ["num_users"]
    # Only keep columns that exist
    col_order = [c for c in col_order if c in dataset.columns]
    dataset = dataset[col_order]
    
    # Save
    out_path = DATASET_DIR / "random_cl_dataset.csv"
    dataset.to_csv(out_path, index=False)
    
    print(f"\n{'=' * 60}")
    print(f"Dataset generated: {out_path}")
    print(f"  Total rows: {len(dataset)}")
    print(f"  Columns: {len(dataset.columns)}")
    print(f"  Users sweep: {sorted(dataset['num_users'].unique())}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
