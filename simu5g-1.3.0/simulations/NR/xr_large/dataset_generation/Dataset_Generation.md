# XR Streaming Dataset Generation Process

This document provides a comprehensive overview of the automated dataset generation process for the XR streaming simulation, orchestrated by the `generate_dataset.py` script.

## 1. Overview

The primary goal of the generation script is to create a robust machine learning training dataset. It records frame-by-frame telemetries by simulating a varying number of Virtual Reality (VR) / Extended Reality (XR) device users on a 5G network under varying load conditions.

During the simulations, users request video streams with dynamically assigned compression levels, and the network simulates the radio and network propagation environment to produce outputs like actual transmission delays, packet errors, and realistic wireless channel state information (CQI).

---

## 2. Process Configuration & Parameters

The behavior of the simulations is controlled via a series of variables and command-line arguments:

### Global Constants
- **FPS_OPTIONS**: Each simulated user gets assigned a frame rate chosen randomly from `[45, 60, 72, 90, 120]` frames per second.
- **MAX_FRAMES**: The simulation collects data for up to `1000` continuous video frames per user.
- **SIM_TIME_LIMIT**: Each simulation run allows for `35` seconds of simulated time.
- **NUM_USERS_SWEEP**: The orchestrator performs a user sweep, starting from `2` simultaneous users up to `10`.

### CLI Arguments
- `--mode`: Selects the source data type used for the simulation (`pca` or `ae`).
- `--repetitions`: Designates the number of times to simulate a specific user count (default is `3` runs per user count configuration).
- `--sim-time`: Override the simulated time limit.
- `--seed`: Base random seed for assigning parameters reproducibly.

---

## 3. High-Level Workflow

The script executes in three distinct phases:

### Phase 1: Video and Parameter Assignment (`assign_videos`, `assign_fps`)
Before any simulations occur, the script iterates through the user configurations (e.g., $N$ users, Repetition $R$):
1. **Video Assignment**: The available traffic files (which contain pre-processed frame sizes based on PCA or AE dimensionality reduction) are shuffled and cyclically distributed among the $N$ simulated users.
2. **FPS Assignment**: A frame rate is randomly selected from the `FPS_OPTIONS` for every user. 
3. **Configurations Generation**: Combinations (jobs) of the number of users, their repetition index, video, and FPS assignments are structured to be dispatched in Phase 2.

### Phase 2: Parallel Simulation Execution (`run_simulation`)
The prepared configurations are scheduled across a `multiprocessing.Pool` sized dynamically up to `32` workers (depending on CPU count) for maximum efficiency.

For each simulation job:
- A run-specific directory is generated: `results/dataset_n{num_users}_r{rep}`.
- A command to run the `simu5g` executable is constructed. Command-line parameters push specific overrides to `omnetpp.ini` (e.g., `--*.ue[*].app[0].pcaFile="..."`, `--*.server.numApps={num_users}`).
- The script uses the `XR-DL-RandomCL` configuration context to invoke randomized compression selection during runtime.
- The standard output and tracking of the simulation are sent into `sim.log`, while the results per user are dropped into `user_{i}.csv` within the local run directory.
- The process is highly fault-tolerant; failing or stalling simulations are elegantly handled through strict timeouts.

### Phase 3: Data Collection and Assembly (`collect_run_results`)
Once all simulations finish, their raw output `.csv` files are parsed and stitched together:
1. Valid frames (frame 1 to `MAX_FRAMES`) are targeted. 
2. The script isolates only "fully-synchronous" frames where **every** user present in that simulation successfully records data for that frame sequence number. 
3. Relevant telemetry is captured per user:
   - `components`: Used compression level / PCA components.
   - `effectiveError`: The mathematical error from utilizing that specific compression.
   - `delay_ms`: Complete transmission delay.
   - `cqi`: The downlink instantaneous Channel Quality Indicator available at frame dispatch.
   - `frame_rate`: Assigned frame rate.
   - `video`: Which video the user was streaming.
4. Additional simulation metadata such as `num_users` and `repetition` are affixed to the rows.

---

## 4. Derived Output Dataset Structure

The final dataset is consolidated and saved into:  
`datasets/pca/dataset.csv` (or `datasets/ae/dataset.csv`, matching the modes).

The columns are strictly ordered to offer an AI model accessible ingestion form:
1. `frameNumber`: Monotonically increasing ID representing the timeframe.
2. `repetition`: Run repetition seed offset.
3. Per-User Block (`userX_...` for $X \in [0, N-1]$):
   - `userX_components`
   - `userX_effectiveError`
   - `userX_delay_ms`
   - `userX_cqi`
   - `userX_frame_rate`
4. `num_users`: Useful to identify the overall load (and to prune columns representing users $\geq$ `num_users`).

By aggregating millions of parameters spanning multiple parallel connections simultaneously varying their compression and frame delays, this CSV comprehensively encapsulates a real-world multi-user networking environment for offline training reinforcement learning or heuristic engines.
