#!/usr/bin/env python3
"""
Comparison Study: Random vs ML-Guided Compression Selection

This script runs simulations comparing:
1. Random compression selection (baseline)
2. ML-guided compression selection (using FastAPI model server)

The goal is to demonstrate that ML-guided selection achieves better QoE.

Usage:
    # Start model server first:
    python3 model_server.py &
    
    # Run comparison (in opp_shell.sh environment):
    python3 run_comparison.py --runs 10
"""

import os
import sys
import csv
import random
import subprocess
import argparse
import requests
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Configuration
COMPRESSION_LEVELS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
USER_RANGE = range(2, 11)  # 2 to 10 users
DEFAULT_RUNS = 10
SIMULATION_DIR = Path(__file__).parent
PCA_FILE = SIMULATION_DIR / "pca_sweep_summary_scaled.csv"
MODEL_SERVER_URL = "http://localhost:8000"

# Output files
RESULTS_DIR = SIMULATION_DIR / "comparison_results"
MAX_WORKERS = 32  # Number of parallel workers (matching available cores)


def setup_simu5g_env():
    """Set up simu5g environment variables automatically.
    
    This replicates what '. setenv' does from the simu5g root directory.
    """
    # Find simu5g root by traversing up from SIMULATION_DIR
    # SIMULATION_DIR is simu5g-1.3.0/simulations/NR/xr, so root is 3 levels up
    simu5g_root = SIMULATION_DIR.parent.parent.parent.resolve()
    
    # Verify this looks like a simu5g root directory
    simu5g_bin = simu5g_root / "bin" / "simu5g"
    if not simu5g_bin.exists():
        print(f"WARNING: Could not find simu5g binary at {simu5g_bin}")
        print("         Make sure simu5g is built, or run from opp_shell.sh environment")
        return False
    
    # Set environment variables (equivalent to setenv script)
    os.environ["SIMU5G_ROOT"] = str(simu5g_root)
    
    # Prepend bin directory to PATH
    bin_dir = str(simu5g_root / "bin")
    current_path = os.environ.get("PATH", "")
    if bin_dir not in current_path:
        os.environ["PATH"] = f"{bin_dir}:{current_path}"
    
    # Add images to OMNETPP_IMAGE_PATH
    images_dir = str(simu5g_root / "images")
    current_image_path = os.environ.get("OMNETPP_IMAGE_PATH", "")
    if images_dir not in current_image_path:
        os.environ["OMNETPP_IMAGE_PATH"] = f"{current_image_path}:{images_dir}" if current_image_path else images_dir
    
    print(f"Simu5G environment configured (root: {simu5g_root})")
    return True


# Auto-setup environment when module loads
setup_simu5g_env()


def load_pca_data() -> Dict[int, List[Dict]]:
    """Load PCA sweep data grouped by compression level."""
    data_by_level = {level: [] for level in COMPRESSION_LEVELS}
    
    with open(PCA_FILE, 'r') as f:
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
                         data_by_level: Dict, output_dir: Path) -> Path:
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


def query_model_server(num_users: int, avg_cqi: float = 14.5) -> int:
    """Query the FastAPI model server for optimal compression level."""
    try:
        response = requests.post(
            f"{MODEL_SERVER_URL}/predict",
            json={"num_users": num_users, "avg_cqi": avg_cqi},
            timeout=5000
        )
        if response.status_code == 200:
            return response.json()["optimal_compression"]
        else:
            print(f"  Model server error: {response.status_code}")
            return random.choice(COMPRESSION_LEVELS)  # Fallback to random
    except requests.exceptions.RequestException as e:
        print(f"  Model server connection error: {e}")
        return random.choice(COMPRESSION_LEVELS)  # Fallback to random


