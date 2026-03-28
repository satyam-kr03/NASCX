#!/usr/bin/env python3
"""
Comparison Script: Model-Based Adaptive vs Static Compression Levels.
PARALLEL VERSION — exploits multiple CPU cores via ProcessPoolExecutor.

Simplified pipeline (inline model queries during simulation):
  1. Run a "model" simulation using selectionMode="model" — the source
     reads live CQI from the Binder and queries the model API each frame.
  2. Run static simulations for every compression level (25,50,...,400).
     All static sims (and the model sim) are launched concurrently.
  3. Collect effective-error results from all runs and write a comparison CSV.

Usage:
    python run_comparison_parallel.py [--num-users N] [--sim-time S] [--seed SEED]
                                      [--server-url URL] [--mode pca|ae]
                                      [--dry-run] [--max-workers W]

The --mode flag selects which traffic_files_(pca|ae) directory to use and
writes results to comparison_results_(pca|ae).
"""

import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Configuration ─────────────────────────────────────────────────────────────

import argparse

SCRIPT_DIR = Path(__file__).parent.resolve()
# mode will be parsed later; defaults to 'pca'
MODE = 'pca'
TRAFFIC_DIR = None  # will be set after CLI parsing
TRIMMED_DIR = None
RESULTS_DIR = None

if MODE == "pca":
    COMP_LEVELS = list(range(5, 81, 5))       # 25, 50, 75, ... 400
else:
    COMP_LEVELS = list(range(4, 373, 16))       # 4, 20, 36, ... 372 (AE levels)
MAX_FRAMES = 1000
# FPS = 60
# DEADLINE_MS = 5.0
# FPS_OPTIONS = [45, 60, 72, 90, 120]            # Per-user frame rate choices
FPS_OPTIONS = [45, 60, 72]             # Per-user frame rate choices

# file prefix for sweep summaries (pca or ae)
FILE_PREFIX = None

# PCA files (trimmed to 2000 frames) -- computed later
PCA_FILES = []

MODEL_SERVER_URL = "http://localhost:8000"

# Default parallelism — tune with --max-workers; None = os.cpu_count()
DEFAULT_MAX_WORKERS = 31


# ── Helpers ───────────────────────────────────────────────────────────────────

def video_name_from_path(p: Path) -> str:
    return p.stem.replace(FILE_PREFIX, "")


def assign_videos(num_users: int, seed: int = 42) -> list[str]:
    """Assign videos to users by cycling through available videos."""
    names = [video_name_from_path(p) for p in PCA_FILES]
    rng = random.Random(seed)
    rng.shuffle(names)
    return [names[i % len(names)] for i in range(num_users)]


def assign_fps(num_users: int, seed: int = 42) -> list[int]:
    """Assign a random frame rate to each user from FPS_OPTIONS."""
    rng = random.Random(seed + 10)
    return [rng.choice(FPS_OPTIONS) for _ in range(num_users)]


def pca_path_for_video(video: str) -> Path:
    return TRIMMED_DIR / f"{FILE_PREFIX}{video}.csv"


def build_sim_cmd(
    config: str,
    num_users: int,
    sim_time: int,
    seed: int,
    video_assignments: list[str],
    run_dir: Path,
    *,
    selection_mode: str = "fixed",
    compression_level: int = 0,
    prescribed_files: dict[int, Path] | None = None,
    model_server_url: str = "",
    fps_assignments: list[int] | None = None,
) -> list[str]:
    """Build the OMNeT++ command line for one simulation run."""
    cmd = [
        "simu5g",
        "omnetpp.ini",
        "-u", "Cmdenv",
        "-c", config,
        f"--sim-time-limit={sim_time}s",
        f"--seed-set={seed}",
        f"--result-dir={run_dir}",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
    ]

    for i in range(num_users):
        video = video_assignments[i]
        pca_rel = os.path.relpath(pca_path_for_video(video), SCRIPT_DIR.parent)
        result_file = str(run_dir / f"user_{i}.csv")

        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].selectionMode="{selection_mode}"')
        cmd.append(f"--*.server.app[{i}].compressionLevel={compression_level}")

        # Model mode: pass server URL and user count
        if selection_mode == "model":
            cmd.append(f'--*.server.app[{i}].modelServerUrl="{model_server_url}"')
            cmd.append(f"--*.server.app[{i}].modelNumUsers={num_users}")

        # Set per-user FPS if provided
        if fps_assignments:
            cmd.append(f"--*.server.app[{i}].fps={fps_assignments[i]}")

        if selection_mode == "prescribed" and prescribed_files and i in prescribed_files:
            cmd.append(f'--*.server.app[{i}].prescribedFile="{prescribed_files[i]}"')

        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")

    # print(cmd)
    return cmd


