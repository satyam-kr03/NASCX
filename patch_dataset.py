import sys

filename = '/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/dataset_generation/generate_dataset.py'
with open(filename, 'r') as f:
    content = f.read()

# Replace run_simulation to include prescribed generation
old_run_sim = """def run_simulation(args):
    \"\"\"Run one simulation for a given (num_users, repetition) pair.
    
    This function is called by the multiprocessing pool.
    \"\"\"
    num_users, repetition, video_assignments, fps_assignments, traffic_paths, run_dir, sim_time = args
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "simu5g",
        "../omnetpp.ini",
        "-u", "Cmdenv",
        "-c", "XR-DL-RandomCL",
        f"--sim-time-limit={sim_time}s",
        f"--seed-set={repetition}",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
    ]
    
    # Add per-user overrides
    for i in range(num_users):
        video = video_assignments[i]
        fps = fps_assignments[i]
        pca_rel = os.path.relpath(traffic_paths[video], SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")
        # String values must be quoted for OMNeT++ command-line parsing
        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")"""

new_run_sim = """def run_simulation(args):
    \"\"\"Run one simulation for a given (num_users, repetition) pair.
    
    This function is called by the multiprocessing pool.
    \"\"\"
    num_users, repetition, video_assignments, fps_assignments, traffic_paths, run_dir, sim_time = args
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # --- Generate Prescribed CSVs for Correlated Exploration ---
    import random
    rng = random.Random(repetition + num_users * 1000)
    
    # Determine type of run
    # Let rep 0-15 be static runs (CL 5, 10, ..., 80)
    # The rest are correlated random
    is_static = False
    static_level = 5
    if repetition < 16:
        is_static = True
        static_level = 5 + repetition * 5

    MAX_COMPONENTS = 80
    MIN_COMPONENTS = 5
    STEP = 5
    
    user_schedules = {i: [] for i in range(num_users)}
    for frame_id in range(1, MAX_FRAMES + 200):
        if is_static:
            for i in range(num_users):
                user_schedules[i].append((frame_id, static_level))
        else:
            # Correlated random: pick a base level for the whole network
            # Then add noise per user
            base_cl = rng.choice(range(MIN_COMPONENTS, MAX_COMPONENTS + 1, STEP))
            for i in range(num_users):
                noise = rng.choice([-10, -5, 0, 5, 10])
                user_cl = base_cl + noise
                # Bound to valid range and align to nearest step
                user_cl = max(MIN_COMPONENTS, min(MAX_COMPONENTS, user_cl))
                user_cl = round(user_cl / STEP) * STEP
                user_schedules[i].append((frame_id, user_cl))
                
    for i in range(num_users):
        presc_file = run_dir / f"prescribed_{i}.csv"
        with open(presc_file, "w") as pf:
            pf.write("frame,components\\n")
            for frame_id, cl in user_schedules[i]:
                pf.write(f"{frame_id},{cl}\\n")
    # ---------------------------------------------------------
    
    cmd = [
        "simu5g",
        "../omnetpp.ini",
        "-u", "Cmdenv",
        "-c", "XR-DL-RandomCL",
        f"--sim-time-limit={sim_time}s",
        f"--seed-set={repetition}",
        f"--*.numUe={num_users}",
        f"--*.server.numApps={num_users}",
    ]
    
    # Add per-user overrides
    for i in range(num_users):
        video = video_assignments[i]
        fps = fps_assignments[i]
        pca_rel = os.path.relpath(traffic_paths[video], SCRIPT_DIR)
        result_file = str(run_dir / f"user_{i}.csv")
        presc_rel = os.path.relpath(run_dir / f"prescribed_{i}.csv", SCRIPT_DIR)
        
        # String values must be quoted for OMNeT++ command-line parsing
        cmd.append(f'--*.server.app[{i}].pcaFile="{pca_rel}"')
        cmd.append(f'--*.server.app[{i}].fps={fps}')
        cmd.append(f'--*.ue[{i}].app[0].pcaFile="{pca_rel}"')
        cmd.append(f'--*.ue[{i}].app[0].resultFile="{result_file}"')
        cmd.append(f"--*.ue[{i}].app[0].expectedFrames={MAX_FRAMES}")
        
        # Override to use prescribed schedule
        cmd.append(f'--*.server.app[{i}].selectionMode="prescribed"')
        cmd.append(f'--*.server.app[{i}].prescribedFile="{presc_rel}"')"""

content = content.replace(old_run_sim, new_run_sim)
with open(filename, 'w') as f:
    f.write(content)
print("generate_dataset run_sim updated")
