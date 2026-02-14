#!/usr/bin/env python3
"""
Surrogate Dataset Generation for XR Semantic Communication.

Methodology:
    For each frame, each user is assigned a RANDOM compression level
    independently. The simulator records the resulting MSE and delay
    for every user. No optimal label is needed.

The NN learns the forward mapping:
    f(cqi_0, fps_0, complexity_0, comp_level_0,
      cqi_1, fps_1, complexity_1, comp_level_1,  ...
      cqi_N, fps_N, complexity_N, comp_level_N)
    -> (mse_0, mse_1, ..., mse_N)

At inference time the trained network is queried across candidate
compression level combinations and the joint assignment that
minimises total MSE is selected.

Output CSV schema (one row = one frame snapshot, all users together):
    frame_number,
    fps_0, avg_cqi_0, frame_complexity_0, compression_level_0, mse_0, delay_ms_0, received_on_time_0,
    fps_1, avg_cqi_1, frame_complexity_1, compression_level_1, mse_1, delay_ms_1, received_on_time_1,
    ...

Usage:
    # Test using existing CSV (no simulator needed)
    python3 generate_surrogate_dataset.py --test --input per_frame_dataset.csv --num-users 3

    # Real simulator run
    python3 generate_surrogate_dataset.py --num-users 3 --runs 1
    python3 generate_surrogate_dataset.py --num-users 5 --runs 3 -j 4
"""

import os
import csv
import random
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import shutil
import uuid
import fcntl
from multiprocessing import Pool, cpu_count
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────

COMPRESSION_LEVELS    = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
MAX_COMPRESSION_LEVEL = 80
FPS_RATES             = [60, 72, 90, 120]
DEFAULT_NUM_USERS     = 3
DEFAULT_RUNS          = 1
DEFAULT_NUM_WORKERS   = min(8, cpu_count())
SIMULATION_DIR        = Path(__file__).parent
SIMULATION_TIME       = 20    # seconds
DEADLINE_MS           = 5.0

TRAFFIC_PROFILES = [
    {"file": "traffic_files/traffic_45kb.csv",  "mean_kb": 45.0},
    {"file": "traffic_files/traffic_65kb.csv",  "mean_kb": 65.0},
    {"file": "traffic_files/traffic_80kb.csv",  "mean_kb": 80.0},
    {"file": "traffic_files/traffic_95kb.csv",  "mean_kb": 95.0},
    {"file": "traffic_files/traffic_120kb.csv", "mean_kb": 120.0},
]

# ── Output schema ─────────────────────────────────────────────────────────────

def build_columns(num_users: int) -> List[str]:
    """Wide schema: one row per frame snapshot containing all users."""
    cols = ['run_id', 'num_users', 'frame_number']
    for u in range(num_users):
        cols += [
            f'fps_{u}',
            f'avg_cqi_{u}',
            f'frame_complexity_{u}',
            f'compression_level_{u}',   # INPUT to NN (the action taken)
            f'mse_{u}',                 # TARGET for NN (what resulted)
            f'delay_ms_{u}',
            f'received_on_time_{u}',
        ]
    return cols

# ── PCA / traffic helpers ─────────────────────────────────────────────────────

def load_pca_data(pca_file: Path) -> Dict[int, List[Dict]]:
    """Load pre-computed PCA sweep data, keyed by compression level."""
    data: Dict[int, List[Dict]] = {lvl: [] for lvl in COMPRESSION_LEVELS}
    with open(pca_file) as f:
        for row in csv.DictReader(f):
            lvl = int(row['components'])
            if lvl in data:
                data[lvl].append({
                    'frame':      int(row['frame']),
                    'mse':        float(row['mse']),
                    'size_bytes': int(float(row['size_bytes'])),
                })
    return data


def frame_complexity_map(pca_data: Dict[int, List[Dict]]) -> Dict[int, int]:
    """
    frame_complexity = byte size at MAX compression level (level 80).
    Represents intrinsic content complexity before any compression decision.
    NOTE: at inference time this must come from the raw uncompressed frame,
    not from running level 80 first.
    """
    return {
        e['frame']: e['size_bytes']
        for e in pca_data.get(MAX_COMPRESSION_LEVEL, [])
    }


