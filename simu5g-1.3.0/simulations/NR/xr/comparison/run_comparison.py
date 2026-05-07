#!/usr/bin/env python3
"""
Comparison Script: Model-Based Adaptive vs Static Compression Levels.

Runs simulations in parallel to compare:
  1. Model-adaptive compression (queries the model server each frame)
  2. Static compression at every level (5, 10, ..., 80)

All simulations are launched concurrently via ProcessPoolExecutor.

Usage:
    python run_comparison.py [--num-users N] [--sim-time S] [--seed SEED]
                             [--server-url URL] [--dry-run] [--max-workers W]
"""

import argparse
import csv
import logging
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

log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()

COMP_LEVELS = list(range(5, 81, 5))  # [5, 10, 15, ..., 80]
MAX_FRAMES = 500
FPS_OPTIONS = [60]  # Moderate load for comparison

FILE_PREFIX = "pca_sweep_summary_"

# Traffic file paths (set after CLI parsing)
TRAFFIC_DIR = None
TRIMMED_DIR = None
RESULTS_DIR = None
PCA_FILES = []

MODEL_SERVER_URL = "http://localhost:8000"
DEFAULT_MAX_WORKERS = 31


# ── Helpers ──────────────────────────────────────────────────────────────────

def video_name_from_path(p: Path) -> str:
    return p.stem.replace(FILE_PREFIX, "")


def assign_videos(num_users: int, seed: int = 42) -> list:
    """Assign videos to users by cycling through available videos."""
    names = [video_name_from_path(p) for p in PCA_FILES]
    rng = random.Random(seed)
    rng.shuffle(names)
    return [names[i % len(names)] for i in range(num_users)]


def assign_fps(num_users: int, seed: int = 42) -> list:
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
    video_assignments: list,
    run_dir: Path,
    *,
    selection_mode: str = "fixed",
    compression_level: int = 0,
    model_server_url: str = "",
    fps_assignments: list = None,
) -> list:
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

        if selection_mode == "model":
            cmd.append(f'--*.server.app[{i}].modelServerUrl="{model_server_url}"')
            cmd.append(f"--*.server.app[{i}].modelNumUsers={num_users}")

        if fps_assignments:
            cmd.append(f"--*.server.app[{i}].fps={fps_assignments[i]}")

        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")

    return cmd


def read_user_results(run_dir: Path, num_users: int) -> dict:
    """Read per-user result CSVs from a simulation run."""
    data = {}
    for i in range(num_users):
        p = run_dir / f"user_{i}.csv"
        if p.exists():
            data[i] = pd.read_csv(p)
        else:
            log.warning(f"Missing {p}")
    return data


# ── Shared metrics extraction (eliminates model/static duplication) ──────

def _extract_user_metrics(
    run_dir: Path, user_idx: int, df: pd.DataFrame
) -> dict:
    """Extract per-user QoE metrics from simulation results.

    Tries the ``.summary`` file first (written by XRTrafficReceiver),
    falls back to computing from the raw CSV.
    """
    summary_path = run_dir / f"user_{user_idx}.csv.summary"
    missing_only_lost = _count_missing_only_lost_rows(df)

    if summary_path.exists():
        summary = _read_summary_file(summary_path)
        if summary is not None:
            lost = int(summary.get("lost_frames", 0))
            return {
                "mean_effective_error": summary["mean_effective_error"],
                "on_time_ratio": summary["on_time_ratio"],
                "mean_delay_ms": summary["mean_delay_ms"],
                "expected_frames": summary["expected_frames"],
                "received_frames": summary["received_frames"],
                "late_frames": summary["late_frames"],
                "lost_frames": lost,
                "delivery_ratio": summary["delivery_ratio"],
                "loss_ratio": summary["loss_ratio"],
                "missing_only_lost": missing_only_lost,
                "incomplete_lost": max(0, lost - missing_only_lost),
                "eval_source": "summary",
            }

    # Fallback: compute from raw CSV
    mean_err = float(df["effectiveError"].mean()) if "effectiveError" in df.columns else float("nan")
    on_time = float(df["receivedOnTime"].mean()) if "receivedOnTime" in df.columns else float("nan")
    mean_delay = float(df["delay_ms"].mean()) if "delay_ms" in df.columns else float("nan")
    expected = int(df["frameNumber"].max()) if ("frameNumber" in df.columns and not df.empty) else 0
    received = int((df["delay_ms"] >= 0).sum()) if "delay_ms" in df.columns else len(df)
    if "delay_ms" in df.columns and "receivedOnTime" in df.columns:
        late = int(((df["delay_ms"] >= 0) & (df["receivedOnTime"] == 0)).sum())
    else:
        late = 0
    lost = int((df["delay_ms"] < 0).sum()) if "delay_ms" in df.columns else 0
    delivery = float(received / expected) if expected > 0 else float("nan")
    loss = float(lost / expected) if expected > 0 else float("nan")

    return {
        "mean_effective_error": mean_err,
        "on_time_ratio": on_time,
        "mean_delay_ms": mean_delay,
        "expected_frames": expected,
        "received_frames": received,
        "late_frames": late,
        "lost_frames": lost,
        "delivery_ratio": delivery,
        "loss_ratio": loss,
        "missing_only_lost": missing_only_lost,
        "incomplete_lost": 0,
        "eval_source": "csv_fallback",
    }


