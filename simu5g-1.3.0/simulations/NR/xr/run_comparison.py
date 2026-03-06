#!/usr/bin/env python3
"""
Comparison Script: Model-Based Adaptive vs Static Compression Levels.

Pipeline:
  1. Run a "probe" simulation with a mid-range fixed compression level
     to obtain per-frame CQI for each user.
  2. Query the model server with per-frame (CQI + video features) to
     obtain the model's prescribed compression schedule per user.
  3. Run a "model" simulation using prescribed schedules.
  4. Run static simulations for every compression level (25,50,...,400).
  5. Collect effective-error results from all runs and write a comparison CSV.

Usage:
    python run_comparison.py [--num-users N] [--sim-time S] [--seed SEED]
                             [--server-url URL] [--dry-run]
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
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Configuration ─────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
TRAFFIC_DIR = SCRIPT_DIR / "traffic_files"
TRIMMED_DIR = TRAFFIC_DIR / "trimmed"
RESULTS_DIR = SCRIPT_DIR / "comparison_results"
DATASET_DIR = SCRIPT_DIR / "datasets"

COMP_LEVELS = list(range(25, 401, 25))       # 25, 50, 75, ... 400
PROBE_LEVEL = 200                             # Mid-range probe level
MAX_FRAMES = 2000
FPS = 60
DEADLINE_MS = 5.0
FPS_OPTIONS = [45, 60, 72, 90, 120]            # Per-user frame rate choices

# PCA files (trimmed to 2000 frames)
PCA_FILES = sorted(TRIMMED_DIR.glob("pca_sweep_summary_*.csv"))

MODEL_SERVER_URL = "http://localhost:8000"


# ── Helpers ───────────────────────────────────────────────────────────────────

def video_name_from_path(p: Path) -> str:
    return p.stem.replace("pca_sweep_summary_", "")


def assign_videos(num_users: int, seed: int = 42) -> list[str]:
    """Assign videos to users by cycling through available videos."""
    names = [video_name_from_path(p) for p in PCA_FILES]
    rng = random.Random(seed)
    rng.shuffle(names)
    return [names[i % len(names)] for i in range(num_users)]


def assign_fps(num_users: int, seed: int = 42) -> list[int]:
    """Assign a random frame rate to each user from FPS_OPTIONS."""
    rng = random.Random(seed + 1000)
    return [rng.choice(FPS_OPTIONS) for _ in range(num_users)]


def pca_path_for_video(video: str) -> Path:
    return TRIMMED_DIR / f"pca_sweep_summary_{video}.csv"


def compute_video_stats(video: str) -> dict:
    """Compute mean/std of frame_complexity and per-frame complexity map."""
    df = pd.read_csv(pca_path_for_video(video))
    frame_df = df.drop_duplicates(subset="frame")[["frame", "frame_complexity"]].copy()
    frame_df = frame_df.sort_values("frame").head(MAX_FRAMES)
    return {
        "mean_traffic_size": float(frame_df["frame_complexity"].mean()),
        "std_traffic_size": float(frame_df["frame_complexity"].std()),
        "complexity_per_frame": dict(
            zip(frame_df["frame"].astype(int), frame_df["frame_complexity"].astype(float))
        ),
    }


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
) -> list[str]:
    """Build the OMNeT++ command line for one simulation run."""
    cmd = [
        "simu5g",
        "omnetpp.ini",
        "-u", "Cmdenv",
        "-c", config,
        f"--sim-time-limit={sim_time}s",
        f"--seed-set={seed}",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
    ]

    for i in range(num_users):
        video = video_assignments[i]
        pca_rel = os.path.relpath(pca_path_for_video(video), SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")

        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].selectionMode="{selection_mode}"')
        cmd.append(f"--*.server.app[{i}].compressionLevel={compression_level}")

        if selection_mode == "prescribed" and prescribed_files and i in prescribed_files:
            cmd.append(f'--*.server.app[{i}].prescribedFile="{prescribed_files[i]}"')

        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")

    return cmd


def run_sim(cmd: list[str], run_dir: Path, label: str, timeout: int = 600) -> bool:
    """Execute a simulation, return True on success."""
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / "sim.log"

    print(f"  [{label}] Running ... ", end="", flush=True)
    t0 = time.time()
    try:
        with open(log_file, "w") as lf:
            result = subprocess.run(
                cmd,
                cwd=str(SCRIPT_DIR),
                stdout=lf,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        elapsed = time.time() - t0
        if result.returncode != 0:
            print(f"FAILED (code {result.returncode}, {elapsed:.0f}s)")
            return False
        print(f"OK ({elapsed:.0f}s)")
        return True
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT ({timeout}s)")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


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


# ── Step 1: Probe simulation ─────────────────────────────────────────────────

def run_probe(num_users, sim_time, seed, video_assignments):
    """Run a fixed-level probe sim to capture per-frame CQI."""
    run_dir = RESULTS_DIR / "probe"
    if run_dir.exists():
        shutil.rmtree(run_dir)

    cmd = build_sim_cmd(
        config="XR-DL-RandomCL",
        num_users=num_users,
        sim_time=sim_time,
        seed=seed,
        video_assignments=video_assignments,
        run_dir=run_dir,
        selection_mode="fixed",
        compression_level=PROBE_LEVEL,
    )

    ok = run_sim(cmd, run_dir, f"Probe (fixed@{PROBE_LEVEL})")
    if not ok:
        return None
    return read_user_results(run_dir, num_users)


# ── Step 2: Query model server ───────────────────────────────────────────────

def query_model_for_frames(
    num_users: int,
    video_assignments: list[str],
    video_stats: dict[str, dict],
    probe_data: dict[int, pd.DataFrame],
    server_url: str,
    fps_assignments: list[int] | None = None,
) -> dict[int, pd.DataFrame]:
    """
    For each frame, build per-user features and query the model server.
    Returns per-user DataFrames with columns [frame, components].
    """
    if fps_assignments is None:
        fps_assignments = [FPS] * num_users
    # Build per-frame CQI lookup from probe results
    user_cqi = {}
    for i, df in probe_data.items():
        cqi_map = dict(zip(df["frameNumber"].astype(int), df["cqi"].astype(int)))
        user_cqi[i] = cqi_map

    # Collect all frame numbers present across all users
    all_frames = set()
    for i in range(num_users):
        all_frames |= set(probe_data[i]["frameNumber"].astype(int))
    frame_list = sorted(all_frames)

    # Build prescribed schedule per user
    prescribed: dict[int, list[dict]] = {i: [] for i in range(num_users)}

    # Process in batches (one model call per frame)
    batch_size = 200
    total = len(frame_list)
    print(f"  Querying model for {total} frames ({num_users} users) ...")

    for batch_start in range(0, total, batch_size):
        batch_frames = frame_list[batch_start : batch_start + batch_size]

        for frame_num in batch_frames:
            users_payload = []
            valid = True
            for i in range(num_users):
                video = video_assignments[i]
                stats = video_stats[video]
                cqi = user_cqi.get(i, {}).get(frame_num, 10)
                # Clamp CQI to model's range [5, 15]
                cqi = max(5, min(15, cqi))

                fc = stats["complexity_per_frame"].get(frame_num, 0.0)

                users_payload.append({
                    "meantrafficsize": stats["mean_traffic_size"],
                    "stdtrafficsize": stats["std_traffic_size"],
                    "frameComplexity": fc,
                    "frame_rate": fps_assignments[i],
                    "cqi": cqi,
                })

            try:
                resp = requests.post(
                    f"{server_url}/predict",
                    json={"users": users_payload},
                    timeout=5,
                )
                resp.raise_for_status()
                result = resp.json()

                for pred in result["predictions"]:
                    uid = pred["user_id"]
                    comp = pred["optimal_components"]
                    prescribed[uid].append({"frame": frame_num, "components": comp})
            except Exception as e:
                # On failure, fall back to probe level
                for i in range(num_users):
                    prescribed[i].append({"frame": frame_num, "components": PROBE_LEVEL})

        pct = min(100, (batch_start + len(batch_frames)) / total * 100)
        print(f"    {pct:.0f}% ({batch_start + len(batch_frames)}/{total})", flush=True)

    return {i: pd.DataFrame(prescribed[i]) for i in range(num_users)}


# ── Step 3: Write prescribed CSV files and run model sim ─────────────────────

def run_model_sim(
    num_users: int,
    sim_time: int,
    seed: int,
    video_assignments: list[str],
    prescribed_dfs: dict[int, pd.DataFrame],
):
    """Write prescribed CSVs and run the model-driven simulation."""
    run_dir = RESULTS_DIR / "model"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    prescribed_files: dict[int, Path] = {}
    for i in range(num_users):
        p = run_dir / f"prescribed_user_{i}.csv"
        prescribed_dfs[i].to_csv(p, index=False)
        prescribed_files[i] = p

    cmd = build_sim_cmd(
        config="XR-DL-RandomCL",
        num_users=num_users,
        sim_time=sim_time,
        seed=seed,
        video_assignments=video_assignments,
        run_dir=run_dir,
        selection_mode="prescribed",
        compression_level=0,
        prescribed_files=prescribed_files,
    )

    ok = run_sim(cmd, run_dir, "Model (prescribed)")
    if not ok:
        return None
    return read_user_results(run_dir, num_users)


# ── Step 4: Run static simulations ───────────────────────────────────────────

def run_static_sims(
    num_users: int,
    sim_time: int,
    seed: int,
    video_assignments: list[str],
    levels: list[int] | None = None,
) -> dict[int, dict[int, pd.DataFrame]]:
    """
    Run one simulation per static compression level.
    Returns: {comp_level: {user_id: DataFrame}}.
    """
    if levels is None:
        levels = COMP_LEVELS

    results = {}
    for cl in levels:
        run_dir = RESULTS_DIR / f"static_{cl}"
        if run_dir.exists():
            shutil.rmtree(run_dir)

        cmd = build_sim_cmd(
            config="XR-DL-RandomCL",
            num_users=num_users,
            sim_time=sim_time,
            seed=seed,
            video_assignments=video_assignments,
            run_dir=run_dir,
            selection_mode="fixed",
            compression_level=cl,
        )

        ok = run_sim(cmd, run_dir, f"Static CL={cl}")
        if ok:
            results[cl] = read_user_results(run_dir, num_users)

    return results


# ── Step 5: Assemble comparison results ──────────────────────────────────────

def assemble_comparison(
    num_users: int,
    video_assignments: list[str],
    model_data: dict[int, pd.DataFrame] | None,
    static_data: dict[int, dict[int, pd.DataFrame]],
    out_path: Path,
):
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
        description="Compare model-adaptive vs static XR compression"
    )
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
    parser.add_argument("--timeout", type=int, default=600,
                        help="Per-simulation timeout in seconds (default: 600)")
    args = parser.parse_args()

    num_users = args.num_users
    sim_time = args.sim_time
    seed = args.seed
    server_url = args.server_url

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  Model vs Static Compression Comparison")
    print("=" * 65)
    print(f"  Users:           {num_users}")
    print(f"  Sim time:        {sim_time}s")
    print(f"  Seed:            {seed}")
    print(f"  Probe level:     {PROBE_LEVEL}")
    print(f"  Static levels:   {COMP_LEVELS[0]}-{COMP_LEVELS[-1]} "
          f"(step 25, {len(COMP_LEVELS)} sims)")
    print(f"  Model server:    {server_url}")
    print(f"  Output dir:      {RESULTS_DIR}")

    # Assign videos and frame rates
    video_assignments = assign_videos(num_users, seed)
    fps_assignments = assign_fps(num_users, seed)
    print(f"\n  Video & FPS assignments:")
    for i, v in enumerate(video_assignments):
        print(f"    User {i}: {v}  ({fps_assignments[i]} fps)")

    # Pre-compute video stats (for model queries)
    video_stats = {}
    for v in set(video_assignments):
        video_stats[v] = compute_video_stats(v)

    if args.dry_run:
        print(f"\n[DRY RUN] Would run {1 + 1 + len(COMP_LEVELS)} simulations.")
        print("  1x probe, 1x model, " + f"{len(COMP_LEVELS)}x static")
        return

    # Check model server health
    print(f"\n[0/5] Checking model server ...")
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

    # ── Step 1: Probe simulation ──────────────────────────────────────────
    print(f"\n[1/5] Running probe simulation (fixed CL={PROBE_LEVEL}) ...")
    probe_data = run_probe(num_users, sim_time, seed, video_assignments)
    if probe_data is None:
        print("[ERROR] Probe simulation failed. Aborting.")
        return
    for i in range(num_users):
        if i in probe_data:
            n = len(probe_data[i])
            cqi_mean = probe_data[i]["cqi"].mean() if "cqi" in probe_data[i].columns else 0
            print(f"    User {i}: {n} frames, avg CQI={cqi_mean:.1f}")

    # ── Step 2: Query model ───────────────────────────────────────────────
    print(f"\n[2/5] Querying model server for prescribed levels ...")
    prescribed_dfs = query_model_for_frames(
        num_users, video_assignments, video_stats, probe_data, server_url,
        fps_assignments=fps_assignments,
    )
    for i in range(num_users):
        vc = prescribed_dfs[i]["components"].value_counts()
        print(f"    User {i}: {len(prescribed_dfs[i])} frames, "
              f"top levels: {dict(vc.head(3))}")

    # ── Step 3: Model simulation ──────────────────────────────────────────
    print(f"\n[3/5] Running model (prescribed) simulation ...")
    model_data = run_model_sim(
        num_users, sim_time, seed, video_assignments, prescribed_dfs
    )
    if model_data is None:
        print("[WARN] Model simulation failed.")

    # ── Step 4: Static simulations ────────────────────────────────────────
    print(f"\n[4/5] Running {len(COMP_LEVELS)} static simulations ...")
    static_data = run_static_sims(
        num_users, sim_time, seed, video_assignments
    )
    print(f"  Completed: {len(static_data)}/{len(COMP_LEVELS)}")

    # ── Step 5: Assemble results ──────────────────────────────────────────
    print(f"\n[5/5] Assembling comparison results ...")
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

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
