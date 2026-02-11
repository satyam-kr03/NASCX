#!/usr/bin/env python3
"""
Per-Frame Dataset Generation for Dynamic Compression Selection

Unlike generate_dataset.py which assigns ONE compression level per user,
this script assigns RANDOM compression levels PER FRAME, enabling the ML
model to learn per-frame compression decisions.

For each simulation run:
  1. Randomly assign compression levels per-frame (not per-user)
  2. Generate adaptive PCA CSVs with varying components per frame
  3. Run the simulation with per-user result CSV output enabled
  4. Parse per-frame results to build training data

The resulting dataset captures the relationship between:
  - Frame complexity (size at max compression = inherent difficulty)
  - Network conditions (CQI, num_users)
  - Compression level chosen
  - Whether the frame was delivered on time

Usage:
    cd /home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr
    python3 generate_per_frame_dataset.py --test        # Quick test
    python3 generate_per_frame_dataset.py --runs 5 -j 8 # Full generation
"""

import os
import sys
import csv
import random
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import re
from multiprocessing import Pool, cpu_count
import shutil

# Configuration
COMPRESSION_LEVELS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
MAX_COMPRESSION = 80  # Used as frame complexity reference
FPS_RATES = [60, 72, 90, 120]
USER_RANGE = range(2, 11)  # 2 to 10 users
DEFAULT_RUNS_PER_CONFIG = 5
DEFAULT_NUM_WORKERS = min(16, cpu_count())
SIMULATION_DIR = Path(__file__).parent
SIMULATION_TIME = 20  # seconds
DATASET_OUTPUT = SIMULATION_DIR / "datasets" / "per_frame_dataset.csv"

# Traffic profile configuration
TRAFFIC_PROFILES = [
    {"file": "traffic_files/traffic_45kb.csv", "mean_kb": 45.0, "std_kb": 24.1, "min_kb": 5.8, "max_kb": 84.2},
    {"file": "traffic_files/traffic_65kb.csv", "mean_kb": 65.0, "std_kb": 34.8, "min_kb": 8.3, "max_kb": 121.7},
    {"file": "traffic_files/traffic_80kb.csv", "mean_kb": 80.0, "std_kb": 42.9, "min_kb": 10.2, "max_kb": 149.8},
    {"file": "traffic_files/traffic_95kb.csv", "mean_kb": 95.0, "std_kb": 50.9, "min_kb": 12.2, "max_kb": 177.8},
    {"file": "traffic_files/traffic_120kb.csv", "mean_kb": 120.0, "std_kb": 64.3, "min_kb": 15.3, "max_kb": 224.7},
]

# Output dataset columns
DATASET_COLUMNS = [
    'run_id', 'num_users', 'user_id', 'fps', 'avg_cqi',
    'frame_number', 'frame_complexity', 'compression_level',
    'compressed_size_bytes', 'mse', 'delay_ms', 'received_on_time'
]


