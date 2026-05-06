# PCA Video Compression Pipeline

This document provides a detailed overview of the Principal Component Analysis (PCA) video compression pipeline located in the `compression/pca/` directory.

## 1. Overview
The PCA pipeline dynamically measures the storage bandwidth and reconstruction quality trade-offs for XR video frames when projected onto varying numbers of PCA components. This mechanism replaces raw frame transmission with optimized coefficient transmission, significantly dropping frame payloads while incurring mathematical reconstruction error (MSE). 

The entry point for this process is `pca.py`, which delegates execution to linearly defined steps in `main.py`.

---

## 2. Pipeline Execution Steps

### 1. Video and Metadata Parsing
The script targets pre-recorded 360-degree XR videos (e.g., `billiards.mp4`). It immediately reads generic metadata attributes such as the raw width, height, and overall frame count. 
Additionally, utilizing an integrated `ffprobe` abstraction, it traces the actual baseline *encoded bitstream size* for every encoded frame to establish a benchmark.

### 2. Training Data Extraction
Instead of fitting the PCA on all frames, a distinct subset proportion defined by `--train-ratio` is chosen strictly for fitting. These specific frames are loaded into memory and pre-processed:
- Each frame is scaled to a standard working analytical resolution (defaulting to `224x224` to ensure mathematical parity if contrasted against Autoencoder evaluations).
- Frames are normalized from `uint8 [0, 255]` to `float32 [0.0, 1.0]` values.

### 3. Incremental PCA Fitting (`PCACompressor`)
Applying standard PCA to thousands of frames concurrently causes memory exhaustion. The pipeline tackles this via `sklearn.decomposition.IncrementalPCA`, located within `models.py`. 
- **Flattening**: The standardized frames of shape `(224, 224, 3)` are flattened into gigantic feature vectors of length `150,528` (`H * W * C`).
- **Batching**: The compressor ingests the training frames using predefined chunks (`batch_size=100`), iteratively learning the global frame mean and discovering the top $N$ principal components up to `--max-components` (typically 80).

### 4. Continuous Streaming Evaluation (`evaluate_compression`)
Following a successful fit, the pipeline sweeps across the segregated testing frames. Critically, to preserve memory, this is handled as a streaming pipeline where **only one frame** resides in isolated memory at a time.
For each frame, the system performs validation matching component counts (`K ∈ {5, 10, ..., 80}`):

1. **Projection**: It zeroes out the image mean and applies the dot product against the learned `K` components, harvesting `K` coefficients.
2. **Reconstruction**: It multiplies the coefficients against the transposed basis to reform the image and adds back the image mean.
3. **Clipping**: The reconstructed matrix is bounded rigidly against `[0, 1]` constraints and reshaped back into visual dimensions.

### 5. Mathematical Metric Calculation
For each frame-to-components run, specific simulation and machine learning metrics are computed and captured:
- **`mse` (Mean Squared Error)**: Computed dynamically between the reconstructed tensor and the uncompressed raw test frame (scaled back to the `[0, 255]` boundary logic).
- **`size_bytes`**: Represents the bytes pushed to the network. Calculated heavily reflecting actual transmission costs:
  - Takes the size of the transmitted coefficients (`4 bytes * K`).
  - Implements an *amortization constant* to factor in the one-time network transmission expense of deploying the learned PCA foundation block (basis vector subset + frame mean array) averaged over the entirety of the video stream.
- **`error_at_k80` and `error_ratio`**: Specific macro properties evaluated exclusively at $K=80$ and their scaling gap vs $K=5$, fundamentally exported to operate as state labels indicating current stream complexity for the eventual AI model grid-search.

### 6. Results Export
The accumulated metrics are outputted securely to two primary destinations:
1. **Summary CSV (`pca_sweep_summary.csv`)**: Holds all discrete frame measurements utilized directly within network simulations.
2. **Visualization (`pca_compression_analysis.png`)**: Immediately graphs and plots the generated performance curve detailing $MSE$ vs. $Components$.