def run_cqi_warmup(num_users: int, warmup_frames: int = 50, seed: int = 42) -> Dict[int, float]:
    """Run a short warmup simulation to collect actual CQI values for each user.
    
    Args:
        num_users: Number of users in the cell
        warmup_frames: Number of frames to run for warmup (default 50)
        seed: Random seed for compression selection
        
    Returns:
        Dict mapping user_id to their average CQI value
    """
    random.seed(seed)
    
    # Create temporary directory for warmup
    run_dir = SIMULATION_DIR / f"warmup_{num_users}_{seed}"
    run_dir.mkdir(exist_ok=True)
    
    # Load PCA data
    data_by_level = load_pca_data()
    
    # Use random compression for warmup
    compression_levels = [random.choice(COMPRESSION_LEVELS) for _ in range(num_users)]
    
    # Generate per-user PCA files
    user_files = []
    for i, comp_level in enumerate(compression_levels):
        user_file = create_user_pca_file(i, comp_level, data_by_level, run_dir)
        user_files.append(user_file)
    
    # Build simulation command with reduced frame count
    cmd = [
        "simu5g",
        "-r", "0",
        "-m",
        "-u", "Cmdenv",
        "-c", "XR-DL-Dataset",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs=5ms",
        f"--*.ue[*].app[0].expectedFrames={warmup_frames}",
    ]
    
    # Add per-user PCA file paths
    for i, user_file in enumerate(user_files):
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_file}"')
    
    cmd.append("omnetpp.ini")
    
    user_cqis = {}
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SIMULATION_DIR,
            capture_output=True,
            text=True,
            timeout=120000  # Shorter timeout for warmup
        )
        
        output = result.stdout + result.stderr
        
        # Parse CQI values from output
        cqi_pattern = re.compile(
            r"Module:\s+\S+\.ue\[(\d+)\]\.app\[0\].*?Avg DL CQI:\s+([\d.]+)",
            re.DOTALL
        )
        
        for match in cqi_pattern.finditer(output):
            user_id = int(match.group(1))
            avg_cqi = float(match.group(2))
            user_cqis[user_id] = avg_cqi
        
        print(f"  Warmup complete: collected CQI for {len(user_cqis)} users: {user_cqis}")
        
    except subprocess.TimeoutExpired:
        print(f"  Warmup timeout, using default CQI values")
    except Exception as e:
        print(f"  Warmup error: {e}")
    finally:
        # Cleanup temp files
        for f in run_dir.glob("*.csv"):
            f.unlink()
        try:
            run_dir.rmdir()
        except:
            pass
    
    # Fill in missing users with default CQI
    for i in range(num_users):
        if i not in user_cqis:
            user_cqis[i] = 14.0  # Default fallback
    
    return user_cqis


def get_compression_levels(mode: str, num_users: int, seed: int, 
                           user_cqis: Optional[Dict[int, float]] = None) -> List[int]:
    """Get compression levels based on selection mode.
    
    Args:
        mode: 'random' or 'ml'
        num_users: Number of users
        seed: Random seed
        user_cqis: Optional dict of per-user CQI values (for ML mode with actual CQI)
    """
    random.seed(seed)
    
    if mode == "random":
        # Random selection for each user
        return [random.choice(COMPRESSION_LEVELS) for _ in range(num_users)]
    elif mode == "ml":
        # ML-guided: per-user compression based on their actual CQI
        compressions = []
        for user_id in range(num_users):
            if user_cqis and user_id in user_cqis:
                cqi = user_cqis[user_id]
            else:
                cqi = 14.0  # Default fallback
            
            optimal = query_model_server(num_users, avg_cqi=cqi)
            compressions.append(optimal)
        
        return compressions
    else:
        raise ValueError(f"Unknown mode: {mode}")