def _read_summary_file(path: Path) -> dict | None:
    """Read a per-user .summary CSV generated by XRTrafficReceiver."""
    try:
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
        if row is None:
            return None
        return {
            "mean_effective_error": _to_float(row.get("mean_error")),
            "on_time_ratio": _to_float(row.get("on_time_ratio")),
            "mean_delay_ms": _to_float(row.get("avg_delay_ms")),
            "delivery_ratio": _to_float(row.get("delivery_ratio")),
            "loss_ratio": _to_float(row.get("loss_ratio")),
            "expected_frames": _to_int(row.get("total_frames", 0)),
            "received_frames": _to_int(row.get("received_frames", 0)),
            "late_frames": _to_int(row.get("late_frames", 0)),
            "lost_frames": _to_int(row.get("lost_frames", 0)),
        }
    except Exception as e:
        log.warning(f"Failed to read summary {path}: {e}")
        return None


def _count_missing_only_lost_rows(df: pd.DataFrame) -> int:
    """Count synthetic rows appended by detectLostFrames()."""
    if df is None or df.empty:
        return 0
    required = ["components", "mse", "genTime", "recvTime", "delay_ms"]
    if not all(c in df.columns for c in required):
        return 0
    mask = (
        (df["components"] == 0)
        & (df["mse"] == 0)
        & (df["genTime"] == 0)
        & (df["recvTime"] == 0)
        & (df["delay_ms"] == -1)
    )
    return int(mask.sum())


