# PCA-based Dimensionality Reduction for 360° XR Frames

## Overview
The PCA compression module provides a memory-efficient, streaming-based pipeline for controllable dimensionality reduction of high-dimensional 360° XR (Extended Reality) video frames. By applying incremental Principal Component Analysis (PCA) to flattened, resized image frames, the module establishes a set of basis vectors. These bases allow arbitrary compression levels (by truncating the number of retained principal components) while assessing reconstruction fidelity.

The primary objective is to evaluate the rate-distortion trade-off: comparing the transmitted data size (dictated by the number of principal components) versus the resulting mean squared error (MSE) relative to the source frames. This establishes a baseline for dynamic compression adaptation across evolving network conditions.

## Architecture

The compression module is systematically organized into five distinct components under the `pca/` package:

1. **`main.py`**: The CLI orchestration script bridging data extraction, model training, streaming evaluation, and storing final outputs.
2. **`data.py`**: Handles video metadata extraction, per-frame encoded bitstream sizing (via `ffprobe`), and memory-efficient streaming frame decoding strictly through `PyAV` and `OpenCV`.
3. **`models.py`**: Supplies the core `PCACompressor` class, a wrapper enveloping `sklearn.decomposition.IncrementalPCA`, purposefully optimized for sizable video datasets and out-of-core learning paradigms.
4. **`evaluate.py`**: The streaming evaluation engine iteratively compressing frames, computing distortion metrics (MSE), and allocating amortized overhead to size estimations simultaneously across various component count scenarios.
5. **`utils.py`**: Implements logging standardization, aggregates frame-metrics into expansive CSV datasets, and renders high-level visualizations via `matplotlib`.

## Core Mechanisms

### Data Extraction and Pre-processing
360° video manipulation places significant duress on memory environments due to uncompressed spatial sizes. The pipeline bypasses out-of-memory errors via:
- **Streaming Decode Allocation**: Frames instantiate sequentially (`_decode_frames`) instead of dumping entire containers into memory concurrently. 
- **Bilinear Resizing**: Every processed image shrinks immediately via `cv2.resize` to an internal working resolution demarcated by `img_size` (default `224x224`). This mitigates ambient vector dimensionality while conforming bounds identical to neural autoencoder alternatives.
- **Vector Normalization**: RGB arrays scale dynamically into `float32` vectors bounded across `[0, 1]`, finally subjected to contiguous 1-D flattening shaping (`N_Pixels` $= H \times W \times C$).

### Metadata Verification
`data.get_video_info` interfaces tightly with `ffprobe` binaries to furnish:
- **Verifiable Frame Metrics**: Prevents reliance on incomplete container headers common in transcoded web sources.
- **Reference Baselines**: Maps packet sizing alongside picture macroblock typologies (I, P, or B frames), building a contextual framework over FFmpeg compression against PCA configurations.

### Incremental PCA Fitting
Due to memory bottlenecks precluding holistic covariance algorithms, the module restricts footprint with out-of-core computation structures:
- The video separates mathematically utilizing a permutation ratio algorithm (`train_ratio = 0.15`). Memory only stores these pre-filtered arrays sequentially.
- The `PCACompressor.fit()` mechanism injects uniform batches (defaulting `100` frames) incrementally into real-time linear subspace modifications.
- Following eigenvector and mean stabilizations, raw test sets disintegrate via standard GC hooks (`del train_frames`), immediately freeing space for downstream analysis.

### Compression & Selective Expansion
The fundamental procedure within `compress_and_reconstruct` enforces representation limitation relative to a truncated `k`-degree component scale:
For a localized target frame vector $x$:
1. Offset centering against global means: $x' = x - \mu$
2. Subspace projection (compression to independent scalar coefficients): $c_k = x' \cdot V_k^T$
3. Rank-$k$ expansion (fidelity re-computation): $\tilde{x} = c_k \cdot V_k + \mu$
4. Output stability clamp via `np.clip(..., 0, 1)` bounds preventing out-of-gamut ranges.

### Streaming Evaluation Engine
Defined under `evaluate.evaluate_compression()`, validation cascades iteratively:
- The pipeline holds merely $\approx 1$ frame instance concurrently. 
- Metrics stream against varying configuration gradients defined by `DEFAULT_COMPONENTS` (`[400, 375... 25]`).
- Error derivation correlates standard pixel-domain **Mean Squared Error (MSE)** standardized against `[0-255]` boundaries.
- Output sizing calculates through exact float limits defined as:
  **(Dynamic Coefficients)** $k \times 4 \text{ Bytes} +$ **(Amortized Static Profile Overhead)** $((k+1) \times \text{N\_Pixels} \times 4 \text{ Bytes}) / \text{total\_frames}$.

### Visualization and Metric Storage
Through `.csv` exports and `plot_results()`, output graphs coalesce into dual-panel summaries emphasizing:
1. Frame-by-frame volatility delineating distinct PCA behavior versus complexity bounds.
2. Standardized temporal Rate-Distortion envelopes tracking asymptotic payload (bytes/PCA sizing) against logarithmic pixel-domain distortion.