def create_pca_file(user_id: int, level: int,
                    pca_data: Dict[int, List[Dict]],
                    out_dir: Path, max_frames: int) -> Path:
    """Write a fixed-level PCA file for one user."""
    path   = out_dir / f"u{user_id}_l{level}.csv"
    frames = sorted(pca_data.get(level, []), key=lambda x: x['frame'])[:max_frames]
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['frame', 'components', 'mse', 'size_bytes'])
        for r in frames:
            w.writerow([r['frame'], level, r['mse'], r['size_bytes']])
    return path


def expected_frames(fps: int) -> int:
    return fps * SIMULATION_TIME

# ── Simulation ────────────────────────────────────────────────────────────────

def parse_result_csv(path: Path) -> Dict[int, Dict]:
    """Parse simulator output into {frame_number: outcome_dict}."""
    results = {}
    if not path.exists():
        return results
    try:
        with open(path) as f:
            for row in csv.DictReader(f):
                fn    = int(row['frameNumber'])
                delay = float(row['delay_ms'])
                # Use effectiveError column which contains data-driven penalty
                # for lost/late frames, or actual MSE for on-time frames
                effective_error = float(row.get('effectiveError', row.get('mse', 1000.0)))
                results[fn] = {
                    'mse':              effective_error,
                    'delay_ms':         delay,
                    'received_on_time': int(row['receivedOnTime']),
                }
    except Exception as e:
        print(f"  Warning: could not parse {path}: {e}")
    return results


def read_cqi(summary_path: Path) -> float:
    try:
        if summary_path.exists():
            with open(summary_path) as f:
                for row in csv.DictReader(f):
                    return float(row.get('avg_cqi', 0.0))
    except Exception:
        pass
    return 0.0


def run_one_simulation(run_dir: Path, num_users: int, fps_rates: List[int],
                       pca_caches: Dict, compression_levels: List[int],
                       deadline_ms: float, traffic_profiles: List[Dict]) -> Tuple[bool, Dict, Dict]:
    """
    Run simulator once with each user fixed to their assigned compression level.
    Returns (success, {user_id: {frame_num: outcome}}, {user_id: avg_cqi}).
    """
    result_files = []
    cmd = [
        "simu5g", "-r", "0", "-m", "-u", "Cmdenv",
        "-c", "XR-DL-Dataset",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs={deadline_ms}ms",
    ]

    for i in range(num_users):
        level      = compression_levels[i]
        max_frames = min(expected_frames(fps_rates[i]),
                         len(pca_caches[i].get(level, [])))
        pca_file   = create_pca_file(i, level, pca_caches[i], run_dir, max_frames)
        res_file   = run_dir / f"u{i}_result.csv"
        result_files.append(res_file)

        # Use minimum compression level (most aggressive) for penalty calculation
        min_components = min(COMPRESSION_LEVELS)
        # Use the absolute path to the traffic file for this user
        traffic_file_path = SIMULATION_DIR / traffic_profiles[i]['file']
        
        cmd += [
            f'--*.server.app[{i}].pcaFile="{pca_file}"',
            f'--*.server.app[{i}].fps={fps_rates[i]}',
            f'--*.ue[{i}].app[0].expectedFrames={max_frames}',
            f'--*.ue[{i}].app[0].resultFile="{res_file}"',
            f'--*.ue[{i}].app[0].pcaFile="{traffic_file_path}"',
            f'--*.ue[{i}].app[0].minComponents={min_components}',
        ]
    cmd.append("omnetpp.ini")

    try:
        proc = subprocess.run(cmd, cwd=SIMULATION_DIR,
                              capture_output=True, text=True, timeout=3000)
    except subprocess.TimeoutExpired:
        return False, {}, {}

    if proc.returncode != 0:
        return False, {}, {}

    frame_results, cqis = {}, {}
    for i, res_file in enumerate(result_files):
        cqis[i]          = read_cqi(Path(str(res_file) + ".summary"))
        frame_results[i] = parse_result_csv(res_file)

    return True, frame_results, cqis

# ── Scenario worker ───────────────────────────────────────────────────────────