def read_user_results(run_dir: Path, num_users: int) -> dict[int, pd.DataFrame]:
    """Read per-user result CSVs from a simulation run."""
    data = {}
    for i in range(num_users):
        p = run_dir / f"user_{i}.csv"
        if p.exists():
            data[i] = pd.read_csv(p)
        else:
            print(f"    [WARN] Missing {p}")
    return data


def compute_mean_effective_error(df: pd.DataFrame) -> float:
    """Compute mean effective error from a user result DataFrame."""
    if df.empty or "effectiveError" not in df.columns:
        return float("nan")
    return float(df["effectiveError"].mean())


# ── Worker function (must be module-level for pickling) ──────────────────────

def _run_one_sim(
    label: str,
    cmd: list[str],
    run_dir: Path,
    num_users: int,
    timeout: int,
) -> tuple[str, dict[int, pd.DataFrame] | None]:
    """
    Worker executed in a subprocess pool.
    Runs one simulation and returns (label, {user_id: DataFrame} | None).
    """
    run_dir = Path(run_dir)  # ensure Path after pickling
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    log_file = run_dir / "sim.log"
    t0 = time.time()
    try:
        with open(log_file, "w") as lf:
            result = subprocess.run(
                cmd,
                cwd=str(SCRIPT_DIR.parent),
                stdout=lf,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        elapsed = time.time() - t0
        if result.returncode != 0:
            print(f"  [{label}] FAILED (code {result.returncode}, {elapsed:.0f}s)",
                  flush=True)
            return label, None
        print(f"  [{label}] OK ({elapsed:.0f}s)", flush=True)
        return label, read_user_results(run_dir, num_users)
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT ({timeout}s)", flush=True)
        return label, None
    except Exception as e:
        print(f"  [{label}] ERROR: {e}", flush=True)
        return label, None


# ── Parallel simulation runner ────────────────────────────────────────────────

def run_all_sims_parallel(
    num_users: int,
    sim_time: int,
    seed: int,
    video_assignments: list[str],
    fps_assignments: list[int],
    server_url: str,
    levels: list[int],
    max_workers: int | None,
    timeout: int,
) -> tuple[dict[int, pd.DataFrame] | None, dict[int, dict[int, pd.DataFrame]]]:
    """
    Build all simulation jobs (model + every static level) and run them
    concurrently across `max_workers` processes.

    Returns:
        model_data   – {user_id: DataFrame} or None if model sim failed
        static_data  – {comp_level: {user_id: DataFrame}}
    """
    # Collect jobs: list of (label, cmd, run_dir)
    jobs: list[tuple[str, list[str], Path]] = []

    # Model job
    model_run_dir = RESULTS_DIR / "model"
    model_cmd = build_sim_cmd(
        config="XR-DL-RandomCL",
        num_users=num_users,
        sim_time=sim_time,
        seed=seed,
        video_assignments=video_assignments,
        run_dir=model_run_dir,
        selection_mode="model",
        compression_level=0,
        model_server_url=server_url,
        fps_assignments=fps_assignments,
    )
    jobs.append(("Model (inline)", model_cmd, model_run_dir))

    # Static jobs
    for cl in levels:
        run_dir = RESULTS_DIR / f"static_{cl}"
        cmd = build_sim_cmd(
            config="XR-DL-RandomCL",
            num_users=num_users,
            sim_time=sim_time,
            seed=seed,
            video_assignments=video_assignments,
            run_dir=run_dir,
            selection_mode="fixed",
            compression_level=cl,
            fps_assignments=fps_assignments,
        )
        jobs.append((f"Static CL={cl}", cmd, run_dir))

    total = len(jobs)
    effective_workers = max_workers or os.cpu_count() or 1
    print(f"  Dispatching {total} simulations across "
          f"{effective_workers} workers ...", flush=True)

    # Submit all jobs to the pool
    results_map: dict[str, dict[int, pd.DataFrame] | None] = {}
    t_start = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_one_sim, label, cmd, run_dir, num_users, timeout): label
            for label, cmd, run_dir in jobs
        }
        completed = 0
        for fut in as_completed(futures):
            label, data = fut.result()
            results_map[label] = data
            completed += 1
            elapsed = time.time() - t_start
            print(f"  Progress: {completed}/{total} done  "
                  f"({elapsed:.0f}s elapsed)", flush=True)

    # Unpack
    model_data = results_map.get("Model (inline)")
    static_data: dict[int, dict[int, pd.DataFrame]] = {}
    for cl in levels:
        key = f"Static CL={cl}"
        if results_map.get(key) is not None:
            static_data[cl] = results_map[key]

    return model_data, static_data


