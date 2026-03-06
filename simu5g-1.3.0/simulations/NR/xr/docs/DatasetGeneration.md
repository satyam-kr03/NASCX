# XR Dataset Generation Methodology

This document outlines the methodology used to generate the Machine Learning (ML) training dataset for XR video streaming over 5G using Simu5G. The pipeline automates the entire process from trace preparation to simulating varying network conditions, and finally assembling the dataset into a machine-readable format for model training.

## Overview

The objective of the dataset generation pipeline is to collect granular, per-frame statistics across a multi-user 5G network under varying load conditions. For each frame, the simulation randomly selects a compression level (PCA components) and logs the resulting network metrics alongside the video's inherent complexity features. This helps train a dynamic compression model that can predict the optimal compression level given real-time network conditions.

The dataset generation is orchestrated via the `generate_dataset.py` script and driven by the `XR-DL-RandomCL` configuration in `omnetpp.ini`.

The simulation execution pipeline follows a structured, five-step methodology:

### 1. Complexity Statistics Compilation
Before starting the simulations, the script analyzes the ground-truth traffic metadata for each available video.
- Reads `pca_sweep_summary_*.csv` files, which contain frame statistics across different compression levels.
- Computes baseline video statistics, including the **mean** and **standard deviation** of frame complexity.
- Extracts the raw baseline per-frame complexity for each individual frame.
- Saves a summary of these statistics to `datasets/complexity_stats.json`.

### 2. PCA Trace Trimming
To establish a uniform and manageable simulation scope, the pipeline enforces a strict cap of up to a predefined limit (default: **2000 frames**).
- Trimmed versions of the PCA traffic files are generated containing only the targeted subset of frames.
- These stripped-down traces are stored in `traffic_files/trimmed/` and directly provided to the simulation application to speed up parsing speeds and minimize memory overhead.

### 3. Simulation Job Preparation & Assignment
The script sweeps through a defined range of concurrent network users (e.g., **2 through 10 users**) to simulate different network load environments. For each user count configuration, multiple independent simulation runs (repetitions) are prepared with distinct random seeds.

During job preparation, the script allocates user parameters in a reproducible manner:
- **Video Assignment**: Cycles through the available trimmed PCA videos, assigning one to each simulated User Equipment (UE).
- **Frame Rate (FPS) Assignment**: Each user is randomly assigned a target frame rate from a pool of viable options (e.g., 45, 60, 72, 90, 120 FPS).

### 4. Simu5G Simulation Setup & Execution
The script executes multiple Simu5G simulations concurrently by distributing the jobs across a multiprocessing pool pointing to the `XR-DL-RandomCL` configuration. The simulation establishes standard XR networking over a meticulously parameterized 5G environment.

#### Network Architecture and Base Station
The simulation is anchored on an **NR Standalone (SA)** architecture.
- **Spectrum**: Uses a 100 MHz bandwidth parameterized with $\mu=1$ numerology (30 kHz Subcarrier Spacing), operating at a carrier frequency of 2.4 GHz, which mathematically translates to 273 Resource Blocks (RBs) available for scheduling.
- **Power Envelope**: The gNodeB explicitly operates at a maximum transmission power of 44 dBm, positioned at the dead center of the simulation bound `(600m, 600m)`. Mobile UEs transmit at 23 dBm.

#### Large-Scale UE Topology & Aggressive Mobility
By default, Simu5G deployments default to a standard 250m × 250m area, which largely homogenizes distance-based Quality-of-Service constraints and Channel Quality Indicators (CQI) metrics.

To generate a generalized training dataset exploring widespread signal variability, the `XR-DL-RandomCL` protocol significantly scales up bounds and introduces aggressive random mobility:
- **Wide Coverage Area**: The deployment area is explicitly expanded to an urban-scale **1200m × 1200m** zone, ensuring immense spatial diversity.
- **Aggressive Mobility Options**: Utilizing `RandomWaypointMobility`, simulated UEs move aggressively between speeds of **5 m/s to 40 m/s** with no resting intervals (`waitTime = 0s`).
- **Initial Distance Segregation**: The simulation initializes UEs via pre-identified distance profiles to guarantee that all CQI regimes are sampled symmetrically. Depending on the concurrent load, the configuration orchestrates random uniform bounds across:
  - **Near Users**: Bound within ~50-100m from the center, generating perfect/near-perfect CQIs (`12-15`).
  - **Mid-Range Users**: Bound within ~200-400m from the center, generating standard/degrading CQIs (`6-12`).
  - **Far Users**: Segregated explicitly to the bounds and corners up to 600-800m away, enforcing heavily degraded extreme worst-case CQI patterns (`1-6`).

#### Channel Modeling and Random MAC Scheduling Setup
- **Realistic Link Loss**: Transitions the simplistic flat Rayleigh fading layout to `URBAN_MACROCELL` scenarios layered with explicit channel **shadowing** enabled. These combined physics models allow the system to simulate realistic localized CQI degradations based not just on UE distance, but dynamically based on time/channel properties as they aggressively roam.
- **Downlink Scheduling**: Upgraded to the **MAXCI (Maximum Carrier-to-Interference ratio)** scheduler algorithm for MAC-layer evaluations over default Proportional Fair constraints, simulating harsh data contention limitations more robust for machine learning evaluation. 

#### Application Physics and Component Variation
- **Traffic Jitter Modeling**: The generic XR Traffic stream simulates frame production delays using Truncated Gaussian characteristics (mean = -4ms, Standard Deviation = 2ms).
- **Strict Delay Bounds**: XR downlink application receivers are tasked with evaluating hard deadlines bound to **5 ms**.
- **Per Frame Variation Processing**: Evaluates the incoming traffic trace with `selectionMode = "random"`, overriding flat transmission configurations with dynamically injected, per-frame randomized compression level properties directly at simulation runtime.

### 5. Data Collection & Dataset Assembly
After the simulations complete, the script scrapes the generated logs and stitches together a comprehensive, tabular dataset (`datasets/random_cl_dataset.csv`).

Key aggregation logic:
- The script reads the `user_{i}.csv` files corresponding to each active user in a given simulation.
- **Strict Matching**: A frame row is only added to the final dataset if *all* participating users have successfully logged data for that specific `frameNumber`.
- Each finalized row represents a specific `frameNumber` in a specific simulation.

For each user, the row will populate the following columns prefixed with `user{i}_`:
* `meantrafficsize`: The aggregate average frame complexity of the user's video.
* `stdtrafficsize`: The standard deviation of frame complexities for the user's video.
* `components`: The specific compression level applied to this frame randomly by the network/server.
* `effectiveError`: The mathematical prediction/reconstruction error associated with applying the chosen compression components.
* `frameComplexity`: The pre-computed baseline complexity measurement of this exact frame.
* `delay_ms`: The total logged end-to-end latency experienced while transmitting this frame.
* `cqi`: The explicit downstream Channel Quality Indicator observed closest to the frame reception event.
* `frame_rate`: The target user-assigned FPS.

The row also includes a global `num_users` indicating the scale/load of the simulated network.

## Usage

To generate the dataset, run the script from the command line:

```bash
python generate_dataset.py [--repetitions N] [--sim-time S] [--dry-run]
```

- `--repetitions`: Customize how many times each user-count topology is simulated (default: 3).
- `--sim-time`: The hard OMNeT++ execution timeout. Standard setup allocates enough time for all 2000 frames to arrive (default: 35 seconds).
- `--dry-run`: Runs the pipeline strictly up to Step 2 to verify trace formatting without launching actual OMNeT++ simulations.
