# Autoencoder-based Dimensionality Reduction for 360° XR Frames

## Overview
The autoencoder compression module provides a neural, learning-based pipeline for controllable dimensionality reduction of high-dimensional 360° XR (Extended Reality) video frames. By training a family of symmetric convolutional autoencoders — one per target bottleneck size — the module learns nonlinear encoder–decoder mappings that compress frames into compact latent vectors and reconstruct them with minimal distortion.

The compression level is governed by the **latent dimension** $d$: smaller values yield higher compression at the cost of increased reconstruction error, while larger values preserve more detail. The primary objective is to evaluate the rate-distortion trade-off: comparing the transmitted data size (dictated by the latent dimension and amortised model weights) versus the resulting mean squared error (MSE) relative to the source frames. This establishes a learned-compression baseline for dynamic adaptation across evolving network conditions, complementing the linear PCA baseline.

## Architecture

The compression module is systematically organised into five distinct components under the `autoencoder/` package:

1. **`main.py`**: The CLI orchestration script bridging data extraction, per-dimension model training, streaming evaluation, and storing final outputs.
2. **`data.py`**: Re-exports the shared video I/O functions from `pca.data` (metadata extraction, per-frame encoded bitstream sizing via `ffprobe`, streaming frame decoding via `PyAV` and `OpenCV`) and adds a PyTorch `Dataset` / `DataLoader` wrapper for mini-batch training.
3. **`models.py`**: Supplies the core `ConvAutoencoder` network (a symmetric Conv2d encoder–decoder) and the `AutoencoderCompressor` manager that instantiates, trains, and queries one model per latent dimension.
4. **`evaluate.py`**: The streaming evaluation engine iteratively compressing frames through each trained model, computing distortion metrics (MSE), and allocating amortised overhead to size estimations simultaneously across various latent dimension scenarios.
5. **`utils.py`**: Implements logging standardisation, aggregates frame-level metrics into CSV datasets, and renders dual-panel visualisations via `matplotlib`.

## Core Mechanisms

### Data Extraction and Pre-processing
The pipeline shares its data layer with the PCA module to avoid code duplication. All video I/O functions (`get_video_info`, `get_encoded_frame_sizes`, `sample_training_frames`, `stream_test_frames`) are re-exported from `pca.data`. The autoencoder-specific addition is:

- **`FrameDataset`**: A PyTorch `Dataset` wrapping an `(N, H, W, 3)` uint8 numpy array. Each `__getitem__` call normalises to float32 $\in [0, 1]$ and transposes to channel-first format `(3, H, W)` as required by PyTorch convolutional layers.
- **`get_dataloader`**: Constructs a `DataLoader` with configurable batch size, shuffling, and multi-worker prefetching for efficient GPU utilisation.

Frame pre-processing follows the same conventions as the PCA pipeline:
- **Bilinear Resizing** to `(img_size, img_size)` (default $224 \times 224$).
- **Normalisation** to float32 $\in [0, 1]$.
- **Train/Test Split** via random permutation with configurable `train_ratio` (default $0.33$).

### Network Architecture
The `ConvAutoencoder` is a symmetric convolutional autoencoder with a flat bottleneck:

**Encoder:**

$$x \in \mathbb{R}^{3 \times 224 \times 224} \xrightarrow{\text{4 × (Conv2d → BN → ReLU)}} h \in \mathbb{R}^{256 \times 14 \times 14} \xrightarrow{\text{Flatten → Linear}} z \in \mathbb{R}^{d}$$

Each convolutional block uses kernel size 4, stride 2, padding 1, halving the spatial dimensions at each stage through the channel progression $[3, 32, 64, 128, 256]$. The resulting $256 \times 14 \times 14 = 50{,}176$-dimensional feature vector is linearly projected to the latent vector $z$ of dimension $d$.

**Decoder:**

$$z \in \mathbb{R}^{d} \xrightarrow{\text{Linear → Reshape}} h \in \mathbb{R}^{256 \times 14 \times 14} \xrightarrow{\text{4 × (ConvTranspose2d → BN → ReLU)}} \hat{x} \in \mathbb{R}^{3 \times 224 \times 224}$$

The decoder mirrors the encoder with transposed convolutions. The final layer uses a **Sigmoid** activation to constrain pixel outputs to $[0, 1]$.

### Per-Dimension Model Training with Warm-Starting
Unlike the PCA pipeline — where a single fit supports arbitrary component truncation — autoencoders have a fixed bottleneck width that is integral to the learned mapping. The module therefore trains **one dedicated model per target latent dimension**, proceeding in **ascending order** of dimension with **warm-starting** to promote monotonic rate-distortion behaviour:

