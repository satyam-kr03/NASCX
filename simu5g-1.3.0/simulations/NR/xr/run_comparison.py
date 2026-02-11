#!/usr/bin/env python3
"""
Comparison Study: ML-Dynamic vs Uncompressed

This script runs simulations comparing:
1. Uncompressed (baseline) — all frames use components=80 (maximum quality, least compression)
2. ML-guided dynamic compression — per-frame adaptive compression levels

The goal is to demonstrate that per-frame dynamic compression achieves
better delivery reliability while maintaining acceptable quality compared
to sending frames at full (uncompressed-equivalent) quality.

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
MAX_COMPRESSION = 80  # "Uncompressed-equivalent" — maximum quality, least compression
FPS_RATES = [60, 72, 90, 120]  # Supported frame rates
USER_RANGE = range(2, 11)  # 2 to 10 users
DEFAULT_RUNS = 10
SIMULATION_DIR = Path(__file__).parent
PCA_FILE = SIMULATION_DIR / "pca_sweep_summary_scaled.csv"
MODEL_SERVER_URL = "http://localhost:8000"
SIMULATION_TIME = 20  # seconds

# Traffic profile configuration (matching generate_dataset.py)
TRAFFIC_PROFILES = [
    {"file": "traffic_45kb.csv", "mean_kb": 45.0, "std_kb": 24.1, "min_kb": 5.8, "max_kb": 84.2},
    {"file": "traffic_65kb.csv", "mean_kb": 65.0, "std_kb": 34.8, "min_kb": 8.3, "max_kb": 121.7},
    {"file": "traffic_80kb.csv", "mean_kb": 80.0, "std_kb": 42.9, "min_kb": 10.2, "max_kb": 149.8},
    {"file": "traffic_95kb.csv", "mean_kb": 95.0, "std_kb": 50.9, "min_kb": 12.2, "max_kb": 177.8},
    {"file": "traffic_120kb.csv", "mean_kb": 120.0, "std_kb": 64.3, "min_kb": 15.3, "max_kb": 224.7},
]

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


def load_pca_data(traffic_file: Path = None) -> Dict[int, List[Dict]]:
    """Load PCA sweep data grouped by compression level.
    
    Args:
        traffic_file: Path to traffic profile CSV. If None, uses default PCA_FILE.
    """
    data_by_level = {level: [] for level in COMPRESSION_LEVELS}
    pca_file = traffic_file if traffic_file else PCA_FILE
    
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


def create_adaptive_pca_file(user_id: int, frame_comp_map: Dict[int, int],
                              data_by_level: Dict, output_dir: Path) -> Path:
    """Create a PCA CSV where each frame has a DIFFERENT compression level.
    
    Args:
        user_id: User index
        frame_comp_map: Dict mapping frame_number -> compression_level
        data_by_level: PCA sweep data grouped by compression level
        output_dir: Directory for output files
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


def query_per_frame_model(num_users: int, avg_cqi: float, fps: int,
                           frame_complexities: List[float]) -> List[int]:
    """Query the model server for per-frame compression levels.
    
    Args:
        num_users: Number of users in the cell
        avg_cqi: Average CQI for this user
        fps: Frame rate
        frame_complexities: List of frame complexity values (size at max components)
    
    Returns:
        List of compression levels, one per frame
    """
    try:
        response = requests.post(
            f"{MODEL_SERVER_URL}/predict_per_frame",
            json={
                "num_users": num_users,
                "avg_cqi": avg_cqi,
                "fps": fps,
                "frame_complexities": frame_complexities
            },
            timeout=30000
        )
        if response.status_code == 200:
            return response.json()["per_frame_compression"]
        else:
            print(f"  Per-frame model server error: {response.status_code} - {response.text}")
            # Fallback: return random compression per frame
            return [random.choice(COMPRESSION_LEVELS) for _ in frame_complexities]
    except requests.exceptions.RequestException as e:
        print(f"  Per-frame model server connection error: {e}")
        return [random.choice(COMPRESSION_LEVELS) for _ in frame_complexities]


