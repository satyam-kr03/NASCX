#!/usr/bin/env python3
"""
Dataset Generation for Optimal Compression Selection

This script runs batch Simu5G simulations with varying:
- Number of users (2-10)
- Random compression levels per user (5, 10, 15, ..., 80)

The generated dataset captures the relationship between network conditions
and compression outcomes for training an ML model.

Supports parallel execution using multiprocessing for faster dataset generation.
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
from functools import partial
import tempfile
import shutil

# Configuration
COMPRESSION_LEVELS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
USER_RANGE = range(5, 11)  # 5 to 10 users
DEFAULT_RUNS_PER_CONFIG = 10
DEFAULT_NUM_WORKERS = min(16, cpu_count())  # Default to 16 or available cores
SIMULATION_DIR = Path(__file__).parent
PCA_SWEEP_FILE = SIMULATION_DIR / "pca_sweep_summary_scaled.csv"
DATASET_OUTPUT = SIMULATION_DIR / "compression_dataset.csv"


def load_pca_sweep_data() -> Dict[int, List[Dict]]:
    """Load PCA sweep data grouped by compression level (components)."""
    data_by_level = {level: [] for level in COMPRESSION_LEVELS}
    
    with open(PCA_SWEEP_FILE, 'r') as f:
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


def create_user_pca_file(user_id: int, compression_level: int, 
                         data_by_level: Dict[int, List[Dict]],
                         output_dir: Path) -> Path:
    """Create a PCA CSV file for a specific user with fixed compression level."""
    output_file = output_dir / f"user_{user_id}_comp_{compression_level}.csv"
    
    frames = data_by_level[compression_level]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'components', 'mse', 'size_bytes'])
        for frame in frames:
            writer.writerow([frame['frame'], frame['components'], 
                           frame['mse'], frame['size_bytes']])
    
    return output_file


def run_simulation(num_users: int, compression_levels: List[int], 
                   run_id: int, deadline_ms: float = 5.0) -> Dict:
    """Run a single simulation and return results."""
    
    # Create temporary directory for this run using unique process-safe name
    run_dir = SIMULATION_DIR / f"run_temp_{run_id}_{os.getpid()}"
    run_dir.mkdir(exist_ok=True)
    
    # Load PCA data
    data_by_level = load_pca_sweep_data()
    
    # Generate per-user PCA files
    user_files = []
    for i, comp_level in enumerate(compression_levels[:num_users]):
        user_file = create_user_pca_file(i, comp_level, data_by_level, run_dir)
        user_files.append(user_file)
    
    # Build simulation command
    cmd = [
        "simu5g",
        "-r", "0",
        "-m",
        "-u", "Cmdenv",
        "-c", "XR-DL-Dataset",  # Uses mobility for CQI variation
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs={deadline_ms}ms",
    ]
    
    # Add per-user PCA file paths (need quotes around paths containing dots)
    for i, user_file in enumerate(user_files):
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_file}"')
    
    cmd.append("omnetpp.ini")
    
    # Only print in non-parallel mode (controlled by caller)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SIMULATION_DIR,
            capture_output=True,
            text=True,
            timeout=3000  # 50 minute timeout
        )
        
        # Parse output for results
        output = result.stdout + result.stderr
        
        # Extract per-user results from output
        user_results = parse_simulation_output(output, num_users, compression_levels)
        
        return {
            'run_id': run_id,
            'num_users': num_users,
            'compression_levels': compression_levels[:num_users],
            'user_results': user_results,
            'success': result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        return {'run_id': run_id, 'num_users': num_users, 'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'run_id': run_id, 'num_users': num_users, 'success': False, 'error': str(e)}
    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(run_dir, ignore_errors=True)
        except:
            pass


def parse_simulation_output(output: str, num_users: int, 
                           compression_levels: List[int]) -> List[Dict]:
    """Parse simulation output to extract per-user metrics."""
    user_results = []
    
    # Pattern to match QoE summary blocks (updated to include CQI)
    qoe_pattern = re.compile(
        r"Module:\s+\S+\.ue\[(\d+)\]\.app\[0\].*?"
        r"Total frames:\s+(\d+).*?"
        r"On-time frames:\s+(\d+).*?"
        r"Avg Delay:\s+([\d.]+)\s+ms.*?"
        r"Delay Reliability:\s+([\d.]+)%.*?"
        r"User Satisfied:\s+(YES|NO).*?"
        r"Avg DL CQI:\s+([\d.]+)",
        re.DOTALL
    )
    
    # Also try to extract MSE info
    mse_pattern = re.compile(
        r"Module:\s+\S+\.ue\[(\d+)\]\.app\[0\].*?"
        r"Mean Error \(QoE\):\s+([\d.e+-]+)",
        re.DOTALL
    )
    
    for match in qoe_pattern.finditer(output):
        user_id = int(match.group(1))
        total_frames = int(match.group(2))
        on_time_frames = int(match.group(3))
        avg_delay = float(match.group(4))
        delay_reliability = float(match.group(5)) / 100.0
        satisfied = match.group(6) == "YES"
        avg_cqi = float(match.group(7))
        
        # Get compression level for this user
        comp_level = compression_levels[user_id] if user_id < len(compression_levels) else 0
        
        # Try to extract MSE
        avg_mse = 0.0
        for mse_match in mse_pattern.finditer(output):
            if int(mse_match.group(1)) == user_id:
                avg_mse = float(mse_match.group(2))
                break
        
        user_results.append({
            'user_id': user_id,
            'compression_level': comp_level,
            'total_frames': total_frames,
            'on_time_frames': on_time_frames,
            'avg_delay_ms': avg_delay,
            'delay_reliability': delay_reliability,
            'user_satisfied': 1 if satisfied else 0,
            'avg_mse': avg_mse,
            'avg_cqi': avg_cqi
        })
    
    return user_results


def save_results(all_results: List[Dict], output_file: Path) -> None:
    """Save results to CSV file."""
    if not all_results:
        return
    
    fieldnames = ['run_id', 'num_users', 'user_id', 'compression_level',
                  'total_frames', 'on_time_frames', 'avg_delay_ms',
                  'delay_reliability', 'user_satisfied', 'avg_mse', 'avg_cqi']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)


def run_simulation_worker(task: Tuple[int, int, List[int], float]) -> Dict:
    """Worker function for parallel execution.
    
    Args:
        task: Tuple of (run_id, num_users, compression_levels, deadline_ms)
    
    Returns:
        Simulation result dictionary
    """
    run_id, num_users, compression_levels, deadline_ms = task
    return run_simulation(num_users, compression_levels, run_id, deadline_ms)


def generate_dataset(num_runs: int = DEFAULT_RUNS_PER_CONFIG,
                    deadline_ms: float = 5.0,
                    seed: int = 42,
                    save_interval: int = 5,
                    num_workers: int = 1) -> None:
    """Generate the complete dataset.
    
    Args:
        num_runs: Number of runs per user count
        deadline_ms: Delay deadline in ms
        seed: Random seed
        save_interval: Save results to disk every N completed tasks (default: 5)
        num_workers: Number of parallel workers (default: 1 for sequential)
    """
    random.seed(seed)
    
    print(f"Generating dataset with {num_runs} runs per user count")
    print(f"User range: {list(USER_RANGE)}")
    print(f"Compression levels: {COMPRESSION_LEVELS}")
    print(f"Deadline: {deadline_ms} ms")
    print(f"Workers: {num_workers}")
    print(f"Save interval: every {save_interval} completed tasks")
    print()
    
    # Pre-generate all tasks
    tasks = []
    run_id = 0
    for num_users in USER_RANGE:
        for _ in range(num_runs):
            run_id += 1
            compression_levels = [random.choice(COMPRESSION_LEVELS) 
                                 for _ in range(num_users)]
            tasks.append((run_id, num_users, compression_levels, deadline_ms))
    
    total_tasks = len(tasks)
    print(f"Total simulation tasks: {total_tasks}")
    print()
    
    all_results = []
    completed = 0
    successful = 0
    failed = 0
    
    if num_workers > 1:
        # Parallel execution
        print(f"Starting parallel execution with {num_workers} workers...")
        with Pool(processes=num_workers) as pool:
            for result in pool.imap_unordered(run_simulation_worker, tasks):
                completed += 1
                
                if result['success'] and 'user_results' in result:
                    successful += 1
                    for user_result in result['user_results']:
                        row = {
                            'run_id': result['run_id'],
                            'num_users': result['num_users'],
                            **user_result
                        }
                        all_results.append(row)
                else:
                    failed += 1
                
                # Progress update
                if completed % save_interval == 0:
                    save_results(all_results, DATASET_OUTPUT)
                    print(f"Progress: {completed}/{total_tasks} ({100*completed/total_tasks:.1f}%) - "
                          f"Success: {successful}, Failed: {failed}, Rows: {len(all_results)}")
    else:
        # Sequential execution (original behavior)
        print("Running in sequential mode...")
        for task in tasks:
            result = run_simulation_worker(task)
            completed += 1
            
            if result['success'] and 'user_results' in result:
                successful += 1
                for user_result in result['user_results']:
                    row = {
                        'run_id': result['run_id'],
                        'num_users': result['num_users'],
                        **user_result
                    }
                    all_results.append(row)
                print(f"  Run {completed}/{total_tasks}: {len(result['user_results'])} user results")
            else:
                failed += 1
                print(f"  Run {completed}/{total_tasks}: FAILED")
            
            # Periodically save results
            if completed % save_interval == 0 and all_results:
                save_results(all_results, DATASET_OUTPUT)
                print(f"  [Checkpoint] Saved {len(all_results)} rows")
    
    # Final save
    if all_results:
        save_results(all_results, DATASET_OUTPUT)
        print(f"\n=== Dataset Generation Complete ===")
        print(f"Total tasks: {total_tasks} (Success: {successful}, Failed: {failed})")
        print(f"Total rows: {len(all_results)}")
        print(f"Output file: {DATASET_OUTPUT}")
    else:
        print("\nNo results generated!")


def quick_test():
    """Run a quick test with 3 users."""
    print("=== Quick Test Mode ===")
    random.seed(42)
    
    num_users = 3
    compression_levels = [random.choice(COMPRESSION_LEVELS) for _ in range(num_users)]
    
    print(f"Testing {num_users} users with compression levels: {compression_levels}")
    
    result = run_simulation(num_users, compression_levels, run_id=999, deadline_ms=5.0)
    
    if result['success']:
        print("\nResults:")
        for user in result.get('user_results', []):
            print(f"  User {user['user_id']}: comp={user['compression_level']}, "
                  f"delay={user['avg_delay_ms']:.2f}ms, "
                  f"reliability={user['delay_reliability']*100:.1f}%, "
                  f"CQI={user.get('avg_cqi', 0):.1f}, "
                  f"satisfied={user['user_satisfied']}")
    else:
        print("Test failed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate dataset for compression selection ML")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_CONFIG,
                       help=f"Number of runs per user count (default: {DEFAULT_RUNS_PER_CONFIG})")
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