def run_scenario_task(task: Tuple) -> Dict:
    """
    One scenario = one simulation run with randomly assigned:
      - fps per user
      - traffic profile per user
      - compression level per user (one fixed value for the whole run)

    Why one fixed level per user for the whole run instead of per-frame:
        The simulator processes all frames in one call with a fixed PCA file
        per user. True per-frame random assignment would require one simulator
        call per frame (very expensive). As a practical compromise, the level
        is fixed per user per run, but randomized across runs — over many runs
        this samples the joint (state, action) space broadly enough for the
        surrogate to learn the MSE landscape.

        If your Simu5G build supports per-frame level switching via the PCA
        file, you can remove this constraint and assign truly per-frame random
        levels, which is strictly better.
    """
    run_id, num_users, fps_rates, traffic_profiles, deadline_ms, run_dir_base = task

    run_dir = run_dir_base / f"run_{run_id}_{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Load PCA data
        pca_caches, complexity_maps = {}, {}
        for i in range(num_users):
            traffic_file       = SIMULATION_DIR / traffic_profiles[i]['file']
            pca_caches[i]      = load_pca_data(traffic_file)
            complexity_maps[i] = frame_complexity_map(pca_caches[i])

        # Assign one random compression level per user for this run
        compression_levels = [random.choice(COMPRESSION_LEVELS) for _ in range(num_users)]

        success, frame_results, cqis = run_one_simulation(
            run_dir, num_users, fps_rates,
            pca_caches, compression_levels, deadline_ms, traffic_profiles
        )

        if not success:
            print(f"  [Run {run_id}] Simulation failed.")
            return {'success': False, 'error': 'simulation failed'}

        # Find frames present for ALL users
        per_user_frame_sets = [set(frame_results[i].keys()) for i in range(num_users)]
        common_frames = sorted(set.intersection(*per_user_frame_sets))

        rows = []
        for fn in common_frames:
            row: Dict = {'run_id': run_id, 'num_users': num_users, 'frame_number': fn}
            for i in range(num_users):
                outcome = frame_results[i].get(fn,
                          {'mse': 1000.0, 'delay_ms': -1.0, 'received_on_time': 0})
                row[f'fps_{i}']               = fps_rates[i]
                row[f'avg_cqi_{i}']           = cqis.get(i, 0.0)
                row[f'frame_complexity_{i}']  = complexity_maps[i].get(fn, 0)
                row[f'compression_level_{i}'] = compression_levels[i]
                row[f'mse_{i}']               = outcome['mse']
                row[f'delay_ms_{i}']          = outcome['delay_ms']
                row[f'received_on_time_{i}']  = outcome['received_on_time']
            rows.append(row)

        print(f"  [Run {run_id}] {len(rows)} frame snapshots. "
              f"Levels: {compression_levels}, FPS: {fps_rates}")
        return {'success': True, 'data': rows, 'count': len(rows), 'num_users': num_users}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {'success': False, 'error': str(e)}
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

# ── I/O ───────────────────────────────────────────────────────────────────────

def save_results(rows: List[Dict], output_file: Path, num_users: int) -> None:
    """Append rows to CSV. Process-safe via flock."""
    if not rows:
        return
    columns = build_columns(num_users)
    with open(output_file, 'a', newline='') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            writer = csv.DictWriter(f, fieldnames=columns)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerows(rows)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

# ── Test mode (pivot existing CSV, no simulator) ──────────────────────────────

def test_from_existing_csv(input_csv: Path, num_users: int, output_file: Path) -> None:
    """
    Pivot an existing per-row CSV into the wide surrogate format.
    No simulator needed — useful for verifying schema before a real run.
    """
    import pandas as pd

    print(f"[TEST] Loading {input_csv} ...")
    df = pd.read_csv(input_csv)

    sub = df[df['num_users'] == num_users]
    if sub.empty:
        print(f"[TEST] No data for num_users={num_users}"); return

    run_id = int(sub['run_id'].iloc[0])
    sub    = sub[sub['run_id'] == run_id].copy()
    print(f"[TEST] run_id={run_id}, num_users={num_users}, "
          f"{sub['frame_number'].nunique()} unique frames")

    # Keep only frames where every user has a record
    counts        = sub.groupby('frame_number')['user_id'].nunique()
    complete      = counts[counts == num_users].index
    sub           = sub[sub['frame_number'].isin(complete)]
    print(f"[TEST] {len(complete)} complete frames")

    rows = []
    for fn, grp in sub.groupby('frame_number'):
        grp = grp.set_index('user_id')
        row: Dict = {'run_id': run_id, 'num_users': num_users, 'frame_number': fn}
        for i in range(num_users):
            if i not in grp.index: continue
            u = grp.loc[i]
            row[f'fps_{i}']               = u['fps']
            row[f'avg_cqi_{i}']           = u['avg_cqi']
            row[f'frame_complexity_{i}']  = u['frame_complexity']
            row[f'compression_level_{i}'] = u['compression_level']
            row[f'mse_{i}']               = u['mse']
            row[f'delay_ms_{i}']          = u['delay_ms']
            row[f'received_on_time_{i}']  = u['received_on_time']
        rows.append(row)

    if output_file.exists():
        output_file.unlink()
    save_results(rows, output_file, num_users)

    out = pd.read_csv(output_file)
    print(f"[TEST] Saved {len(out)} rows → {output_file}")
    print(f"[TEST] Columns ({len(out.columns)}): {list(out.columns)}")
    print(f"\n[TEST] Sample (3 rows):\n{out.head(3).to_string()}")

