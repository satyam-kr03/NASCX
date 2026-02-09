# Generic Simu5G Dataset Generation Guide

## Overview

This guide describes a **simple methodology** for generating datasets from OMNeT++/Simu5G simulations:

1. **C++ CSV Logging** — Write simulation metrics directly to CSV files from your OMNeT++ module
2. **Python Script** — Run simulations and aggregate results

---

## Step 1: Add CSV Logging to Your C++ Module

### Basic CSV Writer Implementation

```cpp
// In your module header (YourModule.h)
#include <fstream>
#include <string>

class YourModule : public cSimpleModule {
  private:
    std::ofstream csvFile;
    std::string csvFilePath;
    
  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    virtual void finish() override;
};
```

### Writing to CSV

```cpp
// In your module implementation (YourModule.cc)

void YourModule::initialize() {
    csvFilePath = par("csvOutputFile").stringValue();
    if (!csvFilePath.empty()) {
        csvFile.open(csvFilePath);
        csvFile << "timestamp,packet_id,delay_ms,cqi" << std::endl;
    }
}

void YourModule::handleMessage(cMessage *msg) {
    // Process message and compute metrics
    // ...
    
    // Log to CSV
    if (csvFile.is_open()) {
        csvFile << simTime().dbl() << ","
                << packetId << ","
                << delayMs << ","
                << currentCqi << std::endl;
    }
}

void YourModule::finish() {
    if (csvFile.is_open()) {
        csvFile.close();
    }
}
```

### NED Parameter Declaration

```ned
simple YourModule {
    parameters:
        string csvOutputFile = default("");
}
```

---

## Step 2: Configure omnetpp.ini

```ini
[Config DatasetGeneration]
sim-time-limit = 20s
*.yourModule.csvOutputFile = "user_results.csv"
*.numUsers = 5
```

---

## Step 3: Python Script

### Simple Template

```python
#!/usr/bin/env python3
"""
Simple Simu5G Dataset Generator
"""

import csv
import random
import subprocess
import shutil
from pathlib import Path

SIMULATION_DIR = Path(__file__).parent
OUTPUT_FILE = SIMULATION_DIR / "dataset.csv"

# Parameter space
NUM_USERS_RANGE = range(2, 11)
PARAM_VALUES = [10, 20, 30, 40, 50]


def run_simulation(num_users, param_value, run_id):
    """Run a single simulation and return results."""
    
    cmd = [
        "simu5g", "-r", "0", "-m", "-u", "Cmdenv", "-c", "DatasetGeneration",
        f"--*.numUsers={num_users}",
        f"--*.yourModule.someParameter={param_value}",
        "omnetpp.ini"
    ]
    
    try:
        result = subprocess.run(cmd, cwd=SIMULATION_DIR, 
                                capture_output=True, text=True, timeout=600)
        
        # Parse results from CSV written by C++ module
        csv_path = SIMULATION_DIR / "user_results.csv"
        results = []
        
        if csv_path.exists():
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    results.append({
                        'run_id': run_id,
                        'num_users': num_users,
                        'param_value': param_value,
                        **row  # Include all columns from CSV
                    })
            csv_path.unlink()  # Clean up
        
        return {'success': result.returncode == 0, 'results': results}
        
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def generate_dataset(num_runs=10, seed=42):
    """Generate dataset by running simulations."""
    random.seed(seed)
    
    all_results = []
    run_id = 0
    
    for num_users in NUM_USERS_RANGE:
        for param_value in PARAM_VALUES:
            for _ in range(num_runs):
                run_id += 1
                
                result = run_simulation(num_users, param_value, run_id)
                
                if result['success']:
                    all_results.extend(result['results'])
                    print(f"Run {run_id}: OK")
                else:
                    print(f"Run {run_id}: FAILED")
    
    # Save all results
    if all_results:
        fieldnames = list(all_results[0].keys())
        with open(OUTPUT_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\nDone! {len(all_results)} rows saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_dataset(num_runs=10, seed=42)
```

---

## Step 4: Running

```bash
cd /path/to/simulations/NR/your_scenario

# Run dataset generation
python3 generate_dataset.py
```

For long runs:
```bash
nohup python3 generate_dataset.py > generation.log 2>&1 &
tail -f generation.log
```

---

## What to Log

You can log **any value** accessible in your C++ code:

- Per-packet metrics (delay, jitter, loss)
- Per-frame metrics (for video/XR applications)
- Channel conditions (CQI, SINR, RSRP)
- Application-level metrics (throughput, QoE)

---

## Example: Per-Packet Logging

```cpp
void TrafficReceiver::handleMessage(cMessage *msg) {
    Packet *pkt = check_and_cast<Packet *>(msg);
    
    simtime_t delay = simTime() - pkt->getCreationTime();
    int packetSize = pkt->getByteLength();
    
    if (csvFile.is_open()) {
        csvFile << simTime().dbl() << ","
                << pkt->getId() << ","
                << delay.dbl() * 1000 << ","  // ms
                << packetSize << std::endl;
    }
    
    delete msg;
}
```

---

## Summary

1. **Add CSV logging** to your C++ module using `std::ofstream`
2. **Configure output path** via NED/INI parameters  
3. **Write a Python script** that runs simulations and aggregates CSV files
4. **Run** and collect your dataset