def run_simulation(num_users: int, compression_levels: List[int], 
                   run_id: int, mode: str) -> Optional[Dict]:
    """Run a single simulation and return results."""
    
    # Create temporary directory for this run
    run_dir = SIMULATION_DIR / f"run_{mode}_{run_id}"
    run_dir.mkdir(exist_ok=True)
    
    # Load PCA data
    data_by_level = load_pca_data()
    
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
        "-c", "XR-DL-Dataset",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs=5ms",
    ]
    
    # Add per-user PCA file paths
    for i, user_file in enumerate(user_files):
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_file}"')
    
    cmd.append("omnetpp.ini")
    
    print(f"  Mode={mode}, Users={num_users}, Compression={compression_levels[:num_users]}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SIMULATION_DIR,
            capture_output=True,
            text=True,
            timeout=30000
        )
        
        output = result.stdout + result.stderr
        user_results = parse_simulation_output(output, num_users, compression_levels)
        
        return {
            'run_id': run_id,
            'mode': mode,
            'num_users': num_users,
            'compression_levels': compression_levels[:num_users],
            'user_results': user_results,
            'success': result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        print(f"    Timeout for run {run_id}")
        return None
    except Exception as e:
        print(f"    Error: {e}")
        return None
    finally:
        # Cleanup temp files
        for f in run_dir.glob("*.csv"):
            f.unlink()
        try:
            run_dir.rmdir()
        except:
            pass


def parse_simulation_output(output: str, num_users: int, 
                           compression_levels: List[int]) -> List[Dict]:
    """Parse simulation output to extract per-user metrics."""
    user_results = []
    
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
        
        comp_level = compression_levels[user_id] if user_id < len(compression_levels) else 0
        
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


def run_single_task(task: Dict) -> Optional[Dict]:
    """Worker function to run a single simulation task.
    
    This function is designed to be called by ProcessPoolExecutor.
    For ML mode, runs a warmup simulation first to collect actual CQI values.
    """
    mode = task['mode']
    num_users = task['num_users']
    run_id = task['run_id']
    run_seed = task['run_seed']
    
    # For ML mode, run CQI warmup first
    user_cqis = None
    if mode == "ml":
        print(f"  Running CQI warmup for {num_users} users...")
        user_cqis = run_cqi_warmup(num_users, warmup_frames=50, seed=run_seed)
    
    compression_levels = get_compression_levels(mode, num_users, run_seed, user_cqis=user_cqis)
    result = run_simulation(num_users, compression_levels, run_id, mode)
    
    if result and result.get('success') and result.get('user_results'):
        rows = []
        for user_result in result['user_results']:
            row = {
                'mode': mode,
                'run_id': run_id,
                'num_users': num_users,
                **user_result
            }
            rows.append(row)
        return {'success': True, 'rows': rows, 'task': task}
    return {'success': False, 'rows': [], 'task': task}


def run_comparison_study(num_runs: int = DEFAULT_RUNS, seed: int = 42):
    """Run the full comparison study with parallel execution."""
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    all_results = []
    
    # Check if model server is running
    try:
        health = requests.get(f"{MODEL_SERVER_URL}/health", timeout=2000)
        if health.status_code != 200:
            print("WARNING: Model server not healthy, ML mode will fallback to random")
    except:
        print("WARNING: Model server not running, ML mode will fallback to random")
        print("         Start with: python3 model_server.py &")
    
    # Build list of all tasks to run
    tasks = []
    run_id = 0
    for mode in ["random", "ml"]:
        for num_users in USER_RANGE:
            for run_idx in range(num_runs):
                run_id += 1
                run_seed = seed + run_id + (1000 if mode == "ml" else 0)
                tasks.append({
                    'mode': mode,
                    'num_users': num_users,
                    'run_id': run_id,
                    'run_idx': run_idx,
                    'run_seed': run_seed
                })
    
    total_tasks = len(tasks)
    print(f"\n{'='*50}")
    print(f"Running {total_tasks} simulations with {MAX_WORKERS} parallel workers")
    print(f"{'='*50}")
    
    completed = 0
    failed = 0
    
    # Run tasks in parallel using ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_task = {executor.submit(run_single_task, task): task for task in tasks}
        
        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                if result and result['success']:
                    all_results.extend(result['rows'])
                    completed += 1
                    print(f"  [{completed + failed}/{total_tasks}] {task['mode']:6s} users={task['num_users']:2d} run={task['run_idx']+1}: OK ({len(result['rows'])} users)")
                else:
                    failed += 1
                    print(f"  [{completed + failed}/{total_tasks}] {task['mode']:6s} users={task['num_users']:2d} run={task['run_idx']+1}: FAILED")
            except Exception as e:
                failed += 1
                print(f"  [{completed + failed}/{total_tasks}] {task['mode']:6s} users={task['num_users']:2d} run={task['run_idx']+1}: ERROR - {e}")
    
    # Save results
    if all_results:
        output_file = RESULTS_DIR / f"comparison_{timestamp}.csv"
        fieldnames = ['mode', 'run_id', 'num_users', 'user_id', 'compression_level',
                      'total_frames', 'on_time_frames', 'avg_delay_ms',
                      'delay_reliability', 'user_satisfied', 'avg_mse', 'avg_cqi']
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*50}")
        print("COMPARISON STUDY COMPLETE")
        print(f"{'='*50}")
        print(f"Completed: {completed}, Failed: {failed}")
        print(f"Total rows: {len(all_results)}")
        print(f"Output file: {output_file}")
        
        # Print summary statistics
        print_summary(all_results)
    else:
        print("\nNo results generated!")


