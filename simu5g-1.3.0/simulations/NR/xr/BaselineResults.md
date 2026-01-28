# XR over 5G NR Simulation Results

## Simulation Setup

| Parameter         | Value                  |
| ----------------- | ---------------------- |
| System Bandwidth  | 100 MHz                |
| Numerology        | μ=1 (30 kHz SCS)       |
| Resource Blocks   | 273                    |
| Carrier Frequency | 2.4 GHz                |
| Channel Model     | Flat Rayleigh Fading   |
| Scheduler         | PF (Proportional Fair) |
| Deployment Area   | 250m × 250m            |

### XR Traffic Model

| Parameter             | Value    |
| --------------------- | -------- |
| Frame Rate            | 60 fps   |
| Mean Frame Size       | 62.5 KB  |
| Min Frame Size        | 23 KB    |
| Max Frame Size        | 92.8 KB  |
| Per-UE Data Rate      | ~30 Mbps |
| Reliability Threshold | 99%      |

---

## Results: 2.5ms Delay Bound

| Metric         | Value      |
| -------------- | ---------- |
| Total Frames   | 1200       |
| On-time Frames | 56 (4.67%) |
| Average Delay  | 2.82 ms    |
| User Satisfied | **NO**     |

> **Finding**: With a 2.5ms delay bound, even a single XR user cannot achieve 99% delay reliability. Only 4.67% of frames meet the deadline.

---

## Results: 5ms Delay Bound

| Users | Satisfied Users | Global Delay Reliability |
| ----- | --------------- | ------------------------ |
| 1     | 1/1 ✅          | 100%                     |
| 2     | 2/2 ✅          | 100%                     |
| 3     | 3/3 ✅          | 99.97%                   |
| 4     | 4/4 ✅          | 99.75%                   |
| 5     | 5/5 ✅          | 99.65%                   |
| 6     | 2/6 ❌          | 98.76%                   |
| 7     | 0/7 ❌          | 98.27%                   |
| 8     | 0/8 ❌          | 97.02%                   |

> **Finding**: With a 5ms delay bound, up to 5 XR users can be supported with 99% delay reliability. At 6+ users, the system becomes overloaded.

---

## Key Conclusions

1. **2.5ms deadline is infeasible**: The average delay (~2.82ms) exceeds the 2.5ms threshold, making it impossible to achieve 99% reliability even for a single user.

2. **5ms deadline capacity**: With a relaxed 5ms deadline, 5G NR can support approximately **5 XR users** per cell at 30 Mbps each.

3. **Capacity cliff**: System performance degrades rapidly beyond 5 users, with no users meeting the 99% threshold at 7+ users.

---

## Running Simulations

```bash
cd /home/satyam/Desktop/NASCX && ./opp_shell.sh
# Inside the shell:
cd simu5g-1.3.0/simulations/NR/xr

# Single user with 2.5ms deadline (default)
simu5g -r 0 -m -u Cmdenv -c XR-DL-SingleUser omnetpp.ini

# Single user with 5ms deadline
simu5g -r 0 -m -u Cmdenv -c XR-DL-SingleUser --*.ue[*].app[0].deadlineMs=5ms omnetpp.ini

# Multi-user sweep
simu5g -r 0 -m -u Cmdenv -c XR-DL-MultiUser-PF --*.numUe=5 --*.server.numApps=5 omnetpp.ini
```

## Available Configurations

| Config                   | Description                       |
| ------------------------ | --------------------------------- |
| `XR-DL-SingleUser`       | Single user baseline              |
| `XR-DL-MultiUser-PF`     | Multi-user with PF scheduler      |
| `XR-DL-MultiUser-MaxCQI` | Multi-user with MAX-CQI scheduler |
| `XR-DL-UserSweep`        | Parametric user sweep (1-10)      |
