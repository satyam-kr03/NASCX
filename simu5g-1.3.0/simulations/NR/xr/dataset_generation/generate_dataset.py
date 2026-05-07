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


# All 16 compression levels (5, 10, 15, ..., 80)
CL_LEVELS = list(range(5, 81, 5))   # [5, 10, 15, ..., 80]
NUM_CL_LEVELS = len(CL_LEVELS)      # 16


def load_error_tables(traffic_paths):
    """Load per-video error tables: {video: {frame: [mse_at_5, ..., mse_at_80]}}.

    For each frame, builds a fixed-length 16-element vector of MSE values,
    one per compression level (5, 10, ..., 80).
    """
    error_tables = {}
    for video_name, summary_path in traffic_paths.items():
        if not Path(summary_path).exists():
            raise FileNotFoundError(f"Missing summary file for video '{video_name}': {summary_path}")

        df = pd.read_csv(summary_path)

        required_cols = {"frame", "components", "mse"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(
                f"Summary file {summary_path} is missing required columns: {sorted(missing)}"
            )

        # Pivot: for each frame, collect MSE at each CL
        table = {}  # frame_number → list of 16 MSE values
        for frame_num, grp in df.groupby("frame"):
            frame_num = int(frame_num)
            mse_by_cl = {int(row["components"]): float(row["mse"]) for _, row in grp.iterrows()}

            mse_vector = []
            for cl in CL_LEVELS:
                mse_vector.append(mse_by_cl.get(cl, 0.0))

            table[frame_num] = mse_vector

        error_tables[video_name] = table

    return error_tables


def lookup_errors(error_tables, video_name, frame_number):
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


# ─── Step 1: Assign videos to users ─────────────────────────────────────────

def assign_videos(num_users, video_names, seed=42):
    """Assign videos to users. Cycles through available videos."""
    rng = random.Random(seed)
    shuffled = list(video_names)
    rng.shuffle(shuffled)
    assignments = [shuffled[i % len(shuffled)] for i in range(num_users)]
    #!/usr/bin/env python3
    """
    Dataset Generation Script for XR Streaming Simulation.

    Generates an ML training dataset by running simu5g simulations with random
    per-frame compression levels. Each user is assigned a video stream (PCA file),
    and the simulation randomly selects compression levels per frame.

    Usage:
        python generate_dataset.py [--dry-run] [--repetitions N] [--sim-time S]

    Output:
        datasets/pca/dataset.csv
    """

    import argparse
    import logging
    import os
    import subprocess
    from dataclasses import dataclass
    from multiprocessing import Pool, cpu_count
    from pathlib import Path
    from typing import Dict, List

    import numpy as np
    import pandas as pd

    # ─── Configuration ───────────────────────────────────────────────────────────

    MAX_FRAMES = 1000      # Only use first 1000 frames per video
    FPS = 60               # Frames per second (default)
    FPS_OPTIONS = [45, 60, 72, 90, 120]  # Per-user frame rate choices
    SIM_TIME_LIMIT = 35    # seconds (>= 1000/60 ≈ 16.7s, with margin)
    DEADLINE_MS = 2.5     # Frame deadline in ms
    NUM_USERS_SWEEP = list(range(2, 11))  # 2..10 users

    # Parallelism
    MAX_WORKERS = min(cpu_count(), 32)

    # All 16 compression levels (5, 10, 15, ..., 80)
    CL_LEVELS = list(range(5, 81, 5))   # [5, 10, 15, ..., 80]
    NUM_CL_LEVELS = len(CL_LEVELS)      # 16


    @dataclass(frozen=True)
    class SimConfig:
        script_dir: Path
        traffic_dir: Path
        results_dir: Path
        dataset_dir: Path
        file_prefix: str
        max_frames: int
        fps_options: List[int]
        sim_time_limit: int
        num_users_sweep: List[int]
        max_workers: int


    @dataclass(frozen=True)
    class RunJob:
        num_users: int
        repetition: int
        video_assignments: List[str]
        fps_assignments: List[int]
        traffic_paths: Dict[str, Path]
        run_dir: Path
        sim_time: int
        max_frames: int
        script_dir: Path


    @dataclass(frozen=True)
    class RunResult:
        num_users: int
        repetition: int
        run_dir: Path
        video_assignments: List[str]
        fps_assignments: List[int]


    def load_error_tables(traffic_paths: Dict[str, Path]) -> Dict[str, Dict[int, List[float]]]:
        """Load per-video error tables: {video: {frame: [mse_at_5, ..., mse_at_80]}}.

        For each frame, builds a fixed-length 16-element vector of MSE values,
        one per compression level (5, 10, ..., 80).
        """
        error_tables = {}
        for video_name, summary_path in traffic_paths.items():
            if not Path(summary_path).exists():
                raise FileNotFoundError(f"Missing summary file for video '{video_name}': {summary_path}")

            df = pd.read_csv(summary_path)

            required_cols = {"frame", "components", "mse"}
            missing = required_cols - set(df.columns)
            if missing:
                raise ValueError(
                    f"Summary file {summary_path} is missing required columns: {sorted(missing)}"
                )

            # Pivot: for each frame, collect MSE at each CL
            table = {}  # frame_number → list of 16 MSE values
            for frame_num, grp in df.groupby("frame"):
                frame_num = int(frame_num)
                mse_by_cl = {int(row["components"]): float(row["mse"]) for _, row in grp.iterrows()}

                mse_vector = []
                for cl in CL_LEVELS:
                    mse_vector.append(mse_by_cl.get(cl, 0.0))

                table[frame_num] = mse_vector

            error_tables[video_name] = table

        return error_tables


    def lookup_errors(error_tables: Dict[str, Dict[int, List[float]]], video_name: str, frame_number: int) -> List[float]:
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


    # ─── Step 1: Assign videos to users ─────────────────────────────────────────

    def assign_videos(num_users: int, video_names: List[str], seed: int = 42) -> List[str]:
        """Assign videos to users. Cycles through available videos."""
        rng = np.random.default_rng(seed)
        shuffled = list(video_names)
        rng.shuffle(shuffled)
        assignments = [shuffled[i % len(shuffled)] for i in range(num_users)]
        return assignments


    def assign_fps(num_users: int, fps_options: List[int], seed: int = 42) -> List[int]:
        """Assign a random frame rate to each user from fps_options."""
        rng = np.random.default_rng(seed)
        return [int(rng.choice(fps_options)) for _ in range(num_users)]


    def build_prescribed_schedule(
        num_users: int,
        max_frames: int,
        rng: np.random.Generator,
        *,
        is_static: bool,
        static_level: int,
        min_components: int = 5,
        max_components: int = 80,
        step: int = 5,
    ) -> Dict[int, List[tuple[int, int]]]:
        user_schedules = {i: [] for i in range(num_users)}
        for frame_id in range(1, max_frames + 200):
            if is_static:
                for i in range(num_users):
                    user_schedules[i].append((frame_id, static_level))
            else:
                # Correlated random: pick a base level for the whole network
                # Then add noise per user
                base_cl = int(rng.choice(np.arange(min_components, max_components + 1, step)))
                for i in range(num_users):
                    noise = int(rng.choice([-10, -5, 0, 5, 10]))
                    user_cl = base_cl + noise
                    # Bound to valid range and align to nearest step
                    user_cl = max(min_components, min(max_components, user_cl))
                    user_cl = round(user_cl / step) * step
                    user_schedules[i].append((frame_id, int(user_cl)))
        return user_schedules


    # ─── Step 2: Run a single simulation ────────────────────────────────────────

    def run_simulation(job: RunJob) -> RunResult | None:
        """Run one simulation for a given (num_users, repetition) pair.

        This function is called by the multiprocessing pool.
        """
        logger = logging.getLogger(__name__)

        run_dir = Path(job.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        rng = np.random.default_rng(job.repetition + job.num_users * 1000)

        is_static = job.repetition < 16
        static_level = 5 + job.repetition * 5 if is_static else 5

        user_schedules = build_prescribed_schedule(
            job.num_users,
            job.max_frames,
            rng,
            is_static=is_static,
            static_level=static_level,
        )

        for i in range(job.num_users):
            presc_file = run_dir / f"prescribed_{i}.csv"
            with open(presc_file, "w") as pf:
                pf.write("frame,components\n")
                for frame_id, cl in user_schedules[i]:
                    pf.write(f"{frame_id},{cl}\n")

        cmd = [
            "simu5g",
            "../omnetpp.ini",
            "-u", "Cmdenv",
            "-c", "XR-DL-RandomCL",
            f"--sim-time-limit={job.sim_time}s",
            f"--seed-set={job.repetition}",
            f"--*.numUe={job.num_users}",
            f"--*.server.numApps={job.num_users}",
        ]

        # Add per-user overrides
        for i in range(job.num_users):
            video = job.video_assignments[i]
            fps = job.fps_assignments[i]
            pca_rel = os.path.relpath(job.traffic_paths[video], job.script_dir)
            result_file = str(run_dir / f"user_{i}.csv")
            presc_rel = os.path.relpath(run_dir / f"prescribed_{i}.csv", job.script_dir)

            # String values must be quoted for OMNeT++ command-line parsing
            cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
            cmd.append(f'--*.server.app[{i}].fps={fps}')
            cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
            cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
            cmd.append(f"--*.ue[{i}].app[0].expectedFrames={job.max_frames}")

            # Override to use prescribed schedule
            cmd.append(f'--*.server.app[{i}].selectionMode="prescribed"')
            cmd.append(f'--*.server.app[{i}].prescribedFile="{presc_rel}"')

        log_file = run_dir / "sim.log"

        try:
            with open(log_file, "w") as log_f:
                result = subprocess.run(
                    cmd,
                    cwd=str(job.script_dir),
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    timeout=6000,  # 10 min timeout per sim
                )

            if result.returncode != 0:
                logger.warning(
                    "Sim n=%s r=%s returned code %s",
                    job.num_users,
                    job.repetition,
                    result.returncode,
                )
                return None
        except subprocess.TimeoutExpired:
            logger.warning("Sim n=%s r=%s timed out", job.num_users, job.repetition)
            return None
        except Exception as exc:
            logger.error("Sim n=%s r=%s: %s", job.num_users, job.repetition, exc)
            return None

        return RunResult(
            num_users=job.num_users,
            repetition=job.repetition,
            run_dir=run_dir,
            video_assignments=job.video_assignments,
            fps_assignments=job.fps_assignments,
        )


    # ─── Step 3: Collect results from a simulation run ──────────────────────────

    def collect_run_results(run_info: RunResult, error_tables: Dict[str, Dict[int, List[float]]]) -> List[Dict]:
        """Collect per-frame data from a single simulation run.

        Produces rows matching the desired dataset format:
            frameNumber, user0_components, user0_effectiveError,
            user0_delay_ms, user0_cqi, ..., num_users
        """
        logger = logging.getLogger(__name__)

        num_users = run_info.num_users
        run_dir = Path(run_info.run_dir)
        video_assignments = run_info.video_assignments
        fps_assignments = run_info.fps_assignments

        # Read per-user result CSVs
        user_data = {}

        for i in range(num_users):
            csv_path = run_dir / f"user_{i}.csv"

            if not csv_path.exists():
                logger.warning("Missing %s", csv_path)
                return []

            # Read per-frame results (now includes per-frame 'cqi' column)
            df = pd.read_csv(csv_path)
            user_data[i] = df

        # Build dataset rows (each row = one frame number across all users)
        # Only include frames where ALL users have data
        frame_numbers = sorted(user_data[0]["frameNumber"].unique())

        # Filter to only actual transmitted frames (not lost/padding rows)
        rows = []
        skipped_missing_error = 0
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

                # Per-user video assignment and full MSE vector from summary file
                video_name = video_assignments[i]
                row[prefix + "video"] = video_name
                try:
                    mse_vector = lookup_errors(
                        error_tables,
                        video_name,
                        frame_num,
                    )
                except KeyError:
                    skipped_missing_error += 1
                    skip_frame = True
                    break
                for cl_idx, cl in enumerate(CL_LEVELS):
                    row[prefix + f"mse_at_{cl}"] = mse_vector[cl_idx]

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
                row["num_users"] = num_users
                row["repetition"] = run_info.repetition
                rows.append(row)

        if skipped_missing_error > 0:
            logger.info(
                "Skipped %s frame/user entries due to missing error labels "
                "(likely holdout frames): n=%s r=%s",
                skipped_missing_error,
                num_users,
                run_info.repetition,
            )

        return rows


    # ─── Main ────────────────────────────────────────────────────────────────────

    def main() -> None:
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

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        logger = logging.getLogger(__name__)

        script_dir = Path(__file__).parent.resolve()
        traffic_dir = script_dir.parent / "compression/traffic_files/pca"
        results_dir = script_dir / "results"
        dataset_dir = script_dir.parent / "datasets/pca"

        config = SimConfig(
            script_dir=script_dir,
            traffic_dir=traffic_dir,
            results_dir=results_dir,
            dataset_dir=dataset_dir,
            file_prefix="pca_sweep_summary_",
            max_frames=MAX_FRAMES,
            fps_options=FPS_OPTIONS,
            sim_time_limit=args.sim_time,
            num_users_sweep=NUM_USERS_SWEEP,
            max_workers=MAX_WORKERS,
        )

        dataset_dir.mkdir(parents=True, exist_ok=True)

        pca_files = sorted(config.traffic_dir.glob(config.file_prefix + "*.csv"))

        logger.info("=" * 60)
        logger.info("XR Dataset Generation")
        logger.info("  Videos: %s", len(pca_files))
        logger.info("  Max frames: %s", config.max_frames)
        logger.info("  User sweep: %s", config.num_users_sweep)
        logger.info("  Repetitions: %s", args.repetitions)
        logger.info("  Sim time: %ss", config.sim_time_limit)
        logger.info("  Workers: %s", config.max_workers)
        logger.info("=" * 60)

        traffic_paths = {}
        for pca_path in pca_files:
            video_name = pca_path.stem.replace(config.file_prefix, "")
            traffic_paths[video_name] = pca_path

        if not traffic_paths:
            logger.error(
                "No traffic summary files found in %s with prefix '%s'",
                config.traffic_dir,
                config.file_prefix,
            )
            return

        logger.info("\n[0/3] Loading per-video error tables...")
        error_tables = load_error_tables(traffic_paths)
        logger.info("  Loaded error tables for %s videos", len(error_tables))

        if args.dry_run:
            logger.info("\n[DRY RUN] Stopping before simulations.")
            logger.info("Traffic files at: %s", config.traffic_dir)
            return

        # Step 1: Prepare simulation jobs
        logger.info("\n[1/3] Preparing simulation jobs...")
        video_names = list(traffic_paths.keys())

        jobs: List[RunJob] = []
        for num_users in config.num_users_sweep:
            for rep in range(args.repetitions):
                run_seed = args.seed + num_users * 100 + rep
                video_assignments = assign_videos(num_users, video_names, seed=run_seed)
                fps_assignments = assign_fps(num_users, config.fps_options, seed=run_seed + 1000)

                run_dir = config.results_dir / f"dataset_n{num_users}_r{rep}"

                jobs.append(RunJob(
                    num_users=num_users,
                    repetition=rep,
                    video_assignments=video_assignments,
                    fps_assignments=fps_assignments,
                    traffic_paths=traffic_paths,
                    run_dir=run_dir,
                    sim_time=config.sim_time_limit,
                    max_frames=config.max_frames,
                    script_dir=config.script_dir,
                ))

        total_jobs = len(jobs)
        logger.info("  Total simulation jobs: %s", total_jobs)
        logger.info("  Using %s parallel workers", config.max_workers)

        # Step 2: Run simulations in parallel
        logger.info("\n[2/3] Running %s simulations...", total_jobs)

        completed_runs: List[RunResult] = []
        with Pool(processes=config.max_workers) as pool:
            for i, result in enumerate(pool.imap_unordered(run_simulation, jobs)):
                pct = (i + 1) / total_jobs * 100
                if result is not None:
                    completed_runs.append(result)
                    logger.info(
                        "  [%s/%s] (%.0f%%) n=%s r=%s ✓",
                        i + 1,
                        total_jobs,
                        pct,
                        result.num_users,
                        result.repetition,
                    )
                else:
                    logger.warning("  [%s/%s] (%.0f%%) FAILED", i + 1, total_jobs, pct)

        logger.info("\n  Completed: %s/%s", len(completed_runs), total_jobs)

        # Step 3: Collect and assemble dataset
        logger.info("\n[3/3] Collecting results and assembling dataset...")

        all_rows = []
        for run_info in completed_runs:
            rows = collect_run_results(run_info, error_tables)
            all_rows.extend(rows)
            logger.info(
                "  n=%s r=%s: %s rows",
                run_info.num_users,
                run_info.repetition,
                len(rows),
            )

        if not all_rows:
            logger.error("No data collected!")
            return

        # Build DataFrame
        dataset = pd.DataFrame(all_rows)

        # Reorder columns: frameNumber, then user columns in order, then num_users
        user_cols = []
        max_users = max(r.num_users for r in completed_runs)
        mse_suffixes = [f"mse_at_{cl}" for cl in CL_LEVELS]
        for i in range(max_users):
            for suffix in ["components", "effectiveError"] + mse_suffixes + [
                            "delay_ms", "cqi", "buffer_bytes", "mcs_index",
                            "frame_rate"]:
                col = f"user{i}_{suffix}"
                if col in dataset.columns:
                    user_cols.append(col)
            video_col = f"user{i}_video"
            if video_col in dataset.columns:
                user_cols.append(video_col)

        col_order = ["frameNumber", "repetition", "dl_utilization", "n_active_ues"] + user_cols + ["num_users"]
        # Only keep columns that exist
        col_order = [c for c in col_order if c in dataset.columns]
        dataset = dataset[col_order]

        # Save
        out_path = config.dataset_dir / "dataset.csv"
        dataset.to_csv(out_path, index=False)

        logger.info("\n%s", "=" * 60)
        logger.info("Dataset generated: %s", out_path)
        logger.info("  Total rows: %s", len(dataset))
        logger.info("  Columns: %s", len(dataset.columns))
        logger.info("  Users sweep: %s", sorted(dataset["num_users"].unique()))
        logger.info("%s", "=" * 60)


    if __name__ == "__main__":
        main()