def print_summary(results: List[Dict]):
    """Print summary comparison of random vs ML modes."""
    
    random_results = [r for r in results if r['mode'] == 'random']
    ml_results = [r for r in results if r['mode'] == 'ml']
    
    def calc_stats(data):
        if not data:
            return {}
        mse_values = [r['avg_mse'] for r in data if r['avg_mse'] > 0]
        delay_values = [r['avg_delay_ms'] for r in data]
        reliability = [r['delay_reliability'] for r in data]
        satisfied = [r['user_satisfied'] for r in data]
        
        return {
            'count': len(data),
            'avg_mse': sum(mse_values) / len(mse_values) if mse_values else 0,
            'avg_delay': sum(delay_values) / len(delay_values) if delay_values else 0,
            'avg_reliability': sum(reliability) / len(reliability) if reliability else 0,
            'satisfaction_rate': sum(satisfied) / len(satisfied) if satisfied else 0
        }
    
    random_stats = calc_stats(random_results)
    ml_stats = calc_stats(ml_results)
    
    print(f"\n{'='*50}")
    print("SUMMARY STATISTICS")
    print(f"{'='*50}")
    print(f"{'Metric':<25} {'Random':<15} {'ML-Guided':<15} {'Improvement':<15}")
    print("-" * 70)
    
    if random_stats and ml_stats:
        # MSE (lower is better)
        mse_improvement = ((random_stats['avg_mse'] - ml_stats['avg_mse']) / random_stats['avg_mse'] * 100) if random_stats['avg_mse'] > 0 else 0
        print(f"{'Avg MSE':<25} {random_stats['avg_mse']:<15.2f} {ml_stats['avg_mse']:<15.2f} {mse_improvement:+.1f}%")
        
        # Delay (lower is better)
        delay_improvement = ((random_stats['avg_delay'] - ml_stats['avg_delay']) / random_stats['avg_delay'] * 100) if random_stats['avg_delay'] > 0 else 0
        print(f"{'Avg Delay (ms)':<25} {random_stats['avg_delay']:<15.2f} {ml_stats['avg_delay']:<15.2f} {delay_improvement:+.1f}%")
        
        # Reliability (higher is better)
        rel_improvement = ((ml_stats['avg_reliability'] - random_stats['avg_reliability']) / random_stats['avg_reliability'] * 100) if random_stats['avg_reliability'] > 0 else 0
        print(f"{'Avg Reliability':<25} {random_stats['avg_reliability']*100:<14.1f}% {ml_stats['avg_reliability']*100:<14.1f}% {rel_improvement:+.1f}%")
        
        # Satisfaction rate (higher is better)
        sat_improvement = ((ml_stats['satisfaction_rate'] - random_stats['satisfaction_rate']) / random_stats['satisfaction_rate'] * 100) if random_stats['satisfaction_rate'] > 0 else 0
        print(f"{'Satisfaction Rate':<25} {random_stats['satisfaction_rate']*100:<14.1f}% {ml_stats['satisfaction_rate']*100:<14.1f}% {sat_improvement:+.1f}%")
    
    print(f"{'='*50}")


def quick_test():
    """Run a quick test with minimal simulations."""
    print("=== Quick Test Mode ===")
    
    # Test model server connection
    try:
        health = requests.get(f"{MODEL_SERVER_URL}/health", timeout=2000)
        print(f"Model server: {health.json()}")
    except Exception as e:
        print(f"Model server not available: {e}")
    
    num_users = 4
    
    # Test random mode
    print(f"\nTesting random mode with {num_users} users...")
    compression_levels = get_compression_levels("random", num_users, seed=42)
    print(f"  Compression levels: {compression_levels}")
    
    result = run_simulation(num_users, compression_levels, run_id=999, mode="random")
    if result and result.get('success'):
        print(f"  Success! {len(result.get('user_results', []))} user results")
    else:
        print("  Failed!")
    
    # Test ML mode with CQI warmup
    print(f"\nTesting ML mode with CQI warmup ({num_users} users)...")
    print("  Running warmup to collect actual CQI values...")
    user_cqis = run_cqi_warmup(num_users, warmup_frames=30, seed=42)
    print(f"  User CQIs: {user_cqis}")
    
    compression_levels = get_compression_levels("ml", num_users, seed=42, user_cqis=user_cqis)
    print(f"  ML Compression levels: {compression_levels}")
    
    result = run_simulation(num_users, compression_levels, run_id=998, mode="ml")
    if result and result.get('success'):
        print(f"  Success! {len(result.get('user_results', []))} user results")
        for ur in result.get('user_results', []):
            print(f"    User {ur['user_id']}: CQI={ur['avg_cqi']:.2f}, Comp={ur['compression_level']}")
    else:
        print("  Failed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run comparison study: Random vs ML-guided compression")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                       help=f"Number of runs per user count per mode (default: {DEFAULT_RUNS})")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    parser.add_argument("--test", action="store_true",
                       help="Run quick test")
    
    args = parser.parse_args()
    
    if args.test:
        quick_test()
    else:
        run_comparison_study(num_runs=args.runs, seed=args.seed)
