# XR Custom Application Modules

This document outlines the custom C++ OMNeT++/Simu5G application modules developed to simulate variable-compression XR (Extended Reality) video streaming over 5G networks.

The core logic is structured across three main components: a custom message header, a traffic source (server), and a traffic receiver (UE block).

---

## 1. Custom Packet Header (`XRHeader.msg`)
The network simulation utilizes a custom INET packet header, `XRHeader`, extending `inet::FieldsChunk`. It encapsulates crucial simulation telemetry within every packet traversing the network stack:
- **`frameNumber`**: The sequential video frame ID.
- **`pcaComponents`**: The number of compression components driving this frame's size.
- **`mse`**: The theoretical reconstruction error of the frame.
- **`sizeBytes`**: The unfragmented logical size of the entire frame payload.
- **`genTime`**: Accurate simulation timestamp when the source dispatched the frame.
- **`fragIndex` / `totalFragments`**: Metadata to manage internal UDP payload fragmentation.

---

## 2. Traffic Generator (`XRTrafficSource.cc`)
Residing typically on the network edge server, this module generates realistic downlink video transmission workloads. 

### Pre-computation and Jitter
Unlike simple constant-bitrate generators, the source loads actual pre-computed trace data (`pcaFile`). It parses the massive CSV correlating `frame_number`, `components`, `size_bytes`, and `mse`. Frame generation times are modeled using a strict base FPS frequency plus an applied truncated-Gaussian jitter.

### Compression Selection Modes
The defining feature of the source is how it assigns a component level before transmitting a frame:
1. **`fixed`**: Statically assigns the identical compression level to every frame across the simulation.
2. **`random`**: Randomly chooses a valid compression level—perfect for generating diverse exploratory dataset regimes.
3. **`prescribed`**: Locks onto a pre-determined schedule mapping specific frame sequences to exact levels.
4. **`model`**: Connects via HTTP (using direct `wget` system calls) to an external Python API running a Machine Learning model. It evaluates live channel statistics stored in the simulation `Binder` and adopts the optimal real-time compression level dynamically suggested.

### Fragmentation Layer
Because complete XR frames (exceeding hundreds of KB) massively bypass standard network MTU thresholds, the source splits the total `size_bytes` against a `maxPayloadSize` variable, dispatching independent UDP packets for each fragment while seamlessly duplicating the `XRHeader` sequentially.

---

## 3. Traffic Sink & Evaluator (`XRTrafficReceiver.cc` / `.h`)
Residing directly within the User Equipment (UE) simulation context, the receiver reconstructs the fragmented payload and performs definitive Quality of Experience (QoE) determinations.

### Fragment Reassembly
The receiver maintains an ongoing active `std::map` monitoring incoming fragments utilizing the `XRHeader`. A frame is recognized as officially "arrived" only when `fragmentsReceived == totalFragments`.

### Deadline Enforcement & Penalties
Critical for XR validity, merely receiving the frame is inadequate; it must arrive physically before a strict rendering threshold:
- **`delay`**: Calculated geometrically as `recvTime - genTime`.
- **`receivedOnTime`**: A boolean flag checking if the sequence beat the `deadlineMs`.
- **`effectiveError`**: The true QoE indicator. If the frame is successfully received *on-time*, the error equates to the mathematical `mse`. If the frame is late, drops fragments, or is lost in transmission blockages, the system replaces the error with `elostValue`—a devastating maximum penalty mathematically derived from the poorest compression configuration, signifying a completely dropped VR frame to the end-user.

### Cross-Layer Intelligence (CQI)
The receiver utilizes cross-layer OMNeT++ hooks to dynamically read the active Downlink Channel Quality Indicator (DL CQI) off the physical properties module (`nrPhy / LtePhyUe`). 
It continuously pushes this high-fidelity physical metric—along with realtime delay tracking—back into the generalized `Binder` system, allowing the remote `XRTrafficSource` to act intelligently on sub-millisecond shifting radio propagation horizons.

### Result Emission
The component generates multi-level summaries directly from C++ into runtime CSVs:
- Iterates over all generated bounds noting entirely dropped frames.
- Determines if the simulated UE exceeded its `reliabilityThreshold` (e.g., maintaining 99% on-time delivery constraints).
- Exports granular frame-by-frame data (`resultFile`) and macro user conclusions (`summaryFile`).