# ── Step 3: Assemble comparison results ──────────────────────────────────────

def assemble_comparison(
    num_users: int,
    video_assignments: list[str],
    model_data: dict[int, pd.DataFrame] | None,
    static_data: dict[int, dict[int, pd.DataFrame]],
    out_path: Path,
) -> pd.DataFrame:
    """
    Build a comparison CSV:
        user, video, strategy, comp_level, mean_effective_error,
        on_time_ratio, mean_delay_ms
    """
    rows = []

    # Model results
    if model_data:
        for i in range(num_users):
            if i in model_data:
                df = model_data[i]
                mean_err = compute_mean_effective_error(df)
                on_time = float(df["receivedOnTime"].mean()) if "receivedOnTime" in df.columns else float("nan")
                mean_delay = float(df["delay_ms"].mean()) if "delay_ms" in df.columns else float("nan")
                rows.append({
                    "user": i,
                    "video": video_assignments[i],
                    "strategy": "model",
                    "comp_level": "adaptive",
                    "mean_effective_error": mean_err,
                    "on_time_ratio": on_time,
                    "mean_delay_ms": mean_delay,
                })

    # Static results
    for cl, user_dfs in sorted(static_data.items()):
        for i in range(num_users):
            if i in user_dfs:
                df = user_dfs[i]
                mean_err = compute_mean_effective_error(df)
                on_time = float(df["receivedOnTime"].mean()) if "receivedOnTime" in df.columns else float("nan")
                mean_delay = float(df["delay_ms"].mean()) if "delay_ms" in df.columns else float("nan")
                rows.append({
                    "user": i,
                    "video": video_assignments[i],
                    "strategy": "static",
                    "comp_level": cl,
                    "mean_effective_error": mean_err,
                    "on_time_ratio": on_time,
                    "mean_delay_ms": mean_delay,
                })

    result_df = pd.DataFrame(rows)
    result_df.to_csv(out_path, index=False)
    return result_df


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare model-adaptive vs static XR compression (parallel)"
    )
    parser.add_argument("--mode", choices=["pca", "ae"], default="pca",
                        help="Choose traffic file mode (pca or ae)")
    parser.add_argument("--num-users", type=int, default=5,
                        help="Number of UEs (2-10, default: 5)")
    parser.add_argument("--sim-time", type=int, default=35,
                        help="Simulation time in seconds (default: 35)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--server-url", default=MODEL_SERVER_URL,
                        help=f"Model server URL (default: {MODEL_SERVER_URL})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without running simulations")
    parser.add_argument("--timeout", type=int, default=6000,
                        help="Per-simulation timeout in seconds (default: 6000)")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS,
                        help="Max parallel worker processes (default: cpu_count)")
    args = parser.parse_args()

    num_users = args.num_users
    sim_time = args.sim_time
    seed = args.seed
    server_url = args.server_url
    max_workers = args.max_workers
    global MODE, TRAFFIC_DIR, TRIMMED_DIR, RESULTS_DIR, FILE_PREFIX, PCA_FILES
    MODE = args.mode
    # Point directly to the older XR dataset path that holds all the generated and trimmed files
    TRAFFIC_DIR = SCRIPT_DIR.parent / ("compression/traffic_files/pca" if MODE == "pca" else "compression/traffic_files/ae")
    TRIMMED_DIR = TRAFFIC_DIR 
    FILE_PREFIX = "pca_sweep_summary_" if MODE == "pca" else "ae_sweep_summary_"
    PCA_FILES = sorted(TRIMMED_DIR.glob(FILE_PREFIX + "*.csv"))
    
    if not PCA_FILES:
        print(f"  [ERROR] No traffic files found in {TRIMMED_DIR}!")
        sys.exit(1)
        
    RESULTS_DIR = SCRIPT_DIR / f"comparison_results_{MODE}"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    effective_workers = max_workers or os.cpu_count() or 1
    total_sims = 1 + len(COMP_LEVELS)

    print("=" * 65)
    print(f"  Model vs Static Compression Comparison  [PARALLEL] (mode={MODE})")
    print("  (Inline model queries — no probe simulation)")
    print("=" * 65)
    print(f"  Users:           {num_users}")
    print(f"  Sim time:        {sim_time}s")
    print(f"  Seed:            {seed}")
    print(f"  Static levels:   {COMP_LEVELS[0]}-{COMP_LEVELS[-1]} "
          f"(step 25, {len(COMP_LEVELS)} sims)")
    print(f"  Model server:    {server_url}")
    print(f"  Output dir:      {RESULTS_DIR}")
    print(f"  Workers:         {effective_workers}  "
          f"(running {total_sims} sims in parallel)")

    # Assign videos and frame rates
    video_assignments = assign_videos(num_users, seed)
    fps_assignments = assign_fps(num_users, seed)
    print(f"\n  Video & FPS assignments:")
    for i, v in enumerate(video_assignments):
        print(f"    User {i}: {v}  ({fps_assignments[i]} fps)")

    if args.dry_run:
        print(f"\n[DRY RUN] Would run {total_sims} simulations "
              f"across {effective_workers} workers.")
        print(f"  1x model (inline), {len(COMP_LEVELS)}x static")
        model_run_dir = RESULTS_DIR / "model"
        print(build_sim_cmd(
            config="XR-DL-RandomCL",
            num_users=num_users,
            sim_time=sim_time,
            seed=seed,
            video_assignments=video_assignments,
            run_dir=model_run_dir,
            selection_mode="model",
            compression_level=0,
            model_server_url=server_url,
            fps_assignments=fps_assignments,
        ))
        return

    # Check model server health
    print(f"\n[0/3] Checking model server ...")
    try:
        r = requests.get(f"{server_url}/health", timeout=5)
        r.raise_for_status()
        health = r.json()
        print(f"  Server OK: device={health['device']}, "
              f"models={health['loaded_models']}")
        if num_users not in health["loaded_models"]:
            print(f"  [WARN] No model for {num_users} users! "
                  f"Available: {health['loaded_models']}")
            return
    except Exception as e:
        print(f"  [ERROR] Cannot reach model server: {e}")
        print("  Start the server with: python model_server.py")
        return

    # ── Steps 1 & 2: Run all sims concurrently ────────────────────────────
    print(f"\n[1-2/3] Running model + {len(COMP_LEVELS)} static simulations "
          f"in parallel ...")
    t0 = time.time()
    model_data, static_data = run_all_sims_parallel(
        num_users=num_users,
        sim_time=sim_time,
        seed=seed,
        video_assignments=video_assignments,
        fps_assignments=fps_assignments,
        server_url=server_url,
        levels=COMP_LEVELS,
        max_workers=max_workers,
        timeout=args.timeout,
    )
    wall_time = time.time() - t0
    print(f"\n  All simulations finished in {wall_time:.1f}s wall-clock time.")

    if model_data is None:
        print("[WARN] Model simulation failed.")
    print(f"  Static sims completed: {len(static_data)}/{len(COMP_LEVELS)}")

    # ── Step 3: Assemble results ──────────────────────────────────────────
    print(f"\n[3/3] Assembling comparison results ...")
    out_csv = RESULTS_DIR / "comparison.csv"
    result_df = assemble_comparison(
        num_users, video_assignments, model_data, static_data, out_csv
    )
    print(f"  Written to: {out_csv}")
    print(f"  Total rows: {len(result_df)}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  RESULTS SUMMARY")
    print("=" * 65)

    if result_df.empty:
        print("\n  [ERROR] No successful simulations! comparison.csv is empty.")
        return

    if model_data:
        model_rows = result_df[result_df["strategy"] == "model"]
        model_avg = model_rows["mean_effective_error"].mean()
        print(f"\n  Model (adaptive):  avg effective error = {model_avg:.6f}")

    static_rows = result_df[result_df["strategy"] == "static"]
    print(f"\n  Static levels (avg effective error across all users):")
    for cl in sorted(static_data.keys()):
        cl_rows = static_rows[static_rows["comp_level"] == cl]
        avg_err = cl_rows["mean_effective_error"].mean()
        print(f"    CL={cl:>3d}:  {avg_err:.6f}")

    # Find best static
    static_summary = (
        static_rows.groupby("comp_level")["mean_effective_error"]
        .mean()
        .reset_index()
    )
    best_static = static_summary.loc[
        static_summary["mean_effective_error"].idxmin()
    ]
    print(f"\n  Best static: CL={best_static['comp_level']}, "
          f"error={best_static['mean_effective_error']:.6f}")

    if model_data:
        improvement = (
            (best_static["mean_effective_error"] - model_avg)
            / best_static["mean_effective_error"]
            * 100
        )
        print(f"  Model improvement over best static: {improvement:+.2f}%")

    print(f"\n  Wall-clock time: {wall_time:.1f}s "
          f"(~{effective_workers}x speedup over serial)")
    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()