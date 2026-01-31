#!/usr/bin/env python3
"""
XR Traffic Data Generator for Simu5G Simulations

Generates synthetic XR frame data matching the statistical profile of real XR traffic.
The output CSV can be used with XRTrafficSource module in Simu5G.

Traffic Profile (based on 3GPP TR 38.838):
- Frame rate: 60 fps (configurable)
- Mean frame size: ~62.5 KB (for ~30 Mbps)
- Frame size distribution: Truncated Gaussian
- MSE: 0 for baseline (uncompressed)

Usage:
    python generate_xr_traffic.py --output xr_traffic_30mbps.csv --duration 20
    python generate_xr_traffic.py --output xr_traffic.csv --bitrate 45 --fps 90

Requirements: Python 3.8+ (standard library only, no external dependencies)
"""

import argparse
import csv
import random
import math
from pathlib import Path
from typing import List, Dict


def truncated_gaussian(mean: float, std: float, min_val: float, max_val: float, 
                        size: int) -> List[float]:
    """
    Generate samples from a truncated Gaussian distribution.
    
    Uses rejection sampling with Python's random.gauss().
    
    Args:
        mean: Mean of the distribution
        std: Standard deviation
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        size: Number of samples to generate
    
    Returns:
        List of samples within [min_val, max_val]
    """
    samples = []
    max_attempts = size * 100  # Prevent infinite loops
    attempts = 0
    
    while len(samples) < size and attempts < max_attempts:
        x = random.gauss(mean, std)
        if min_val <= x <= max_val:
            samples.append(x)
        attempts += 1
    
    # If we hit max attempts, fill remaining with clamped values
    while len(samples) < size:
        x = random.gauss(mean, std)
        x = max(min_val, min(max_val, x))
        samples.append(x)
    
    return samples


def calculate_frame_size_params(target_bitrate_mbps: float, fps: float) -> Dict[str, float]:
    """
    Calculate frame size distribution parameters to achieve target bitrate.
    
    Based on 3GPP TR 38.838 XR traffic model characteristics:
    - Frame sizes follow a truncated Gaussian distribution
    - Size variation coefficient ~0.3 (std/mean)
    - Min/max typically ±50% of mean
    
    Args:
        target_bitrate_mbps: Target average bitrate in Mbps
        fps: Frames per second
    
    Returns:
        Dictionary with mean, std, min, max in bytes
    """
    # Convert Mbps to bytes per frame
    bits_per_second = target_bitrate_mbps * 1e6
    bytes_per_second = bits_per_second / 8
    mean_frame_size = bytes_per_second / fps
    
    # Typical variation coefficient for XR traffic
    variation_coeff = 0.3
    std_frame_size = mean_frame_size * variation_coeff
    
    # Truncation bounds (approximately ±50% of mean)
    min_frame_size = max(1000, mean_frame_size * 0.35)  # At least 1KB
    max_frame_size = mean_frame_size * 1.5
    
    return {
        'mean': mean_frame_size,
        'std': std_frame_size,
        'min': min_frame_size,
        'max': max_frame_size
    }


def generate_xr_traffic_data(
    num_frames: int,
    target_bitrate_mbps: float = 30.0,
    fps: float = 60.0,
    components: int = 0,
    mse: float = 0.0,
    seed: int = 42
) -> List[Dict]:
    """
    Generate XR traffic frame data.
    
    Args:
        num_frames: Number of frames to generate
        target_bitrate_mbps: Target average bitrate in Mbps
        fps: Frames per second
        components: PCA components value (0 = uncompressed)
        mse: Mean squared error value (0 = lossless)
        seed: Random seed for reproducibility
    
    Returns:
        List of dictionaries with frame data
    """
    random.seed(seed)
    
    # Calculate distribution parameters
    params = calculate_frame_size_params(target_bitrate_mbps, fps)
    
    # Generate frame sizes
    frame_sizes = truncated_gaussian(
        mean=params['mean'],
        std=params['std'],
        min_val=params['min'],
        max_val=params['max'],
        size=num_frames
    )
    
    # Round to integers (bytes)
    frame_sizes = [round(s) for s in frame_sizes]
    
    # Create frame data
    frames = []
    for i in range(num_frames):
        frames.append({
            'frame': i + 1,
            'components': components,
            'mse': mse,
            'size_bytes': int(frame_sizes[i])
        })
    
    return frames


def write_csv(frames: List[Dict], output_path: Path) -> None:
    """Write frame data to CSV file."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['frame', 'components', 'mse', 'size_bytes'])
        writer.writeheader()
        writer.writerows(frames)


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of values."""
    n = len(values)
    if n == 0:
        return {'mean': 0, 'std': 0, 'min': 0, 'max': 0}
    
    mean_val = sum(values) / n
    variance = sum((x - mean_val) ** 2 for x in values) / n
    std_val = math.sqrt(variance)
    
    return {
        'mean': mean_val,
        'std': std_val,
        'min': min(values),
        'max': max(values)
    }


def print_statistics(frames: List[Dict], target_bitrate: float, fps: float) -> None:
    """Print summary statistics of generated data."""
    sizes = [f['size_bytes'] for f in frames]
    stats = calculate_statistics(sizes)
    
    actual_bitrate = (stats['mean'] * 8 * fps) / 1e6
    
    print()
    print("=" * 50)
    print("XR Traffic Data Generation Summary")
    print("=" * 50)
    print(f"Total frames:       {len(frames)}")
    print(f"Frame rate:         {fps} fps")
    print(f"Duration:           {len(frames) / fps:.2f} seconds")
    print("-" * 50)
    print(f"Target bitrate:     {target_bitrate:.2f} Mbps")
    print(f"Actual bitrate:     {actual_bitrate:.2f} Mbps")
    print("-" * 50)
    print(f"Mean frame size:    {stats['mean'] / 1024:.2f} KB")
    print(f"Min frame size:     {stats['min'] / 1024:.2f} KB")
    print(f"Max frame size:     {stats['max'] / 1024:.2f} KB")
    print(f"Std deviation:      {stats['std'] / 1024:.2f} KB")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Generate XR traffic data for Simu5G simulations",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='xr_traffic.csv',
        help='Output CSV file path'
    )
    
    parser.add_argument(
        '-d', '--duration',
        type=float,
        default=20.0,
        help='Simulation duration in seconds'
    )
    
    parser.add_argument(
        '-f', '--fps',
        type=float,
        default=60.0,
        help='Frame rate (frames per second)'
    )
    
    parser.add_argument(
        '-b', '--bitrate',
        type=float,
        default=30.0,
        help='Target bitrate in Mbps'
    )
    
    parser.add_argument(
        '-c', '--components',
        type=int,
        default=0,
        help='PCA components (0 = uncompressed baseline)'
    )
    
    parser.add_argument(
        '-m', '--mse',
        type=float,
        default=0.0,
        help='MSE value (0 = lossless baseline)'
    )
    
    parser.add_argument(
        '-s', '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress statistics output'
    )
    
    args = parser.parse_args()
    
    # Calculate number of frames
    num_frames = int(args.duration * args.fps)
    
    # Generate data
    frames = generate_xr_traffic_data(
        num_frames=num_frames,
        target_bitrate_mbps=args.bitrate,
        fps=args.fps,
        components=args.components,
        mse=args.mse,
        seed=args.seed
    )
    
    # Write to file
    output_path = Path(args.output)
    write_csv(frames, output_path)
    
    if not args.quiet:
        print_statistics(frames, args.bitrate, args.fps)
        print(f"\nOutput written to: {output_path.absolute()}")


if __name__ == '__main__':
    main()