def _to_int(value, default=0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _to_float(value, default=float("nan")) -> float:
    try:
        return float(value)
    except Exception:
        return default


# ── Worker function (module-level for pickling) ──────────────────────────

def _run_one_sim(
    label: str, cmd: list, run_dir: Path, num_users: int, timeout: int,
) -> tuple:
    """Run one simulation in a subprocess pool worker."""
    run_dir = Path(run_dir)
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
            print(f"  [{label}] FAILED (code {result.returncode}, {elapsed:.0f}s)", flush=True)
            return label, None
        print(f"  [{label}] OK ({elapsed:.0f}s)", flush=True)
        return label, read_user_results(run_dir, num_users)
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT ({timeout}s)", flush=True)
        return label, None
    except Exception as e:
        print(f"  [{label}] ERROR: {e}", flush=True)
        return label, None


# ── Parallel simulation runner ───────────────────────────────────────────

def run_all_sims_parallel(
    num_users: int,
    sim_time: int,
    seed: int,
    video_assignments: list,
    fps_assignments: list,
    server_url: str,
    levels: list,
    max_workers: int | None,
    timeout: int,
) -> tuple:
    """Run model + all static simulations concurrently."""
    jobs = []

    # Model job
    model_run_dir = RESULTS_DIR / "model"
    model_cmd = build_sim_cmd(
        config="XR-DL-RandomCL",
        num_users=num_users, sim_time=sim_time, seed=seed,
        video_assignments=video_assignments, run_dir=model_run_dir,
        selection_mode="model", compression_level=0,
        model_server_url=server_url, fps_assignments=fps_assignments,
    )
    jobs.append(("Model (inline)", model_cmd, model_run_dir))

    # Static jobs
    for cl in levels:
        run_dir = RESULTS_DIR / f"static_{cl}"
        cmd = build_sim_cmd(
            config="XR-DL-RandomCL",
            num_users=num_users, sim_time=sim_time, seed=seed,
            video_assignments=video_assignments, run_dir=run_dir,
            selection_mode="fixed", compression_level=cl,
            fps_assignments=fps_assignments,
        )
        jobs.append((f"Static CL={cl}", cmd, run_dir))

    total = len(jobs)
    effective_workers = max_workers or os.cpu_count() or 1
    print(f"  Dispatching {total} simulations across {effective_workers} workers ...", flush=True)

    results_map = {}
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
            print(f"  Progress: {completed}/{total} done ({elapsed:.0f}s elapsed)", flush=True)

    model_data = results_map.get("Model (inline)")
    static_data = {}
    for cl in levels:
        key = f"Static CL={cl}"
        if results_map.get(key) is not None:
            static_data[cl] = results_map[key]

    return model_data, static_data


# ── Assemble comparison results ──────────────────────────────────────────

def assemble_comparison(
    num_users: int,
    video_assignments: list,
    model_data: dict | None,
    static_data: dict,
    out_path: Path,
) -> pd.DataFrame:
    """Build a comparison CSV using the shared metrics extractor."""
    rows = []

    # Model results
    if model_data:
        model_run_dir = RESULTS_DIR / "model"
        for i in range(num_users):
            if i in model_data:
                metrics = _extract_user_metrics(model_run_dir, i, model_data[i])
                rows.append({
                    "user": i,
                    "video": video_assignments[i],
                    "strategy": "model",
                    "comp_level": "adaptive",
                    **metrics,
                })

    # Static results
    for cl, user_dfs in sorted(static_data.items()):
        static_run_dir = RESULTS_DIR / f"static_{cl}"
        for i in range(num_users):
            if i in user_dfs:
                metrics = _extract_user_metrics(static_run_dir, i, user_dfs[i])
                rows.append({
                    "user": i,
                    "video": video_assignments[i],
                    "strategy": "static",
                    "comp_level": cl,
                    **metrics,
                })

    result_df = pd.DataFrame(rows)
    result_df.to_csv(out_path, index=False)
    return result_df


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare model-adaptive vs static XR compression (parallel)"
    )
    parser.add_argument("--num-users", type=int, default=5, help="Number of UEs (2-10)")
    parser.add_argument("--sim-time", type=int, default=50, help="Simulation time (seconds)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--server-url", default=MODEL_SERVER_URL, help="Model server URL")
    parser.add_argument("--traffic-dir", default=None, help="Path to comparison traffic files")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    parser.add_argument("--timeout", type=int, default=6000, help="Per-sim timeout (seconds)")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Max parallel workers")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    global TRAFFIC_DIR, TRIMMED_DIR, RESULTS_DIR, PCA_FILES

    if args.traffic_dir:
        TRAFFIC_DIR = Path(args.traffic_dir).expanduser().resolve()
    else:
        TRAFFIC_DIR = SCRIPT_DIR.parent / "comparison/traffic_files/pca"

    # Fallback to baseline training traffic if comparison dir doesn't exist
    if not TRAFFIC_DIR.exists():
        fallback = SCRIPT_DIR.parent / "compression/traffic_files/pca"
        if fallback.exists():
            log.warning(f"Comparison traffic dir not found, falling back to {fallback}")
            TRAFFIC_DIR = fallback
        else:
            log.error(f"No traffic files found in '{TRAFFIC_DIR}' or fallback")
            sys.exit(1)

    TRIMMED_DIR = TRAFFIC_DIR
    PCA_FILES = sorted(TRIMMED_DIR.glob(FILE_PREFIX + "*.csv"))

    if not PCA_FILES:
        log.error(f"No traffic files found in {TRIMMED_DIR}!")
        sys.exit(1)

    RESULTS_DIR = SCRIPT_DIR / "comparison_results_pca"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    num_users = args.num_users
    effective_workers = args.max_workers or os.cpu_count() or 1
    total_sims = 1 + len(COMP_LEVELS)

    print("=" * 65)
    print("  Model vs Static Compression Comparison  [PARALLEL]")
    print("=" * 65)
    print(f"  Users:           {num_users}")
    print(f"  Sim time:        {args.sim_time}s")
    print(f"  Seed:            {args.seed}")
    print(f"  Static levels:   {COMP_LEVELS[0]}-{COMP_LEVELS[-1]} (step {COMP_LEVELS[1]-COMP_LEVELS[0]}, {len(COMP_LEVELS)} sims)")
    print(f"  Model server:    {args.server_url}")
    print(f"  Traffic files:   {TRAFFIC_DIR}")
    print(f"  Output dir:      {RESULTS_DIR}")
    print(f"  Workers:         {effective_workers} (running {total_sims} sims in parallel)")

    video_assignments = assign_videos(num_users, args.seed)
    fps_assignments = assign_fps(num_users, args.seed)
    print(f"\n  Video & FPS assignments:")
    for i, v in enumerate(video_assignments):
        print(f"    User {i}: {v}  ({fps_assignments[i]} fps)")

    if args.dry_run:
        print(f"\n[DRY RUN] Would run {total_sims} simulations.")
        return

    # Check model server health
    print(f"\n[0/3] Checking model server ...")
    try:
        r = requests.get(f"{args.server_url}/health", timeout=5)
        r.raise_for_status()
        health = r.json()
        print(f"  Server OK: device={health['device']}, max_users={health.get('max_users_supported', 0)}")
        if num_users > health.get("max_users_supported", 0):
            log.error(f"Server supports up to {health.get('max_users_supported')} users, but {num_users} requested!")
            return
    except Exception as e:
        log.error(f"Cannot reach model server: {e}")
        print("  Start the server with: python model_server.py")
        return

    # Run all simulations
    print(f"\n[1-2/3] Running model + {len(COMP_LEVELS)} static simulations ...")
    t0 = time.time()
    model_data, static_data = run_all_sims_parallel(
        num_users=num_users, sim_time=args.sim_time, seed=args.seed,
        video_assignments=video_assignments, fps_assignments=fps_assignments,
        server_url=args.server_url, levels=COMP_LEVELS,
        max_workers=args.max_workers, timeout=args.timeout,
    )
    wall_time = time.time() - t0
    print(f"\n  All simulations finished in {wall_time:.1f}s")

    if model_data is None:
        log.warning("Model simulation failed.")
    print(f"  Static sims completed: {len(static_data)}/{len(COMP_LEVELS)}")

    # Assemble results
    print(f"\n[3/3] Assembling comparison results ...")
    out_csv = RESULTS_DIR / "comparison.csv"
    result_df = assemble_comparison(num_users, video_assignments, model_data, static_data, out_csv)
    print(f"  Written to: {out_csv}")
    print(f"  Total rows: {len(result_df)}")

    # Summary
    print("\n" + "=" * 65)
    print("  RESULTS SUMMARY")
    print("=" * 65)

    if result_df.empty:
        log.error("No successful simulations!")
        return

    if model_data:
        model_rows = result_df[result_df["strategy"] == "model"]
        model_avg = model_rows["mean_effective_error"].mean()
        print(f"\n  Model (adaptive):  avg effective error = {model_avg:.6f}")

    static_rows = result_df[result_df["strategy"] == "static"]
    print(f"\n  Static levels (avg effective error):")
    for cl in sorted(static_data.keys()):
        cl_rows = static_rows[static_rows["comp_level"] == cl]
        avg_err = cl_rows["mean_effective_error"].mean()
        print(f"    CL={cl:>3d}:  {avg_err:.6f}")

    static_summary = static_rows.groupby("comp_level")["mean_effective_error"].mean().reset_index()
    best_static = static_summary.loc[static_summary["mean_effective_error"].idxmin()]
    print(f"\n  Best static: CL={best_static['comp_level']}, error={best_static['mean_effective_error']:.6f}")

    if model_data:
        improvement = (best_static["mean_effective_error"] - model_avg) / best_static["mean_effective_error"] * 100
        print(f"  Model improvement over best static: {improvement:+.2f}%")

    print(f"\n  Wall-clock time: {wall_time:.1f}s (~{effective_workers}x speedup over serial)")
    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()