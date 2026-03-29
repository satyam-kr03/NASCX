#!/usr/bin/env python3
"""
Dataset Generation Script for XR Streaming Simulation.

Generates an ML training dataset by running simu5g simulations with random
per-frame compression levels. Each user is assigned a video stream (PCA file),
and the simulation randomly selects compression levels per frame.

Usage:
    python generate_dataset.py [--dry-run] [--repetitions N] [--sim-time S] [--mode pca|ae]

Output:
    datasets/dataset.csv
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
# These will be set after parsing CLI arguments in main()
TRAFFIC_DIR = None          # will point to traffic_files_pca or traffic_files_ae
RESULTS_DIR = SCRIPT_DIR / "results"
DATASET_DIR = None          # will point to datasets_pca or datasets_ae

# Filename prefix used for lookup (pca or ae)
FILE_PREFIX = None

# Sweep summary files (one per video) -- computed later
PCA_FILES = []

MAX_FRAMES = 1000      # Only use first 2000 frames per video
FPS = 60               # Frames per second (default)
FPS_OPTIONS = [45, 60, 72, 90, 120]  # Per-user frame rate choices
SIM_TIME_LIMIT = 35    # seconds (>= 2000/60 ≈ 33.33s, with margin)
DEADLINE_MS = 2.5     # Frame deadline in ms
NUM_USERS_SWEEP = list(range(2, 11))  # 2..10 users

# Parallelism
MAX_WORKERS = min(cpu_count(), 32)


# ─── Step 1: Assign videos to users ─────────────────────────────────────────

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


# ─── Step 2: Run a single simulation ────────────────────────────────────────

def run_simulation(args):
    """Run one simulation for a given (num_users, repetition) pair.
    
    This function is called by the multiprocessing pool.
    """
    num_users, repetition, video_assignments, fps_assignments, traffic_paths, run_dir, sim_time = args
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # --- Generate Prescribed CSVs for Correlated Exploration ---
    import random
    rng = random.Random(repetition + num_users * 1000)
    
    # Determine type of run
    # Let rep 0-15 be static runs (CL 5, 10, ..., 80)
    # The rest are correlated random
    is_static = False
    static_level = 5
    if repetition < 16:
        is_static = True
        static_level = 5 + repetition * 5

    MAX_COMPONENTS = 80
    MIN_COMPONENTS = 5
    STEP = 5
    
    user_schedules = {i: [] for i in range(num_users)}
    for frame_id in range(1, MAX_FRAMES + 200):
        if is_static:
            for i in range(num_users):
                user_schedules[i].append((frame_id, static_level))
        else:
            # Correlated random: pick a base level for the whole network
            # Then add noise per user
            base_cl = rng.choice(range(MIN_COMPONENTS, MAX_COMPONENTS + 1, STEP))
            for i in range(num_users):
                noise = rng.choice([-10, -5, 0, 5, 10])
                user_cl = base_cl + noise
                # Bound to valid range and align to nearest step
                user_cl = max(MIN_COMPONENTS, min(MAX_COMPONENTS, user_cl))
                user_cl = round(user_cl / STEP) * STEP
                user_schedules[i].append((frame_id, int(user_cl)))
                
    for i in range(num_users):
        presc_file = run_dir / f"prescribed_{i}.csv"
        with open(presc_file, "w") as pf:
            pf.write("frame,components\n")
            for frame_id, cl in user_schedules[i]:
                pf.write(f"{frame_id},{cl}\n")
    # ---------------------------------------------------------
    
    cmd = [
        "simu5g",
        "../omnetpp.ini",
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
        pca_rel = os.path.relpath(traffic_paths[video], SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")
        presc_rel = os.path.relpath(run_dir / f"prescribed_{i}.csv", SCRIPT_DIR)
        
        # String values must be quoted for OMNeT++ command-line parsing
        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")
        
        # Override to use prescribed schedule
        cmd.append(f'--*.server.app[{i}].selectionMode="prescribed"')
        cmd.append(f'--*.server.app[{i}].prescribedFile="{presc_rel}"')
    
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


# ─── Step 3: Collect results from a simulation run ──────────────────────────

def collect_run_results(run_info):
    """Collect per-frame data from a single simulation run.
    
    Produces rows matching the desired dataset format:
        frameNumber, user0_components, user0_effectiveError,
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
            prefix = f"user{i}_"
            
            # Get this user's data for this frame
            frame_df = user_data[i][user_data[i]["frameNumber"] == frame_num]
            
            if frame_df.empty:
                skip_frame = True
                break
            
            frame_row = frame_df.iloc[0]
            
            # Per-frame data from simulation
            row[prefix + "components"] = int(frame_row["components"])
            row[prefix + "effectiveError"] = float(frame_row["effectiveError"])
            
            # Delay  
            row[prefix + "delay_ms"] = float(frame_row["delay_ms"])
            
            # Per-frame CQI (instantaneous DL CQI at frame reception time)
            row[prefix + "cqi"] = int(frame_row["cqi"]) if "cqi" in frame_row.index else 0
            
            # New gNB metrics (per user)
            row[prefix + "buffer_bytes"] = int(frame_row["buffer_bytes"]) if "buffer_bytes" in frame_row.index else 0
            row[prefix + "mcs_index"] = int(frame_row["mcs_index"]) if "mcs_index" in frame_row.index else 0
            
            # Global gNB metrics (same across all users, just read from user 0 to avoid duplication)
            if i == 0:
                row["dl_utilization"] = float(frame_row["dl_utilization"]) if "dl_utilization" in frame_row.index else 0.0
                row["n_active_ues"] = int(frame_row["n_active_ues"]) if "n_active_ues" in frame_row.index else 0
            
            # Frame rate assigned to this user
            row[prefix + "frame_rate"] = fps_assignments[i]
        
        if not skip_frame:
            row["num_users"]   = num_users
            row["repetition"]  = run_info["repetition"]   # ← ADD THIS
            row[f"user{i}_video"] = video_assignments[i]
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
    parser.add_argument("--mode", choices=["pca", "ae"], default="pca",
                        help="Which traffic directory to use (pca or ae)")
    args = parser.parse_args()
    
    # determine directories based on mode
    global TRAFFIC_DIR, PCA_FILES, FILE_PREFIX, DATASET_DIR
    TRAFFIC_DIR = SCRIPT_DIR.parent / ("compression/traffic_files/pca" if args.mode == "pca" else "compression/traffic_files/ae")

    FILE_PREFIX = "pca_sweep_summary_" if args.mode == "pca" else "ae_sweep_summary_"
    PCA_FILES = sorted(TRAFFIC_DIR.glob(FILE_PREFIX + "*.csv"))
    DATASET_DIR = SCRIPT_DIR.parent / ("datasets/pca" if args.mode == "pca" else "datasets/ae")
    
    sim_time = args.sim_time
    
    print(f"=" * 60)
    print(f"XR Dataset Generation (mode={args.mode})")
    print(f"  Videos: {len(PCA_FILES)}")
    print(f"  Max frames: {MAX_FRAMES}")
    print(f"  User sweep: {NUM_USERS_SWEEP}")
    print(f"  Repetitions: {args.repetitions}")
    print(f"  Sim time: {sim_time}s")
    print(f"  Workers: {MAX_WORKERS}")
    print(f"=" * 60)
    
    traffic_paths = {}
    for pca_path in PCA_FILES:
        video_name = pca_path.stem.replace(FILE_PREFIX, "")
        traffic_paths[video_name] = pca_path

    if args.dry_run:
        print("\n[DRY RUN] Stopping before simulations.")
        print("Traffic files at:", TRAFFIC_DIR)
        return
    
    # Step 1: Prepare simulation jobs
    print("\n[1/3] Preparing simulation jobs...")
    video_names = list(traffic_paths.keys())
    
    jobs = []
    for num_users in NUM_USERS_SWEEP:
        for rep in range(args.repetitions):
            run_seed = args.seed + num_users * 100 + rep
            video_assignments = assign_videos(num_users, video_names, seed=run_seed)
            fps_assignments = assign_fps(num_users, seed=run_seed + 1000)
            
            run_dir = RESULTS_DIR / f"dataset_n{num_users}_r{rep}"

            jobs.append((
                num_users, rep, video_assignments, fps_assignments,
                {v: traffic_paths[v] for v in video_names},
                str(run_dir),
                sim_time,
            ))
    
    total_jobs = len(jobs)
    print(f"  Total simulation jobs: {total_jobs}")
    print(f"  Using {MAX_WORKERS} parallel workers")
    
    # Step 2: Run simulations in parallel
    print(f"\n[2/3] Running {total_jobs} simulations...")
    
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
    
    # Step 3: Collect and assemble dataset
    print("\n[3/3] Collecting results and assembling dataset...")
    
    all_rows = []
    for run_info in completed_runs:
        rows = collect_run_results(run_info)
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
        for suffix in ["components",
                        "effectiveError", "delay_ms", "cqi", "buffer_bytes", "mcs_index",
                        "frame_rate"]:
            col = f"user{i}_{suffix}"
            if col in dataset.columns:
                user_cols.append(col)
    
    col_order = ["frameNumber", "repetition", "dl_utilization", "n_active_ues"] + user_cols + ["num_users"]
    # Only keep columns that exist
    col_order = [c for c in col_order if c in dataset.columns]
    dataset = dataset[col_order]
    
    # Save
    out_path = DATASET_DIR / "dataset.csv"
    dataset.to_csv(out_path, index=False)
    
    print(f"\n{'=' * 60}")
    print(f"Dataset generated: {out_path}")
    print(f"  Total rows: {len(dataset)}")
    print(f"  Columns: {len(dataset.columns)}")
    print(f"  Users sweep: {sorted(dataset['num_users'].unique())}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
