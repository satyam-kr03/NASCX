#!/usr/bin/env python3
"""
Dataset Generation Script for XR Streaming Simulation.

Generates an ML training dataset by running Simu5G simulations with
prescribed per-frame compression levels. Each user is assigned a video
stream (PCA sweep summary), and the simulation follows a prescribed
schedule of compression levels per frame.

Usage:
    python generate_dataset.py [--dry-run] [--repetitions N] [--sim-time S]

Output:
    ../datasets/pca/dataset.csv
"""

import logging
import os
import random
import argparse
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import Optional

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = SCRIPT_DIR / "results"

MAX_FRAMES = 1000       # Number of frames per video to simulate
FPS_OPTIONS = [45, 60, 72, 90, 120]  # Per-user frame rate choices
SIM_TIME_LIMIT = 35     # Default simulation time limit (seconds)
NUM_USERS_SWEEP = list(range(2, 11))  # Sweep user counts 2..10

MAX_WORKERS = min(cpu_count(), 32)

# All 16 compression levels (5, 10, 15, ..., 80)
CL_LEVELS = list(range(5, 81, 5))
NUM_CL_LEVELS = len(CL_LEVELS)  # 16

FILE_PREFIX = "pca_sweep_summary_"


# ─── Data classes ────────────────────────────────────────────────────────────

@dataclass
class SimConfig:
    """Configuration for a single simulation run."""
    num_users: int
    repetition: int
    video_assignments: list
    fps_assignments: list
    traffic_paths: dict
    run_dir: str
    sim_time: int
    traffic_dir: Path


@dataclass
class RunResult:
    """Result metadata from a completed simulation."""
    num_users: int
    repetition: int
    run_dir: str
    video_assignments: list
    fps_assignments: list


# ─── Error table loading ────────────────────────────────────────────────────