# ── Main ──────────────────────────────────────────────────────────────────────

def generate(num_users: int, num_runs: int, seed: int,
             num_workers: int, output_file: Path) -> None:
    random.seed(seed)

    if output_file.exists():
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    run_dir_base = SIMULATION_DIR / "temp_surrogate"
    run_dir_base.mkdir(exist_ok=True)

    tasks = []
    for run_id in range(1, num_runs + 1):
        fps_rates        = [random.choice(FPS_RATES)        for _ in range(num_users)]
        traffic_profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
        tasks.append((run_id, num_users, fps_rates, traffic_profiles,
                      DEADLINE_MS, run_dir_base))

    print("=" * 60)
    print(f"SURROGATE DATASET GENERATION")
    print(f"  num_users : {num_users}  (input dim = {num_users * 4})")
    print(f"  output dim: {num_users}  (one MSE per user)")
    print(f"  runs      : {num_runs}")
    print(f"  workers   : {num_workers}")
    print(f"  output    : {output_file}")
    print("=" * 60)

    completed, total = 0, 0
    runner = Pool(processes=num_workers).imap_unordered if num_workers > 1 else map

    if num_workers > 1:
        with Pool(processes=num_workers) as pool:
            for result in pool.imap_unordered(run_scenario_task, tasks):
                completed += 1
                if result['success'] and result.get('data'):
                    save_results(result['data'], output_file, num_users)
                    total += result['count']
                    print(f"[{completed}/{num_runs}] +{result['count']} rows. Total: {total}")
                else:
                    print(f"[{completed}/{num_runs}] FAILED: {result.get('error')}")
    else:
        for task in tasks:
            result = run_scenario_task(task)
            completed += 1
            if result['success'] and result.get('data'):
                save_results(result['data'], output_file, num_users)
                total += result['count']
                print(f"[{completed}/{num_runs}] +{result['count']} rows. Total: {total}")
            else:
                print(f"[{completed}/{num_runs}] FAILED: {result.get('error')}")

    shutil.rmtree(run_dir_base, ignore_errors=True)
    print(f"\nDone. {total} frame snapshots → {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-users", type=int, default=DEFAULT_NUM_USERS,
                        help=f"Users in cell (default: {DEFAULT_NUM_USERS})")
    parser.add_argument("--runs",      type=int, default=DEFAULT_RUNS,
                        help=f"Simulation runs (default: {DEFAULT_RUNS})")
    parser.add_argument("--seed",      type=int, default=42)
    parser.add_argument("--workers",   "-j", type=int, default=1,
                        help="Parallel workers (default: 1 for safety)")
    parser.add_argument("--output",    type=Path, default=None,
                        help="Output CSV (default: datasets/surrogate_n<N>.csv)")
    parser.add_argument("--test",      action="store_true",
                        help="Pivot existing CSV to verify schema (no simulator)")
    parser.add_argument("--input",     type=Path, default=None,
                        help="Existing CSV for --test mode")
    args = parser.parse_args()

    out = args.output or Path(f"datasets/surrogate_n{args.num_users}.csv")

    if args.test:
        if not args.input:
            parser.error("--test requires --input <csv>")
        test_from_existing_csv(args.input, args.num_users, out)
    else:
        generate(args.num_users, args.runs, args.seed, args.workers, out)