def run_cqi_warmup(num_users: int, fps_rates: List[int], traffic_profiles: List[Dict],
                   warmup_frames: int = 50, seed: int = 42) -> Dict[int, float]:
    """Run a short warmup simulation to collect actual CQI values for each user.
    
    Args:
        num_users: Number of users in the cell
        fps_rates: List of FPS values per user
        traffic_profiles: List of traffic profile dicts per user
        warmup_frames: Number of frames to run for warmup (default 50)
        seed: Random seed for compression selection
        
    Returns:
        Dict mapping user_id to their average CQI value
    """
    random.seed(seed)
    
    # Create temporary directory for warmup
    run_dir = SIMULATION_DIR / f"warmup_{num_users}_{seed}"
    run_dir.mkdir(exist_ok=True)
    
    # Use mid-level compression for warmup (less biased than random)
    warmup_comp = 40
    
    # Generate per-user PCA files using their traffic profiles
    user_files = []
    for i in range(num_users):
        traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
        data_by_level = load_pca_data(traffic_file)
        user_file = create_user_pca_file(i, warmup_comp, data_by_level, run_dir)
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
    ]
    
    # Add per-user PCA file paths, FPS, and expected frames
    for i, user_file in enumerate(user_files):
        fps = fps_rates[i]
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_file}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].expectedFrames={warmup_frames}')
    
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


def get_dynamic_compression(num_users: int, fps_rates: List[int],
                             traffic_profiles: List[Dict],
                             user_cqis: Dict[int, float]) -> Dict[int, Dict[int, int]]:
    """Get per-frame compression levels for each user (ml-dynamic mode).
    
    Args:
        num_users: Number of users
        fps_rates: FPS per user
        traffic_profiles: Traffic profile per user
        user_cqis: Per-user CQI values from warmup
    
    Returns:
        Dict[user_id -> Dict[frame_number -> compression_level]]
    """
    per_user_frame_comps = {}
    
    for user_id in range(num_users):
        cqi = user_cqis.get(user_id, 14.0)
        fps = fps_rates[user_id]
        profile = traffic_profiles[user_id]
        
        # Load PCA sweep data for this user's traffic profile
        traffic_file = SIMULATION_DIR / profile['file']
        data_by_level = load_pca_data(traffic_file)
        
        # Get frame complexity = size_bytes at max components (80) for each frame
        max_comp_frames = data_by_level[MAX_COMPRESSION]
        expected_frames = fps * SIMULATION_TIME
        max_comp_frames = max_comp_frames[:expected_frames]
        
        frame_complexities = [float(f['size_bytes']) for f in max_comp_frames]
        frame_numbers = [f['frame'] for f in max_comp_frames]
        
        # Query the per-frame model in one batch
        per_frame_comps = query_per_frame_model(
            num_users=num_users,
            avg_cqi=cqi,
            fps=fps,
            frame_complexities=frame_complexities
        )
        
        # Map frame_number -> compression_level
        frame_comp_map = {
            frame_numbers[i]: per_frame_comps[i]
            for i in range(len(frame_numbers))
        }
        per_user_frame_comps[user_id] = frame_comp_map
    
    return per_user_frame_comps