- The `AutoencoderCompressor` instantiates $|\mathcal{D}|$ independent `ConvAutoencoder` instances, where $\mathcal{D}$ is the set of evaluation dimensions (default: $\{32, 64, 96, \ldots, 512\}$, trained smallest-first).
- Each model is trained using the **Adam** optimiser (default $\text{lr} = 10^{-3}$) with pixel-wise **MSE loss** over $E$ epochs (default $E = 50$).
- **Warm-starting**: after training the model for dimension $d_i$, its convolutional backbone weights (`encoder_conv`, `decoder_conv`) are copied into the next model ($d_{i+1}$) before that model's training begins. Since the convolutional layers are structurally identical across all models — only the FC bottleneck layers (`encoder_fc`, `decoder_fc`) differ in width — this transfers the learned spatial feature extraction while allowing the new, wider bottleneck to be optimised from scratch. The warm-start gives larger models a strictly better initialisation, promoting monotonically decreasing reconstruction error as the latent dimension increases.
- Following training, all models are set to `eval()` mode and training data is freed via standard GC hooks (`del train_frames`).

### Compression and Reconstruction
The `compress_and_reconstruct` procedure for a target frame $x$ and latent dimension $d$:

1. **Channel transposition and batching**: $(H, W, 3) \to (1, 3, H, W)$
2. **Encoding**: $z = f_{\text{enc}}^{(d)}(x) \in \mathbb{R}^{d}$
3. **Decoding**: $\hat{x} = f_{\text{dec}}^{(d)}(z) \in \mathbb{R}^{3 \times H \times W}$
4. **Output clamping**: $\hat{x} \leftarrow \text{clip}(\hat{x}, 0, 1)$ preventing out-of-gamut values
5. **Reshape**: $(1, 3, H, W) \to (H, W, 3)$

The entire forward pass runs under `torch.no_grad()` for memory-efficient inference.

### Streaming Evaluation Engine
Defined under `evaluate.evaluate_compression()`, the evaluation mirrors the PCA pipeline's structure:

- The pipeline holds merely $\approx 1$ frame in memory at a time (plus the model weights on device).
- For each test frame, a **baseline row** is emitted with `latent_dim=0`, `mse=0.0`, and `ae_size_bytes=raw_size_bytes`.
- For each target latent dimension $d \in \mathcal{D}$, the frame is compressed and reconstructed through the corresponding model.
- **Error metric**: pixel-domain Mean Squared Error scaled to $[0, 255]$ range:

$$\text{MSE} = \frac{255^2}{N_{\text{pixels}}} \sum_{i} (\hat{x}_i - x_i)^2$$

- **Size accounting** (per frame):

$$\text{ae\_size\_bytes} = \underbrace{d \times 4}_{\text{latent vector (float32)}} + \underbrace{\frac{|\theta^{(d)}| \times 4}{\text{total\_frames}}}_{\text{amortised model weights}}$$

where $|\theta^{(d)}|$ is the number of trainable parameters in the model for dimension $d$. This amortises the one-time cost of transmitting or storing the decoder weights across all frames, directly mirroring the PCA pipeline's treatment of basis vectors and global mean.

### Visualisation and Metric Storage
Through `.csv` exports and `plot_results()`, output graphs coalesce into dual-panel summaries:

1. **Frame-by-frame reconstruction error**: MSE (log-scale) per frame index for each latent dimension, showing per-frame volatility and content-dependent compression difficulty.
2. **Rate-distortion curve**: Average MSE (log-scale) versus `ae_size_bytes` with annotated latent dimension labels, encapsulating the fundamental compression–quality trade-off.

### CSV Output Format
Each row records one `(frame, latent_dim)` evaluation point:

| Column | Description |
|---|---|
| `frame` | Frame index in the video |
| `latent_dim` | Bottleneck dimension ($0$ for uncompressed baseline) |
| `mse` | Pixel-domain MSE ($\times 255^2$) |
| `ae_size_bytes` | Latent vector + amortised model weight cost |
| `encoded_size_bytes` | Original codec packet size from `ffprobe` |
| `raw_size_bytes` | Uncompressed frame size ($H \times W \times C$) |
| `pict_type` | Original codec picture type (I / P / B) |

## Usage

```bash
# From the adaptive_compression/ directory:
python ae.py \
  --video-path ../data/yt360-videos/aliens.mp4 \
  --max-latent-dim 512 \
  --epochs 50 \
  --batch-size 32 \
  --lr 0.001 \
  --train-ratio 0.33 \
  --output-csv ae_compression_results.csv \
  --output-plot ae_compression_analysis.png \
  --device cuda \
  --log-level INFO
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--video-path` | `../data/yt360-videos/minecraft.mp4` | Path to the input video file |
| `--max-latent-dim` | `512` | Maximum latent dimension; filters `DEFAULT_LATENT_DIMS` |
| `--train-ratio` | `0.33` | Fraction of frames used for training |
| `--epochs` | `50` | Training epochs per model |
| `--batch-size` | `32` | Mini-batch size for training |
| `--lr` | `0.001` | Adam optimiser learning rate |
| `--img-size` | `224` | Working resolution (frames resized to square) |
| `--device` | Auto-detect | `cuda` or `cpu` |
| `--output-csv` | `ae_compression_results.csv` | Output CSV path |
| `--output-plot` | `ae_compression_analysis.png` | Output plot path |
| `--log-level` | `INFO` | Logging verbosity |