def load_pca_sweep_data(pca_file: Path) -> Dict[int, List[Dict]]:
    """Load PCA sweep data grouped by compression level (components)."""
    data_by_level = {level: [] for level in COMPRESSION_LEVELS}
    
    with open(pca_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            components = int(row['components'])
            if components in data_by_level:
                data_by_level[components].append({
                    'frame': int(row['frame']),
                    'components': components,
                    'mse': float(row['mse']),
                    'size_bytes': int(float(row['size_bytes']))
                })
    
    return data_by_level


def get_frame_complexity_map(data_by_level: Dict[int, List[Dict]]) -> Dict[int, float]:
    """Get frame complexity for each frame (size at max components).
    
    Frame complexity = size_bytes at components=80 (least compressed).
    A larger value means the frame is inherently more complex/difficult.
    """
    complexity_map = {}
    for frame_data in data_by_level[MAX_COMPRESSION]:
        complexity_map[frame_data['frame']] = frame_data['size_bytes']
    return complexity_map


def create_adaptive_pca_file(user_id: int, frame_comp_map: Dict[int, int],
                              data_by_level: Dict[int, List[Dict]],
                              output_dir: Path) -> Path:
    """Create a PCA CSV where each frame has a DIFFERENT compression level.
    
    Args:
        user_id: User index
        frame_comp_map: Dict mapping frame_number -> compression_level
        data_by_level: PCA sweep data grouped by compression level
        output_dir: Directory for output files
    
    Returns:
        Path to the generated CSV file
    """
    output_file = output_dir / f"user_{user_id}_adaptive.csv"
    
    # Build fast lookup: (frame, components) -> row
    frame_lookup = {}
    for level, frames in data_by_level.items():
        for f in frames:
            frame_lookup[(f['frame'], level)] = f
    
    with open(output_file, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(['frame', 'components', 'mse', 'size_bytes'])
        
        for frame_num in sorted(frame_comp_map.keys()):
            comp = frame_comp_map[frame_num]
            key = (frame_num, comp)
            if key in frame_lookup:
                row = frame_lookup[key]
                writer.writerow([row['frame'], row['components'],
                               row['mse'], row['size_bytes']])
    
    return output_file


def calculate_expected_frames(fps: int) -> int:
    """Calculate expected frames based on FPS and simulation time."""
    return fps * SIMULATION_TIME


def run_simulation(num_users: int, per_user_frame_comps: Dict[int, Dict[int, int]],
                   fps_rates: List[int], traffic_profiles: List[Dict],
                   run_id: int, deadline_ms: float = 5.0) -> Dict:
    """Run simulation with per-frame compression and collect per-frame results.
    
    Args:
        num_users: Number of users
        per_user_frame_comps: Dict[user_id -> Dict[frame_number -> compression_level]]
        fps_rates: FPS per user
        traffic_profiles: Traffic profile per user
        run_id: Unique run identifier
        deadline_ms: Delay deadline
    """
    # Create temporary directory for this run
    run_dir = SIMULATION_DIR / f"pf_run_{run_id}_{os.getpid()}"
    run_dir.mkdir(exist_ok=True)
    
    # Generate per-user adaptive PCA files
    user_pca_files = []
    user_data_by_level = {}
    for i in range(num_users):
        traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
        data_by_level = load_pca_sweep_data(traffic_file)
        user_data_by_level[i] = data_by_level
        
        pca_file = create_adaptive_pca_file(i, per_user_frame_comps[i],
                                             data_by_level, run_dir)
        user_pca_files.append(pca_file)
    
    # Build simulation command
    cmd = [
        "simu5g",
        "-r", "0",
        "-m",
        "-u", "Cmdenv",
        "-c", "XR-DL-Dataset",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs={deadline_ms}ms",
    ]
    
    # Per-user settings: PCA file, FPS, expected frames, and result CSV
    result_files = []
    for i in range(num_users):
        fps = fps_rates[i]
        expected_frames = calculate_expected_frames(fps)
        result_csv = run_dir / f"user_{i}_results.csv"
        result_files.append(result_csv)
        
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_pca_files[i]}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].expectedFrames={expected_frames}')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_csv}"')
    
    cmd.append("omnetpp.ini")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SIMULATION_DIR,
            capture_output=True,
            text=True,
            timeout=3000
        )
        
        output = result.stdout + result.stderr
        
        # Parse per-user CQI from stdout
        user_cqis = parse_user_cqis(output, num_users)
        
        # Parse per-frame results from CSV files
        per_frame_results = []
        for i in range(num_users):
            if result_files[i].exists():
                frames = parse_result_csv(result_files[i])
                complexity_map = get_frame_complexity_map(user_data_by_level[i])
                
                for frame in frames:
                    per_frame_results.append({
                        'run_id': run_id,
                        'num_users': num_users,
                        'user_id': i,
                        'fps': fps_rates[i],
                        'avg_cqi': user_cqis.get(i, 0.0),
                        'frame_number': frame['frameNumber'],
                        'frame_complexity': complexity_map.get(frame['frameNumber'], 0),
                        'compression_level': frame['components'],
                        'compressed_size_bytes': frame['sizeBytes'],
                        'mse': frame['mse'],
                        'delay_ms': frame['delay_ms'],
                        'received_on_time': frame['receivedOnTime'],
                    })
        
        return {
            'run_id': run_id,
            'num_users': num_users,
            'per_frame_results': per_frame_results,
            'success': result.returncode == 0 and len(per_frame_results) > 0
        }
    
    except subprocess.TimeoutExpired:
        return {'run_id': run_id, 'num_users': num_users, 'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'run_id': run_id, 'num_users': num_users, 'success': False, 'error': str(e)}
    finally:
        # Cleanup
        try:
            shutil.rmtree(run_dir, ignore_errors=True)
        except:
            pass


def parse_user_cqis(output: str, num_users: int) -> Dict[int, float]:
    """Parse per-user average CQI from simulation stdout."""
    user_cqis = {}
    cqi_pattern = re.compile(
        r"Module:\s+\S+\.ue\[(\d+)\]\.app\[0\].*?Avg DL CQI:\s+([\d.]+)",
        re.DOTALL
    )
    for match in cqi_pattern.finditer(output):
        user_id = int(match.group(1))
        avg_cqi = float(match.group(2))
        user_cqis[user_id] = avg_cqi
    
    # Fill missing with 0
    for i in range(num_users):
        if i not in user_cqis:
            user_cqis[i] = 0.0
    
    return user_cqis


def parse_result_csv(result_file: Path) -> List[Dict]:
    """Parse the per-frame result CSV written by XRTrafficReceiver.
    
    Expected format:
        frameNumber,components,mse,sizeBytes,genTime,recvTime,delay_ms,receivedOnTime,effectiveError,deadline_ms
    """
    frames = []
    try:
        with open(result_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                frame_num = int(row['frameNumber'])
                components = int(row['components'])
                delay = float(row['delay_ms'])
                on_time = int(row['receivedOnTime'])
                
                # Skip lost frames (components=0, delay=-1)
                # They will be handled as "not on time" implicitly
                if components == 0 and delay < 0:
                    frames.append({
                        'frameNumber': frame_num,
                        'components': 0,
                        'mse': 1000.0,
                        'sizeBytes': 0,
                        'delay_ms': -1,
                        'receivedOnTime': 0,
                    })
                    continue
                
                frames.append({
                    'frameNumber': frame_num,
                    'components': components,
                    'mse': float(row['mse']),
                    'sizeBytes': int(float(row['sizeBytes'])),
                    'delay_ms': delay,
                    'receivedOnTime': on_time,
                })
    except Exception as e:
        print(f"    Error parsing {result_file}: {e}")
    
    return frames


def run_worker(task: Tuple) -> Dict:
    """Worker function for parallel execution."""
    run_id, num_users, per_user_frame_comps, fps_rates, traffic_profiles, deadline_ms = task
    return run_simulation(num_users, per_user_frame_comps, fps_rates,
                         traffic_profiles, run_id, deadline_ms)


def save_results(all_results: List[Dict], output_file: Path) -> None:
    """Save per-frame results to CSV file."""
    if not all_results:
        return
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        writer.writerows(all_results)


def generate_dataset(num_runs: int = DEFAULT_RUNS_PER_CONFIG,
                    deadline_ms: float = 5.0,
                    seed: int = 42,
                    save_interval: int = 5,
                    num_workers: int = 1) -> None:
    """Generate per-frame dataset with mixed compression per frame.
    
    For each simulation, every frame gets a randomly assigned compression level.
    This produces per-frame training data that captures the relationship between
    frame complexity, compression choice, and delivery outcome.
    """
    random.seed(seed)
    
    print(f"=" * 60)
    print("PER-FRAME DATASET GENERATION")
    print(f"=" * 60)
    print(f"Runs per user count: {num_runs}")
    print(f"User range: {list(USER_RANGE)}")
    print(f"Compression levels: {COMPRESSION_LEVELS}")
    print(f"FPS rates: {FPS_RATES}")
    print(f"Traffic profiles: {[p['file'] for p in TRAFFIC_PROFILES]}")
    print(f"Deadline: {deadline_ms} ms")
    print(f"Workers: {num_workers}")
    print()
    
    # Pre-generate all tasks
    tasks = []
    run_id = 0
    
    for num_users in USER_RANGE:
        for _ in range(num_runs):
            run_id += 1
            fps_rates = [random.choice(FPS_RATES) for _ in range(num_users)]
            traffic_profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
            
            # For each user, assign random compression PER FRAME
            per_user_frame_comps = {}
            for i in range(num_users):
                traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
                data_by_level = load_pca_sweep_data(traffic_file)
                
                # Get list of frame numbers from max compression level
                frame_numbers = [f['frame'] for f in data_by_level[MAX_COMPRESSION]]
                expected_frames = calculate_expected_frames(fps_rates[i])
                frame_numbers = frame_numbers[:expected_frames]
                
                # Assign random compression to each frame
                frame_comp_map = {
                    fn: random.choice(COMPRESSION_LEVELS) for fn in frame_numbers
                }
                per_user_frame_comps[i] = frame_comp_map
            
            tasks.append((run_id, num_users, per_user_frame_comps, fps_rates,
                         traffic_profiles, deadline_ms))
    
    total_tasks = len(tasks)
    print(f"Total simulation tasks: {total_tasks}")
    print()
    
    all_results = []
    completed = 0
    successful = 0
    failed = 0
    
    if num_workers > 1:
        print(f"Starting parallel execution with {num_workers} workers...")
        with Pool(processes=num_workers) as pool:
            for result in pool.imap_unordered(run_worker, tasks):
                completed += 1
                
                if result.get('success') and 'per_frame_results' in result:
                    successful += 1
                    all_results.extend(result['per_frame_results'])
                else:
                    failed += 1
                
                if completed % save_interval == 0:
                    save_results(all_results, DATASET_OUTPUT)
                    print(f"Progress: {completed}/{total_tasks} ({100*completed/total_tasks:.1f}%) - "
                          f"Success: {successful}, Failed: {failed}, Rows: {len(all_results)}")
    else:
        print("Running in sequential mode...")
        for task in tasks:
            result = run_worker(task)
            completed += 1
            
            if result.get('success') and 'per_frame_results' in result:
                successful += 1
                n_frames = len(result['per_frame_results'])
                all_results.extend(result['per_frame_results'])
                print(f"  Run {completed}/{total_tasks}: {n_frames} per-frame results")
            else:
                failed += 1
                error = result.get('error', 'unknown')
                print(f"  Run {completed}/{total_tasks}: FAILED ({error})")
            
            if completed % save_interval == 0 and all_results:
                save_results(all_results, DATASET_OUTPUT)
                print(f"  [Checkpoint] Saved {len(all_results)} rows")
    
    # Final save
    if all_results:
        save_results(all_results, DATASET_OUTPUT)
        print(f"\n{'=' * 60}")
        print("PER-FRAME DATASET GENERATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total tasks: {total_tasks} (Success: {successful}, Failed: {failed})")
        print(f"Total per-frame rows: {len(all_results)}")
        print(f"Output file: {DATASET_OUTPUT}")
        
        # Print some statistics
        import pandas as pd
        df = pd.DataFrame(all_results)
        print(f"\nDataset Statistics:")
        print(f"  Unique runs:        {df['run_id'].nunique()}")
        print(f"  User range:         {df['num_users'].min()}-{df['num_users'].max()}")
        print(f"  FPS values:         {sorted(df['fps'].unique())}")
        print(f"  Compression levels: {sorted(df['compression_level'].unique())}")
        print(f"  CQI range:          {df['avg_cqi'].min():.2f}-{df['avg_cqi'].max():.2f}")
        print(f"  Frame complexity:   {df['frame_complexity'].min():.0f}-{df['frame_complexity'].max():.0f} bytes")
        print(f"  On-time rate:       {df['received_on_time'].mean()*100:.1f}%")
    else:
        print("\nNo results generated!")


def quick_test():
    """Run a quick test with 3 users and per-frame compression."""
    print("=" * 60)
    print("QUICK TEST: Per-Frame Compression")
    print("=" * 60)
    random.seed(42)
    
    num_users = 3
    fps_rates = [random.choice(FPS_RATES) for _ in range(num_users)]
    traffic_profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
    
    # Assign random compression per frame for each user
    per_user_frame_comps = {}
    for i in range(num_users):
        traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
        data_by_level = load_pca_sweep_data(traffic_file)
        
        frame_numbers = [f['frame'] for f in data_by_level[MAX_COMPRESSION]]
        expected_frames = calculate_expected_frames(fps_rates[i])
        frame_numbers = frame_numbers[:expected_frames]
        
        frame_comp_map = {fn: random.choice(COMPRESSION_LEVELS) for fn in frame_numbers}
        per_user_frame_comps[i] = frame_comp_map
    
    print(f"\nTest configuration ({num_users} users):")
    for i in range(num_users):
        comps = list(per_user_frame_comps[i].values())
        unique_comps = len(set(comps))
        print(f"  User {i}: fps={fps_rates[i]}, traffic={traffic_profiles[i]['file']}, "
              f"unique_compression_levels={unique_comps}")
    
    result = run_simulation(num_users, per_user_frame_comps, fps_rates,
                           traffic_profiles, run_id=999, deadline_ms=5.0)
    
    if result.get('success'):
        frames = result['per_frame_results']
        print(f"\nSuccess! {len(frames)} per-frame results collected")
        
        # Show stats per user
        for i in range(num_users):
            user_frames = [f for f in frames if f['user_id'] == i]
            if user_frames:
                on_time = sum(f['received_on_time'] for f in user_frames)
                avg_mse = sum(f['mse'] for f in user_frames) / len(user_frames)
                comps = [f['compression_level'] for f in user_frames]
                unique_comps = len(set(comps))
                print(f"  User {i}: {len(user_frames)} frames, {on_time} on-time "
                      f"({on_time/len(user_frames)*100:.1f}%), "
                      f"avg_mse={avg_mse:.1f}, CQI={user_frames[0]['avg_cqi']:.1f}, "
                      f"unique_comps={unique_comps}")
        
        # Show first few frame results
        print(f"\n  Sample frames (User 0):")
        user0_frames = [f for f in frames if f['user_id'] == 0][:5]
        for f in user0_frames:
            print(f"    Frame {f['frame_number']}: comp={f['compression_level']}, "
                  f"size={f['compressed_size_bytes']}B, complexity={f['frame_complexity']}B, "
                  f"delay={f['delay_ms']:.2f}ms, on_time={f['received_on_time']}")
    else:
        print(f"\nTest failed! Error: {result.get('error', 'unknown')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate per-frame dataset for dynamic compression ML model"
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_CONFIG,
                       help=f"Runs per user count (default: {DEFAULT_RUNS_PER_CONFIG})")
    parser.add_argument("--deadline", type=float, default=5.0,
                       help="Delay deadline in ms (default: 5.0)")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    parser.add_argument("--save-interval", type=int, default=5,
                       help="Save results every N runs (default: 5)")
    parser.add_argument("--workers", "-j", type=int, default=DEFAULT_NUM_WORKERS,
                       help=f"Number of parallel workers (default: {DEFAULT_NUM_WORKERS})")
    parser.add_argument("--test", action="store_true",
                       help="Run quick test with 3 users")
    
    args = parser.parse_args()
    
    if args.test:
        quick_test()
    else:
        generate_dataset(num_runs=args.runs, deadline_ms=args.deadline,
                        seed=args.seed, save_interval=args.save_interval,
                        num_workers=args.workers)
