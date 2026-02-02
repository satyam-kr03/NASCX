# Error-Aware Proportional Fair Scheduler

This document describes the **Error-Aware Proportional Fair (Error-Aware PF)** scheduler integrated into Simu5G for XR traffic optimization. It includes a complete guide for integrating custom schedulers and detailed specifications of the Error-Aware PF algorithm.

---

## Table of Contents

1. [Overview](#overview)
2. [Integrating a New Scheduler in Simu5G](#integrating-a-new-scheduler-in-simu5g)
   - [Step 1: Define the Scheduler Enum](#step-1-define-the-scheduler-enum)
   - [Step 2: Create Header File](#step-2-create-header-file)
   - [Step 3: Create Implementation File](#step-3-create-implementation-file)
   - [Step 4: Register Scheduler in Factory](#step-4-register-scheduler-in-factory)
   - [Step 5: Add NED Parameters](#step-5-add-ned-parameters)
   - [Step 6: Regenerate Makefile and Build](#step-6-regenerate-makefile-and-build)
   - [Step 7: Configure in omnetpp.ini](#step-7-configure-in-omnetppini)
3. [Error-Aware PF Scheduler Specification](#error-aware-pf-scheduler-specification)
   - [Motivation](#motivation)
   - [Algorithm Overview](#algorithm-overview)
   - [Score Computation](#score-computation)
   - [EMA Normalization](#ema-normalization)
   - [Configuration Parameters](#configuration-parameters)
4. [XR Metrics Integration](#xr-metrics-integration)
5. [Results](#results)

---

## Overview

The Error-Aware PF scheduler extends the standard Proportional Fair scheduler by incorporating application-layer quality metrics (MSE/RMSE) into scheduling decisions. This enables the scheduler to prioritize users experiencing higher reconstruction error, improving overall XR Quality of Experience (QoE).

---

## Integrating a New Scheduler in Simu5G

This section provides a step-by-step guide for integrating a custom scheduler into the Simu5G framework.

### Step 1: Define the Scheduler Enum

Add a new enum value for your scheduler in the scheduling discipline enum.

**File:** `src/common/LteCommon.h`

```cpp
// Add to the SchedDiscipline enum
enum SchedDiscipline {
    DRR,
    PF,
    MAXCI,
    MAXCI_MB,
    MAXCI_OPT_MB,
    MAXCI_COMP,
    ALLOCATOR_BESTFIT,
    ERROR_AWARE_PF,    // <-- Add your new scheduler here
    UNKNOWN_DISCIPLINE
};
```

**File:** `src/common/LteCommonEnum.msg`

Add the enum to the message file so it can be used in NED:

```msg
enum SchedDiscipline {
    DRR = 1;
    PF = 2;
    MAXCI = 3;
    MAXCI_MB = 4;
    MAXCI_OPT_MB = 5;
    MAXCI_COMP = 6;
    ALLOCATOR_BESTFIT = 7;
    ERROR_AWARE_PF = 8;    // <-- Add your new scheduler here
};
```

### Step 2: Create Header File

Create a header file for your scheduler class.

**File:** `src/stack/mac/scheduling_modules/LteErrorAwarePf.h`

```cpp
#ifndef _LTE_ERROR_AWARE_PF_H_
#define _LTE_ERROR_AWARE_PF_H_

#include "stack/mac/scheduling_modules/LtePf.h"

namespace simu5g
{

class LteErrorAwarePf : public LtePf
{
protected:
    // Scheduler-specific member variables
    bool useLogScaling_;
    bool enableErrorAwareScheduling_;
    double beta_;   // Weight for base PF score
    double gamma_;  // Weight for RMSE

public:
    // Constructor with parameters
    LteErrorAwarePf(Binder *binder, double pfAlpha = 0.95, 
                    double beta = 0.6, double gamma = 0.4);

    // Virtual destructor for proper polymorphic behavior
    virtual ~LteErrorAwarePf() = default;

    // Override the scheduling method
    virtual void prepareSchedule() override;
    
    // Custom score computation
    virtual double computeScore(MacCid cid, unsigned int availableBytes,
                                unsigned int availableBlocks, MacNodeId nodeId);
};

} // namespace simu5g

#endif
```

**Key Points:**
- Inherit from an existing scheduler (e.g., `LtePf`) to reuse common functionality
- Declare member variables for configurable parameters
- Add a **virtual destructor** to ensure proper cleanup in polymorphic contexts
- Override `prepareSchedule()` which is the main scheduling entry point

### Step 3: Create Implementation File

Implement your scheduler logic.

**File:** `src/stack/mac/scheduling_modules/LteErrorAwarePf.cc`

```cpp
#include "stack/mac/scheduling_modules/LteErrorAwarePf.h"
#include "stack/mac/scheduler/LteSchedulerEnb.h"
#include "common/binder/Binder.h"

namespace simu5g
{

using namespace omnetpp;

void LteErrorAwarePf::prepareSchedule()
{
    // Read parameters from NED (optional - can also use constructor values)
    cModule *schedulerModule = eNbScheduler_->mac_->getParentModule()
                                   ->getSubmodule("mac")
                                   ->getSubmodule("scheduler");
    
    if (schedulerModule != nullptr)
    {
        beta_ = schedulerModule->par("errorAwareBeta").doubleValue();
        gamma_ = schedulerModule->par("errorAwareGamma").doubleValue();
        // ... read other parameters
    }

    // Clear structures
    grantedBytes_.clear();
    activeConnectionTempSet_ = *activeConnectionSet_;

    // Build score list for active connections
    ScoreList score;
    
    for (const auto &cid : carrierActiveConnectionSet_)
    {
        // ... compute score for each connection
        double s = computeScore(cid, availableBytes, availableBlocks, nodeId);
        ScoreDesc desc(cid, s);
        score.push(desc);
    }

    // Grant resources in score order
    while (!score.empty())
    {
        ScoreDesc current = score.top();
        MacCid cid = current.x_;
        
        bool terminate = false;
        bool active = true;
        bool eligible = true;

        unsigned int granted = requestGrant(cid, 4294967295U, terminate, active, eligible);
        grantedBytes_[cid] += granted;

        if (terminate) break;
        if (!active || !eligible) score.pop();
        if (!active)
        {
            activeConnectionTempSet_.erase(current.x_);
            carrierActiveConnectionSet_.erase(current.x_);
        }
    }
}

double LteErrorAwarePf::computeScore(MacCid cid, unsigned int availableBytes,
                                     unsigned int availableBlocks, MacNodeId nodeId)
{
    // Compute base PF score
    double baseScore = /* ... */;
    
    // Get application-layer metrics from Binder
    const XRMetrics *xrMetrics = binder_->getXRMetrics(nodeId);
    
    if (xrMetrics == nullptr)
        return baseScore;  // Fallback to standard PF
    
    // Incorporate RMSE into score
    double rmse = sqrt(xrMetrics->mse);
    
    // Combine scores with configurable weights
    double finalScore = beta_ * baseScore + gamma_ * rmse;
    
    return finalScore;
}

} // namespace simu5g
```

### Step 4: Register Scheduler in Factory

Add your scheduler to the factory method and declare friendship if accessing private members.

**File:** `src/stack/mac/scheduler/LteSchedulerEnb.h`

```cpp
class LteSchedulerEnb
{
    // Add friend declaration if your scheduler needs access to private members
    friend class LteErrorAwarePf;
    
    // ... existing code
};
```

**File:** `src/stack/mac/scheduler/LteSchedulerEnb.cc`

Add include and factory case:

```cpp
#include "stack/mac/scheduling_modules/LteErrorAwarePf.h"

LteScheduler* LteSchedulerEnb::getScheduler(SchedDiscipline discipline)
{
    switch (discipline)
    {
        // ... existing cases
        
        case ERROR_AWARE_PF:
            return new LteErrorAwarePf(binder_,
                               mac_->par("pfAlpha").doubleValue(),
                               mac_->par("errorAwareBeta").doubleValue(),
                               mac_->par("errorAwareGamma").doubleValue());
        
        default:
            throw cRuntimeError("LteScheduler not recognized");
    }
}
```

### Step 5: Add NED Parameters

Define configurable parameters in the MAC NED file.

**File:** `src/stack/mac/LteMacEnb.ned`

```ned
simple LteMacEnb extends LteMacBase
{
    parameters:
        // ... existing parameters
        
        // Scheduling discipline enum - add your scheduler
        string schedulingDisciplineDl @enum(DRR,PF,MAXCI,...,ERROR_AWARE_PF) = default("MAXCI");
        string schedulingDisciplineUl @enum(DRR,PF,MAXCI,...,ERROR_AWARE_PF) = default("MAXCI");
        
        // Proportional Fair parameters
        double pfAlpha = default(0.95);

        // Error-Aware PF Scheduler parameters
        double errorAwareBeta = default(0.6);    // Weight for base PF score
        double errorAwareGamma = default(0.4);   // Weight for RMSE
        bool errorAwareUseLogScaling = default(true);
        bool errorAwareEnableScheduling = default(true);
}
```

### Step 6: Regenerate Makefile and Build

After adding new source files, regenerate the Makefile and rebuild:

```bash
cd /path/to/simu5g
make makefiles           # Regenerate Makefile to include new .cc files
make MODE=release -j32   # Build with 32 cores
```

> **Important:** If you add new `.cc` files without running `make makefiles`, they won't be compiled and you'll get "undefined symbol" errors at runtime.

### Step 7: Configure in omnetpp.ini

Use your scheduler in simulation configurations:

```ini
[Config MySimulation]
# Select your scheduler
**.gnb.cellularNic.mac.schedulingDisciplineDl = "ERROR_AWARE_PF"

# Configure scheduler parameters
**.mac.errorAwareBeta = 0.6
**.mac.errorAwareGamma = 0.4
**.mac.errorAwareUseLogScaling = true
**.mac.errorAwareEnableScheduling = true
```

---

## Error-Aware PF Scheduler Specification

### Motivation

Traditional schedulers (PF, Max-CQI, Round Robin) make decisions based solely on radio channel conditions and fairness metrics. For XR applications, this is insufficient because:

1. **XR frames have varying importance** - High-error frames may need prioritization
2. **Quality is application-dependent** - MSE/RMSE directly impacts visual quality
3. **Deadline-sensitive** - XR requires consistent low latency

The Error-Aware PF scheduler addresses these by incorporating application-layer metrics into scheduling decisions.

### Algorithm Overview

The Error-Aware PF scheduler follows this workflow:

```
┌─────────────────────────────────────────────────────────┐
│                    prepareSchedule()                     │
├─────────────────────────────────────────────────────────┤
│  1. Load configuration parameters from NED              │
│  2. Clear previous scheduling state                     │
│  3. For each active connection:                         │
│     a. Compute base PF score                            │
│     b. Retrieve XR metrics (MSE, size) from Binder      │
│     c. Apply EMA normalization                          │
│     d. Compute weighted final score                     │
│  4. Sort connections by score (priority queue)          │
│  5. Grant resources in score order until exhausted      │
└─────────────────────────────────────────────────────────┘
```

### Score Computation

The final score for each connection is computed as:

```
finalScore = β × normBase + γ × normRMSE + (1-β-γ) × normSize
```

Where:
- **β (beta)**: Weight for base PF score (default: 0.6)
- **γ (gamma)**: Weight for RMSE component (default: 0.4)
- **normBase**: Normalized base PF score
- **normRMSE**: Normalized RMSE value
- **normSize**: Normalized frame size

**Base PF Score:**
```
baseScore = (availableBytes / availableBlocks) / pfRate[cid]
```

**Log Scaling (optional):**
When enabled, values are transformed using `log1p()` before normalization:
```
rmseVal = log(1 + rmse)
sizeVal = log(1 + sizeBytes)
baseVal = log(1 + max(baseScore, 0))
```

### EMA Normalization

To handle varying scales across different metrics, an Exponential Moving Average (EMA) based normalization is applied:

**EMA Update:**
```
newMean = α × value + (1 - α) × prevMean
newVar = α × (value - newMean)² + (1 - α) × prevVar
```

**Z-Score Normalization:**
```
zScore = (value - mean) / sqrt(variance)
```

**Bootstrap Mode:**
When variance is too small (< 0.01), the raw scaled value is used instead of z-score to avoid instability during warmup.

**Parameters:**
- EMA smoothing factor (α): 0.12
- Per-CID state tracking for mean and variance

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `errorAwareBeta` | double | 0.6 | Weight for base PF score component |
| `errorAwareGamma` | double | 0.4 | Weight for RMSE component |
| `errorAwareUseLogScaling` | bool | true | Apply log1p transformation to metrics |
| `errorAwareEnableScheduling` | bool | true | Enable/disable error-aware scheduling |

---

## XR Metrics Integration

The scheduler retrieves XR metrics from the **Binder** module, which serves as a central registry accessible to all network components.

### Binder Interface

**Setting Metrics (from XRTrafficSource):**
```cpp
void Binder::setXRMetrics(MacNodeId nodeId, double mse, uint32_t sizeBytes);
```

**Getting Metrics (from Scheduler):**
```cpp
const XRMetrics* Binder::getXRMetrics(MacNodeId nodeId);
```

### XRMetrics Structure

```cpp
struct XRMetrics {
    double mse;          // Mean Squared Error of the frame
    uint32_t sizeBytes;  // Frame size in bytes
    simtime_t timestamp; // When metrics were set
};
```

### Data Flow

```
┌──────────────────┐         ┌────────────┐         ┌─────────────────────┐
│  XRTrafficSource │ ──────► │   Binder   │ ◄────── │  LteErrorAwarePf    │
│  (Application)   │ setXR   │  (Registry)│  getXR  │    (Scheduler)      │
│                  │ Metrics │            │ Metrics │                     │
└──────────────────┘         └────────────┘         └─────────────────────┘
```

---

## Results

*Results from experiments comparing Error-Aware PF with standard schedulers will be added here.*

### Planned Experiments

1. **Baseline Comparison**
   - Compare Error-Aware PF vs Standard PF vs Max-CQI
   - Metrics: Delay reliability, Mean Error, User satisfaction rate

2. **Parameter Sensitivity**
   - Vary β and γ weights
   - Evaluate impact on QoE

3. **Scalability Analysis**
   - Test with 2-10 concurrent users
   - Measure capacity limits

### Results Table (Placeholder)

| Scheduler | Users | Delay Reliability | Mean Error | Satisfied Users |
|-----------|-------|-------------------|------------|-----------------|
| PF | 2 | - | - | - |
| Max-CQI | 2 | - | - | - |
| Error-Aware PF | 2 | - | - | - |

---

## References

1. Simu5G Documentation: https://simu5g.org/
2. OMNeT++ Simulation Manual
3. 3GPP TR 26.926 - Traffic Models and Quality Evaluation Methods for Media Distribution over 5G

---

*Document Version: 1.0*  
*Last Updated: February 2026*