def load_error_tables(traffic_paths: dict) -> dict:
    """Load per-video error tables: {video: {frame: [mse_at_5, ..., mse_at_80]}}.

    For each frame, builds a fixed-length 16-element vector of MSE values,
    one per compression level (5, 10, ..., 80).
    """
    error_tables = {}
    for video_name, summary_path in traffic_paths.items():
        if not Path(summary_path).exists():
            raise FileNotFoundError(
                f"Missing summary file for video '{video_name}': {summary_path}"
            )

        df = pd.read_csv(summary_path)

        required_cols = {"frame", "components", "mse"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(
                f"Summary file {summary_path} is missing columns: {sorted(missing)}"
            )

        # Pivot: for each frame, collect MSE at each CL
        table = {}
        for frame_num, grp in df.groupby("frame"):
            frame_num = int(frame_num)
            mse_by_cl = {
                int(row["components"]): float(row["mse"])
                for _, row in grp.iterrows()
            }
            mse_vector = [mse_by_cl.get(cl, 0.0) for cl in CL_LEVELS]
            table[frame_num] = mse_vector

        error_tables[video_name] = table

    return error_tables


def lookup_errors(error_tables: dict, video_name: str, frame_number: int) -> list:
    """Lookup per-frame MSE vector with deterministic frame-base fallback.

    Returns a 16-element list [mse_at_5, mse_at_10, ..., mse_at_80].
    Tries exact frame first, then (frame-1) for 0-based indexing.
    """
    if video_name not in error_tables:
        raise KeyError(f"No error table loaded for video '{video_name}'")

    table = error_tables[video_name]
    exact_key = int(frame_number)
    shifted_key = int(frame_number) - 1

    if exact_key in table:
        return table[exact_key]
    if shifted_key in table:
        return table[shifted_key]

    raise KeyError(
        f"Missing error lookup for video='{video_name}', frame={frame_number}"
    )


# ─── User assignment helpers ────────────────────────────────────────────────

def assign_videos(num_users: int, video_names: list, seed: int = 42) -> list:
    """Assign videos to users by cycling through available videos."""
    rng = random.Random(seed)
    shuffled = list(video_names)
    rng.shuffle(shuffled)
    return [shuffled[i % len(shuffled)] for i in range(num_users)]


def assign_fps(num_users: int, seed: int = 42) -> list:
    """Assign a random frame rate to each user from FPS_OPTIONS."""
    rng = random.Random(seed)
    return [rng.choice(FPS_OPTIONS) for _ in range(num_users)]


# ─── Prescribed schedule generation ────────────────────────────────────────

def build_prescribed_schedule(
    num_users: int,
    repetition: int,
    num_frames: int = MAX_FRAMES + 200,
) -> dict:
    """Build per-user compression level schedules for a simulation run.

    For repetitions 0-15: static schedules (CL 5, 10, ..., 80).
    For repetitions >= 16: correlated random schedules with per-user noise.

    Returns:
        dict mapping user_index -> list of (frame_id, compression_level) tuples
    """
    rng = random.Random(repetition + num_users * 1000)

    is_static = repetition < 16
    static_level = 5 + repetition * 5 if is_static else 5

    MIN_COMPONENTS, MAX_COMPONENTS, STEP = 5, 80, 5

    user_schedules = {i: [] for i in range(num_users)}
    for frame_id in range(1, num_frames + 1):
        if is_static:
            for i in range(num_users):
                user_schedules[i].append((frame_id, static_level))
        else:
            # Correlated random: pick a base level for the whole network,
            # then add bounded noise per user
            base_cl = rng.choice(range(MIN_COMPONENTS, MAX_COMPONENTS + 1, STEP))
            for i in range(num_users):
                noise = rng.choice([-10, -5, 0, 5, 10])
                user_cl = max(MIN_COMPONENTS, min(MAX_COMPONENTS, base_cl + noise))
                user_cl = round(user_cl / STEP) * STEP
                user_schedules[i].append((frame_id, int(user_cl)))

    return user_schedules


# ─── Single simulation runner ───────────────────────────────────────────────

def run_simulation(args: tuple) -> Optional[dict]:
    """Run one simulation for a given (num_users, repetition) pair.

    This function is called by the multiprocessing pool. It accepts a tuple
    to satisfy Pool.imap_unordered's interface.
    """
    config = SimConfig(*args)
    run_dir = Path(config.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Generate prescribed compression schedules
    user_schedules = build_prescribed_schedule(
        config.num_users, config.repetition
    )

    for i in range(config.num_users):
        presc_file = run_dir / f"prescribed_{i}.csv"
        with open(presc_file, "w") as pf:
            pf.write("frame,components\n")
            for frame_id, cl in user_schedules[i]:
                pf.write(f"{frame_id},{cl}\n")

    # Build OMNeT++ command
    cmd = [
        "simu5g",
        "../omnetpp.ini",
        "-u", "Cmdenv",
        "-c", "XR-DL-RandomCL",
        f"--sim-time-limit={config.sim_time}s",
        f"--seed-set={config.repetition}",
        f"--*.numUe={config.num_users}",
        f"--*.server.numApps={config.num_users}",
    ]

    # Add per-user overrides
    for i in range(config.num_users):
        video = config.video_assignments[i]
        fps = config.fps_assignments[i]
        pca_rel = os.path.relpath(config.traffic_paths[video], SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")
        presc_rel = os.path.relpath(run_dir / f"prescribed_{i}.csv", SCRIPT_DIR)

        # String values must be quoted for OMNeT++ command-line parsing
        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")

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
                timeout=6000,
            )

        if result.returncode != 0:
            log.warning(
                f"Sim n={config.num_users} r={config.repetition} "
                f"returned code {result.returncode}"
            )
            return None
    except subprocess.TimeoutExpired:
        log.warning(f"Sim n={config.num_users} r={config.repetition} timed out")
        return None
    except Exception as e:
        log.error(f"Sim n={config.num_users} r={config.repetition}: {e}")
        return None

    return {
        "num_users": config.num_users,
        "repetition": config.repetition,
        "run_dir": str(run_dir),
        "video_assignments": config.video_assignments,
        "fps_assignments": config.fps_assignments,
    }


# ─── Result collection ──────────────────────────────────────────────────────

def collect_run_results(run_info: dict, error_tables: dict) -> list:
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
            log.warning(f"Missing {csv_path}")
            return []
        user_data[i] = pd.read_csv(csv_path)

    frame_numbers = sorted(user_data[0]["frameNumber"].unique())

    rows = []
    skipped_missing_error = 0
    for frame_num in frame_numbers:
        if frame_num < 1 or frame_num > MAX_FRAMES:
            continue

        row = {"frameNumber": frame_num}
        skip_frame = False

        for i in range(num_users):
            prefix = f"user{i}_"

            frame_df = user_data[i][user_data[i]["frameNumber"] == frame_num]
            if frame_df.empty:
                skip_frame = True
                break

            frame_row = frame_df.iloc[0]

            # Per-frame data from simulation
            row[prefix + "components"] = int(frame_row["components"])
            row[prefix + "effectiveError"] = float(frame_row["effectiveError"])

            # Per-user video assignment and full MSE vector from summary file
            video_name = video_assignments[i]
            row[prefix + "video"] = video_name
            try:
                mse_vector = lookup_errors(error_tables, video_name, frame_num)
            except KeyError:
                skipped_missing_error += 1
                skip_frame = True
                break
            for cl_idx, cl in enumerate(CL_LEVELS):
                row[prefix + f"mse_at_{cl}"] = mse_vector[cl_idx]

            # Delay
            row[prefix + "delay_ms"] = float(frame_row["delay_ms"])

            # Per-frame CQI
            row[prefix + "cqi"] = (
                int(frame_row["cqi"]) if "cqi" in frame_row.index else 0
            )

            # gNB metrics (per user)
            row[prefix + "buffer_bytes"] = (
                int(frame_row["buffer_bytes"])
                if "buffer_bytes" in frame_row.index else 0
            )
            row[prefix + "mcs_index"] = (
                int(frame_row["mcs_index"])
                if "mcs_index" in frame_row.index else 0
            )

            # Global gNB metrics (read from user 0 to avoid duplication)
            if i == 0:
                row["dl_utilization"] = (
                    float(frame_row["dl_utilization"])
                    if "dl_utilization" in frame_row.index else 0.0
                )
                row["n_active_ues"] = (
                    int(frame_row["n_active_ues"])
                    if "n_active_ues" in frame_row.index else 0
                )

            row[prefix + "frame_rate"] = fps_assignments[i]

        if not skip_frame:
            row["num_users"] = num_users
            row["repetition"] = run_info["repetition"]
            rows.append(row)

    if skipped_missing_error > 0:
        log.info(
            f"Skipped {skipped_missing_error} frame/user entries due to missing "
            f"error labels: n={num_users} r={run_info['repetition']}"
        )

    return rows


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate XR streaming dataset")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only prepare files, don't run simulations",
    )
    parser.add_argument(
        "--repetitions", type=int, default=3,
        help="Number of repetitions per user count (default: 3)",
    )
    parser.add_argument(
        "--sim-time", type=int, default=SIM_TIME_LIMIT,
        help=f"Simulation time limit in seconds (default: {SIM_TIME_LIMIT})",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Base random seed for video assignments",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Resolve directories
    traffic_dir = SCRIPT_DIR.parent / "compression/traffic_files/pca"
    dataset_dir = SCRIPT_DIR.parent / "datasets/pca"

    pca_files = sorted(traffic_dir.glob(FILE_PREFIX + "*.csv"))

    log.info("=" * 60)
    log.info(f"XR Dataset Generation")
    log.info(f"  Videos: {len(pca_files)}")
    log.info(f"  Max frames: {MAX_FRAMES}")
    log.info(f"  User sweep: {NUM_USERS_SWEEP}")
    log.info(f"  Repetitions: {args.repetitions}")
    log.info(f"  Sim time: {args.sim_time}s")
    log.info(f"  Workers: {MAX_WORKERS}")
    log.info("=" * 60)

    traffic_paths = {}
    for pca_path in pca_files:
        video_name = pca_path.stem.replace(FILE_PREFIX, "")
        traffic_paths[video_name] = pca_path

    if not traffic_paths:
        log.error(f"No traffic summary files found in {traffic_dir}")
        return

    log.info("Loading per-video error tables...")
    error_tables = load_error_tables(traffic_paths)
    log.info(f"  Loaded error tables for {len(error_tables)} videos")

    if args.dry_run:
        log.info("[DRY RUN] Stopping before simulations.")
        log.info(f"Traffic files at: {traffic_dir}")
        return

    # Prepare simulation jobs
    log.info("Preparing simulation jobs...")
    video_names = list(traffic_paths.keys())

    jobs = []
    for num_users in NUM_USERS_SWEEP:
        for rep in range(args.repetitions):
            run_seed = args.seed + num_users * 100 + rep
            va = assign_videos(num_users, video_names, seed=run_seed)
            fa = assign_fps(num_users, seed=run_seed + 1000)
            run_dir = RESULTS_DIR / f"dataset_n{num_users}_r{rep}"

            jobs.append((
                num_users, rep, va, fa,
                {v: traffic_paths[v] for v in video_names},
                str(run_dir),
                args.sim_time,
                traffic_dir,
            ))

    total_jobs = len(jobs)
    log.info(f"  Total simulation jobs: {total_jobs}")
    log.info(f"  Using {MAX_WORKERS} parallel workers")

    # Run simulations in parallel
    log.info(f"Running {total_jobs} simulations...")

    completed_runs = []
    with Pool(processes=MAX_WORKERS) as pool:
        for i, result in enumerate(pool.imap_unordered(run_simulation, jobs)):
            pct = (i + 1) / total_jobs * 100
            if result is not None:
                completed_runs.append(result)
                log.info(
                    f"  [{i+1}/{total_jobs}] ({pct:.0f}%) "
                    f"n={result['num_users']} r={result['repetition']} ✓"
                )
            else:
                log.warning(f"  [{i+1}/{total_jobs}] ({pct:.0f}%) FAILED")

    log.info(f"Completed: {len(completed_runs)}/{total_jobs}")

    # Collect and assemble dataset
    log.info("Collecting results and assembling dataset...")

    all_rows = []
    for run_info in completed_runs:
        rows = collect_run_results(run_info, error_tables)
        all_rows.extend(rows)
        log.info(
            f"  n={run_info['num_users']} r={run_info['repetition']}: "
            f"{len(rows)} rows"
        )

    if not all_rows:
        log.error("No data collected!")
        return

    dataset = pd.DataFrame(all_rows)

    # Reorder columns
    user_cols = []
    max_users = max(r["num_users"] for r in completed_runs)
    mse_suffixes = [f"mse_at_{cl}" for cl in CL_LEVELS]
    for i in range(max_users):
        for suffix in (
            ["components", "effectiveError"]
            + mse_suffixes
            + ["delay_ms", "cqi", "buffer_bytes", "mcs_index", "frame_rate"]
        ):
            col = f"user{i}_{suffix}"
            if col in dataset.columns:
                user_cols.append(col)
        video_col = f"user{i}_video"
        if video_col in dataset.columns:
            user_cols.append(video_col)

    col_order = (
        ["frameNumber", "repetition", "dl_utilization", "n_active_ues"]
        + user_cols
        + ["num_users"]
    )
    col_order = [c for c in col_order if c in dataset.columns]
    dataset = dataset[col_order]

    # Save
    dataset_dir.mkdir(parents=True, exist_ok=True)
    out_path = dataset_dir / "dataset.csv"
    dataset.to_csv(out_path, index=False)

    log.info("=" * 60)
    log.info(f"Dataset generated: {out_path}")
    log.info(f"  Total rows: {len(dataset)}")
    log.info(f"  Columns: {len(dataset.columns)}")
    log.info(f"  Users sweep: {sorted(dataset['num_users'].unique())}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