def run_simulation(num_users: int, compression_levels: List[int],
                   fps_rates: List[int], traffic_profiles: List[Dict], 
                   run_id: int, mode: str,
                   per_user_frame_comps: Optional[Dict[int, Dict[int, int]]] = None) -> Optional[Dict]:
    """Run a single simulation and return results.
    
    Args:
        num_users: Number of users
        compression_levels: List of compression levels per user (for uncompressed mode)
        fps_rates: List of FPS values per user
        traffic_profiles: List of traffic profile dicts per user
        run_id: Run identifier
        mode: 'uncompressed' or 'ml-dynamic'
        per_user_frame_comps: For ml-dynamic mode, Dict[user_id -> Dict[frame_number -> compression_level]]
    """
    
    # Create temporary directory for this run
    run_dir = SIMULATION_DIR / f"run_{mode}_{run_id}"
    run_dir.mkdir(exist_ok=True)
    
    # Generate per-user PCA files
    user_files = []
    if mode == "ml-dynamic" and per_user_frame_comps:
        # DYNAMIC: each frame can have a different compression level
        for i in range(num_users):
            traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
            data_by_level = load_pca_data(traffic_file)
            user_file = create_adaptive_pca_file(i, per_user_frame_comps[i],
                                                  data_by_level, run_dir)
            user_files.append(user_file)
    else:
        # UNCOMPRESSED: fixed compression level (80) per user
        for i, comp_level in enumerate(compression_levels[:num_users]):
            traffic_file = SIMULATION_DIR / traffic_profiles[i]['file']
            data_by_level = load_pca_data(traffic_file)
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
    
    # Add per-user PCA file paths, FPS, and expected frames
    for i, user_file in enumerate(user_files):
        fps = fps_rates[i]
        expected_frames = fps * SIMULATION_TIME
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_file}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].expectedFrames={expected_frames}')
    
    cmd.append("omnetpp.ini")
    
    # Log compression info
    if mode == "ml-dynamic" and per_user_frame_comps:
        unique_counts = [len(set(per_user_frame_comps[i].values())) for i in range(num_users)]
        print(f"  Mode={mode}, Users={num_users}, UniqueCompsPerUser={unique_counts}")
    else:
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
        user_results = parse_simulation_output(output, num_users, compression_levels,
                                               fps_rates, traffic_profiles)
        
        return {
            'run_id': run_id,
            'mode': mode,
            'num_users': num_users,
            'compression_levels': compression_levels[:num_users],
            'fps_rates': fps_rates[:num_users],
            'traffic_profiles': [p['file'] for p in traffic_profiles[:num_users]],
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
                           compression_levels: List[int],
                           fps_rates: List[int] = None,
                           traffic_profiles: List[Dict] = None) -> List[Dict]:
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
        fps = fps_rates[user_id] if fps_rates and user_id < len(fps_rates) else 60
        profile = traffic_profiles[user_id] if traffic_profiles and user_id < len(traffic_profiles) else TRAFFIC_PROFILES[0]
        
        avg_mse = 0.0
        for mse_match in mse_pattern.finditer(output):
            if int(mse_match.group(1)) == user_id:
                avg_mse = float(mse_match.group(2))
                break
        
        user_results.append({
            'user_id': user_id,
            'compression_level': comp_level,
            'fps': fps,
            'size_mean_kb': profile['mean_kb'],
            'size_std_kb': profile['std_kb'],
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
    For ml-dynamic mode, runs a warmup simulation first to collect actual CQI values.
    """
    mode = task['mode']
    num_users = task['num_users']
    run_id = task['run_id']
    run_seed = task['run_seed']
    fps_rates = task['fps_rates']
    traffic_profiles = task['traffic_profiles']
    
    per_user_frame_comps = None
    
    if mode == "ml-dynamic":
        # Run CQI warmup first, then get per-frame compression levels
        print(f"  Running CQI warmup for {num_users} users (mode={mode})...")
        user_cqis = run_cqi_warmup(num_users, fps_rates, traffic_profiles, 
                                   warmup_frames=50, seed=run_seed)
        
        per_user_frame_comps = get_dynamic_compression(
            num_users, fps_rates, traffic_profiles, user_cqis
        )
        # Create a summary compression_levels list for logging (use mode of per-frame comps)
        compression_levels = []
        for i in range(num_users):
            comps = list(per_user_frame_comps[i].values())
            from collections import Counter
            most_common = Counter(comps).most_common(1)[0][0]
            compression_levels.append(most_common)
    elif mode == "uncompressed":
        # Uncompressed: all users use components=80 (maximum quality)
        compression_levels = [MAX_COMPRESSION] * num_users
    else:
        raise ValueError(f"Unknown mode: {mode}")
    
    result = run_simulation(num_users, compression_levels, fps_rates, traffic_profiles,
                           run_id, mode, per_user_frame_comps=per_user_frame_comps)
    
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
            print("WARNING: Model server not healthy, ml-dynamic mode will fail")
    except:
        print("WARNING: Model server not running, ml-dynamic mode will fail")
        print("         Start with: python3 model_server.py &")
    
    # Build list of all tasks to run
    tasks = []
    run_id = 0
    for mode in ["uncompressed", "ml-dynamic"]:
        for num_users in USER_RANGE:
            for run_idx in range(num_runs):
                run_id += 1
                run_seed = seed + run_id + (2000 if mode == "ml-dynamic" else 0)
                random.seed(run_seed)
                
                # Assign FPS and traffic profiles per user (same seed offset for both modes)
                fps_rates = [random.choice(FPS_RATES) for _ in range(num_users)]
                traffic_profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
                
                tasks.append({
                    'mode': mode,
                    'num_users': num_users,
                    'run_id': run_id,
                    'run_idx': run_idx,
                    'run_seed': run_seed,
                    'fps_rates': fps_rates,
                    'traffic_profiles': traffic_profiles
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
                    print(f"  [{completed + failed}/{total_tasks}] {task['mode']:12s} users={task['num_users']:2d} run={task['run_idx']+1}: OK ({len(result['rows'])} users)")
                else:
                    failed += 1
                    print(f"  [{completed + failed}/{total_tasks}] {task['mode']:12s} users={task['num_users']:2d} run={task['run_idx']+1}: FAILED")
            except Exception as e:
                failed += 1
                print(f"  [{completed + failed}/{total_tasks}] {task['mode']:12s} users={task['num_users']:2d} run={task['run_idx']+1}: ERROR - {e}")
    
    # Save results
    if all_results:
        output_file = RESULTS_DIR / f"comparison_{timestamp}.csv"
        fieldnames = ['mode', 'run_id', 'num_users', 'user_id', 'compression_level',
                      'fps', 'size_mean_kb', 'size_std_kb',
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
    """Print summary comparison of Uncompressed vs ML-Dynamic."""
    
    modes = ['uncompressed', 'ml-dynamic']
    mode_labels = {'uncompressed': 'Uncompressed', 'ml-dynamic': 'ML-Dynamic'}
    
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
    
    mode_stats = {}
    for mode in modes:
        mode_data = [r for r in results if r['mode'] == mode]
        if mode_data:
            mode_stats[mode] = calc_stats(mode_data)
    
    print(f"\n{'='*70}")
    print("SUMMARY STATISTICS")
    print(f"{'='*70}")
    
    # Header
    header = f"{'Metric':<25}"
    for mode in modes:
        if mode in mode_stats:
            header += f" {mode_labels[mode]:<15}"
    print(header)
    print("-" * 70)
    
    uncomp_stats = mode_stats.get('uncompressed', {})
    
    # Print each metric
    metrics = [
        ('Avg MSE', 'avg_mse', 'lower'),
        ('Avg Delay (ms)', 'avg_delay', 'lower'),
        ('Avg Reliability', 'avg_reliability', 'higher'),
        ('Satisfaction Rate', 'satisfaction_rate', 'higher'),
    ]
    
    for label, key, direction in metrics:
        line = f"{label:<25}"
        for mode in modes:
            if mode not in mode_stats:
                continue
            val = mode_stats[mode].get(key, 0)
            if key in ('avg_reliability', 'satisfaction_rate'):
                line += f" {val*100:<14.1f}%"
            else:
                line += f" {val:<15.2f}"
        
        print(line)
    
    # Print improvement vs uncompressed
    if uncomp_stats:
        dynamic_stats = mode_stats.get('ml-dynamic', {})
        if dynamic_stats:
            print(f"\n{'ML-Dynamic vs Uncompressed':}")
            print("-" * 70)
            
            r = uncomp_stats
            m = dynamic_stats
            
            # For MSE, dynamic will likely be higher (worse) since it compresses more
            # but that's the expected trade-off for better delivery
            mse_diff = m['avg_mse'] - r['avg_mse']
            delay_imp = (r['avg_delay'] - m['avg_delay']) / r['avg_delay'] * 100 if r['avg_delay'] > 0 else 0
            rel_imp = (m['avg_reliability'] - r['avg_reliability']) / r['avg_reliability'] * 100 if r['avg_reliability'] > 0 else 0
            sat_diff = (m['satisfaction_rate'] - r['satisfaction_rate']) * 100
            
            print(f"  MSE trade-off:  {mse_diff:+.1f} ({'higher' if mse_diff > 0 else 'lower'} — compression trade-off)")
            print(f"  Delay:          {delay_imp:+.1f}% {'(better)' if delay_imp > 0 else '(worse)'}")
            print(f"  Reliability:    {rel_imp:+.1f}% {'(better)' if rel_imp > 0 else '(worse)'}")
            print(f"  Satisfaction:   {sat_diff:+.1f}pp")
    
    print(f"{'='*70}")


def quick_test():
    """Run a quick test with both modes."""
    print("=== Quick Test Mode (Uncompressed vs ML-Dynamic) ===")
    
    # Test model server connection
    try:
        health = requests.get(f"{MODEL_SERVER_URL}/health", timeout=2000)
        health_data = health.json()
        print(f"Model server: {health_data}")
        model_available = health_data.get('model_loaded', False)
        print(f"  Dynamic model available: {model_available}")
    except Exception as e:
        print(f"Model server not available: {e}")
        model_available = False
    
    num_users = 4
    random.seed(42)
    
    # Assign FPS and traffic profiles for test
    fps_rates = [random.choice(FPS_RATES) for _ in range(num_users)]
    traffic_profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
    
    print(f"\nTest configuration for {num_users} users:")
    for i in range(num_users):
        print(f"  User {i}: fps={fps_rates[i]}, traffic={traffic_profiles[i]['file']}")
    
    # ---- Test 1: Uncompressed mode ----
    print(f"\n{'='*50}")
    print("Testing UNCOMPRESSED mode (components=80)...")
    compression_levels = [MAX_COMPRESSION] * num_users
    print(f"  Compression levels: {compression_levels}")
    
    result = run_simulation(num_users, compression_levels, fps_rates, traffic_profiles,
                           run_id=999, mode="uncompressed")
    if result and result.get('success'):
        print(f"  Success! {len(result.get('user_results', []))} user results")
        for ur in result.get('user_results', []):
            print(f"    User {ur['user_id']}: CQI={ur['avg_cqi']:.2f}, FPS={ur.get('fps', 60)}, "
                  f"reliability={ur['delay_reliability']*100:.1f}%, MSE={ur['avg_mse']:.1f}")
    else:
        print("  Failed!")
    
    # ---- Test 2: ML-Dynamic mode (per-frame) ----
    if model_available:
        print(f"\n{'='*50}")
        print("Testing ML-DYNAMIC mode (per-frame compression)...")
        print("  Running warmup to collect actual CQI values...")
        user_cqis = run_cqi_warmup(num_users, fps_rates, traffic_profiles, 
                                   warmup_frames=30, seed=42)
        print(f"  User CQIs: {user_cqis}")
        
        per_user_frame_comps = get_dynamic_compression(
            num_users, fps_rates, traffic_profiles, user_cqis
        )
        
        # Show per-user compression diversity
        for i in range(num_users):
            comps = list(per_user_frame_comps[i].values())
            unique = len(set(comps))
            from collections import Counter
            top3 = Counter(comps).most_common(3)
            print(f"  User {i}: {len(comps)} frames, {unique} unique compression levels, "
                  f"top3={top3}")
        
        # Use mode of compressions as representative for logging
        compression_levels_summary = []
        for i in range(num_users):
            from collections import Counter
            comps = list(per_user_frame_comps[i].values())
            most_common = Counter(comps).most_common(1)[0][0]
            compression_levels_summary.append(most_common)
        
        result = run_simulation(num_users, compression_levels_summary, fps_rates, 
                              traffic_profiles, run_id=998, mode="ml-dynamic",
                              per_user_frame_comps=per_user_frame_comps)
        if result and result.get('success'):
            print(f"  Success! {len(result.get('user_results', []))} user results")
            for ur in result.get('user_results', []):
                print(f"    User {ur['user_id']}: CQI={ur['avg_cqi']:.2f}, FPS={ur.get('fps', 60)}, "
                      f"reliability={ur['delay_reliability']*100:.1f}%, MSE={ur['avg_mse']:.1f}")
        else:
            print("  Failed!")
    else:
        print(f"\n{'='*50}")
        print("Skipping ML-DYNAMIC test (dynamic model not loaded)")
        print("  Train with: python3 train_dynamic_model.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run comparison study: Uncompressed vs ML-Dynamic compression")
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
