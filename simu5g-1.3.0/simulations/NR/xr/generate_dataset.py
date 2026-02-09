#!/usr/bin/env python3
"""
Minimal Dataset Generation Script for Simu5G XR Simulations

Runs simulations with varying users, compression levels, FPS, and traffic profiles.
Outputs results to compression_dataset.csv
"""

import os
import csv
import random
import subprocess
import shutil
from pathlib import Path

# Configuration
COMPRESSION_LEVELS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
FPS_RATES = [60, 72, 90, 120]
USER_RANGE = range(2, 11)  # 2 to 10 users
SIMULATION_DIR = Path(__file__).parent
SIMULATION_TIME = 20  # seconds

TRAFFIC_PROFILES = [
    {"file": "traffic_45kb.csv", "mean_kb": 45.0, "std_kb": 24.1, "min_kb": 5.8, "max_kb": 84.2},
    {"file": "traffic_65kb.csv", "mean_kb": 65.0, "std_kb": 34.8, "min_kb": 8.3, "max_kb": 121.7},
    {"file": "traffic_80kb.csv", "mean_kb": 80.0, "std_kb": 42.9, "min_kb": 10.2, "max_kb": 149.8},
    {"file": "traffic_95kb.csv", "mean_kb": 95.0, "std_kb": 50.9, "min_kb": 12.2, "max_kb": 177.8},
    {"file": "traffic_120kb.csv", "mean_kb": 120.0, "std_kb": 64.3, "min_kb": 15.3, "max_kb": 224.7},
]


def load_pca_sweep_data(pca_file):
    """Load PCA sweep data grouped by compression level."""
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


def create_user_pca_file(user_id, compression_level, data_by_level, output_dir):
    """Create a PCA CSV file for a specific user."""
    output_file = output_dir / f"user_{user_id}_comp_{compression_level}.csv"
    frames = data_by_level[compression_level]
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'components', 'mse', 'size_bytes'])
        for frame in frames:
            writer.writerow([frame['frame'], frame['components'], frame['mse'], frame['size_bytes']])
    return output_file


def run_simulation(num_users, compression_levels, fps_rates, traffic_profiles, run_id, deadline_ms=5.0):
    """Run a single simulation and return results."""
    run_dir = SIMULATION_DIR / f"run_temp_{run_id}"
    run_dir.mkdir(exist_ok=True)
    
    # Create per-user PCA files
    user_files = []
    for i in range(num_users):
        data_by_level = load_pca_sweep_data(SIMULATION_DIR / traffic_profiles[i]['file'])
        user_file = create_user_pca_file(i, compression_levels[i], data_by_level, run_dir)
        user_files.append(user_file)
    
    # Build simulation command
    cmd = [
        "simu5g", "-r", "0", "-m", "-u", "Cmdenv", "-c", "XR-DL-Dataset",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
        f"--*.ue[*].app[0].deadlineMs={deadline_ms}ms",
    ]
    
    for i in range(num_users):
        expected_frames = fps_rates[i] * SIMULATION_TIME
        cmd.append(f'--*.server.app[{i}].pcaFile="{user_files[i]}"')
        cmd.append(f'--*.server.app[{i}].fps={fps_rates[i]}')
        cmd.append(f'--*.ue[{i}].app[0].expectedFrames={expected_frames}')
    
    cmd.append("omnetpp.ini")
    
    try:
        result = subprocess.run(cmd, cwd=SIMULATION_DIR, capture_output=True, text=True, timeout=3000)
        
        # Parse results from CSV
        csv_path = SIMULATION_DIR / "user_results.csv"
        user_results = []
        
        if csv_path.exists():
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = int(row['user_id'])
                    user_results.append({
                        'user_id': uid,
                        'fps': fps_rates[uid],
                        'compression_level': compression_levels[uid],
                        'size_mean_kb': traffic_profiles[uid]['mean_kb'],
                        'size_min_kb': traffic_profiles[uid]['min_kb'],
                        'size_max_kb': traffic_profiles[uid]['max_kb'],
                        'size_std_kb': traffic_profiles[uid]['std_kb'],
                        'total_frames': int(row['total_frames']),
                        'on_time_frames': int(row['on_time_frames']),
                        'avg_delay_ms': float(row['avg_delay_ms']),
                        'delay_reliability': float(row['delay_reliability']),
                        'user_satisfied': int(row['user_satisfied']),
                        'avg_mse': float(row['avg_mse']),
                        'avg_cqi': float(row['avg_cqi'])
                    })
            csv_path.unlink()
        
        return {'run_id': run_id, 'num_users': num_users, 'user_results': user_results, 
                'success': result.returncode == 0 and len(user_results) > 0}
    
    except subprocess.TimeoutExpired:
        return {'run_id': run_id, 'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'run_id': run_id, 'success': False, 'error': str(e)}
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def generate_dataset(num_runs=10, deadline_ms=5.0, seed=42):
    """Generate the dataset."""
    random.seed(seed)
    output_file = SIMULATION_DIR / "compression_dataset.csv"
    
    print(f"Generating dataset: {num_runs} runs per user count, deadline={deadline_ms}ms")
    
    all_results = []
    run_id = 0
    
    for num_users in USER_RANGE:
        for run in range(num_runs):
            run_id += 1
            comp_levels = [random.choice(COMPRESSION_LEVELS) for _ in range(num_users)]
            fps = [random.choice(FPS_RATES) for _ in range(num_users)]
            profiles = [random.choice(TRAFFIC_PROFILES) for _ in range(num_users)]
            
            result = run_simulation(num_users, comp_levels, fps, profiles, run_id, deadline_ms)
            
            if result['success']:
                for user in result['user_results']:
                    all_results.append({'run_id': run_id, 'num_users': num_users, **user})
                print(f"Run {run_id}: {num_users} users - OK ({len(result['user_results'])} results)")
            else:
                print(f"Run {run_id}: {num_users} users - FAILED")
    
    # Save results
    if all_results:
        fieldnames = ['run_id', 'num_users', 'user_id', 'fps', 'compression_level',
                      'size_mean_kb', 'size_min_kb', 'size_max_kb', 'size_std_kb',
                      'total_frames', 'on_time_frames', 'avg_delay_ms',
                      'delay_reliability', 'user_satisfied', 'avg_mse', 'avg_cqi']
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\nDone! {len(all_results)} rows saved to {output_file}")
    else:
        print("No results generated!")


if __name__ == "__main__":
    generate_dataset(num_runs=1, deadline_ms=5.0, seed=42)
