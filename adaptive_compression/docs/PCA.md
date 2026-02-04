# PCA-based Video Compression

## Overview

This module implements **Principal Component Analysis (PCA)** for variable-rate video frame compression. PCA is a classical linear dimensionality reduction technique that projects data onto a lower-dimensional subspace defined by the directions of maximum variance.

## How It Works

### Principal Component Analysis

1. **Flatten frames**: Each video frame (224×224×3) is reshaped into a 1D vector
2. **Fit PCA**: Learn principal components from training frames using Incremental PCA
3. **Transform**: Project frames onto the principal component basis
4. **Truncate**: Keep only the top-k components (variable compression)
5. **Reconstruct**: Inverse transform to recover the frame

### Compression Mechanism

The compression rate is controlled by the **number of principal components** kept:
- More components → Higher quality, larger size
- Fewer components → Lower quality, smaller size

Since PCA components are ordered by variance explained, keeping the first k components retains the most important information.

## Module Structure

```
pca/
├── __init__.py      # Constants and configuration
├── models.py        # PCACompressor class
├── data.py          # Video loading and preprocessing
├── evaluate.py      # Compression evaluation
├── main.py          # CLI entry point
└── utils.py         # Logging, saving, plotting
```

## Configuration

Default parameters defined in `__init__.py`:

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| `RANDOM_SEED` | 42 | Random seed for reproducibility |
| `DEFAULT_IMG_SIZE` | 224 | Input image size (square) |
| `DEFAULT_TRAIN_RATIO` | 0.15 | Ratio of frames for PCA fitting |
| `DEFAULT_MAX_COMPONENTS` | 80 | Maximum PCA components to fit |
| `DEFAULT_COMPONENTS` | [80, 75, ..., 5] | Component counts to evaluate |

## PCACompressor Class

The core class that handles compression and reconstruction.

### Initialization

```python
from pca.models import PCACompressor

compressor = PCACompressor(
    n_components=80,    # Maximum components to keep
    img_size=224        # Image size (assumes square)
)
```

### Methods

#### `fit(frames)`
Fit PCA on training frames using Incremental PCA for memory efficiency.

```python
# frames: numpy array of shape (N, H, W, 3), values 0-255
compressor.fit(frames_train)
```

#### `compress_and_reconstruct(frame, n_components)`
Compress and reconstruct a single frame.

```python
# frame: numpy array of shape (H, W, 3), normalized to [0, 1]
reconstructed, size_bytes = compressor.compress_and_reconstruct(
    frame, 
    n_components=40
)
```

Returns:
- `reconstructed`: Reconstructed frame as numpy array
- `size_bytes`: Compressed size in bytes

## Usage

### Command Line

```bash
# Run with default settings
python pca.py

# Custom parameters
python pca.py \
    --video-path /path/to/video.mp4 \
    --max-components 80 \
    --train-ratio 0.15 \
    --output-csv pca_results.csv \
    --output-plot pca_analysis.png
```

### Programmatic API

```python
import numpy as np
from pca.data import load_data
from pca.models import PCACompressor
from pca.evaluate import evaluate_compression
from pca.utils import save_results, plot_results

# Set seed
np.random.seed(42)

# Load data
frames_train, frames_test = load_data(video_path, train_ratio=0.15)

# Create and fit compressor
compressor = PCACompressor(n_components=80, img_size=224)
compressor.fit(frames_train)

# Evaluate at different component counts
components_list = list(range(80, 0, -5))  # [80, 75, 70, ..., 5]
results = evaluate_compression(compressor, frames_test, components_list)

# Save results
save_results(results, "pca_results.csv")
plot_results(results, "pca_analysis.png")
```

## Output Format

### CSV Results
The evaluation produces a CSV file with columns:

| Column | Description |
|--------|-------------|
| `frame` | Frame index (1-based) |
| `components` | Number of PCA components used |
| `mse` | Mean Squared Error (pixel scale 0-255) |
| `size_bytes` | Compressed size in bytes |

### Size Calculation
```
size_bytes = n_components × img_size × 4 (bytes per float32)
```

For example, with 40 components and 224×224 images:
```
size_bytes = 40 × 224 × 4 = 35,840 bytes ≈ 35 KB
```

### Visualization
A PNG file with two plots:
1. **MSE by Frame**: Reconstruction error across frames for each component count
2. **Rate-Distortion Curve**: Average MSE vs. compressed size

## Comparison with Autoencoder

| Aspect | PCA | Autoencoder |
|--------|-----|-------------|
| **Type** | Linear | Non-linear |
| **Training** | Fast (single pass) | Slow (multiple epochs) |
| **GPU Required** | No | Yes (recommended) |
| **Adaptability** | Fixed basis | Learned basis |
| **Low Bitrate** | Poor quality | Better quality |
| **High Bitrate** | Good quality | Similar quality |

### When to Use PCA
- Quick baseline compression
- Limited computational resources
- High bitrate scenarios
- Interpretable compression

### When to Use Autoencoder
- Maximum compression efficiency
- Low bitrate requirements
- GPU available for training
- Complex video content

## Algorithm Details

### Incremental PCA
Uses `sklearn.decomposition.IncrementalPCA` to handle large datasets:
- Processes data in batches (default: 100 frames)
- Memory efficient for large videos
- Mathematically equivalent to batch PCA

### MSE Calculation
MSE is computed in the original pixel scale (0-255) for consistency:
```python
mse = np.mean((reconstructed - original) ** 2) * 255 * 255
```

## Performance Characteristics

| Components | Typical MSE | Compressed Size |
|------------|-------------|-----------------|
| 80 | ~500 | ~71 KB |
| 40 | ~1200 | ~36 KB |
| 20 | ~2500 | ~18 KB |
| 5 | ~5000 | ~4.5 KB |

*Values are approximate and depend on video content.*

## Dependencies

- NumPy
- scikit-learn (IncrementalPCA)
- PyTorch (for image resizing)
- Pandas
- Matplotlib
- PyAV (for video reading)

## File Locations

- **Entry Point**: `adaptive_compression/pca.py`
- **Module**: `adaptive_compression/pca/`
- **Default Video**: `data/sintel_trailer-1080p.mp4`
- **Output**: `pca/pca_compression_results.csv`
- **Plot**: `pca/pca_compression_analysis.png`

## Limitations

1. **Linear assumption**: PCA assumes data lies on a linear subspace, which may not capture complex image structures
2. **Global basis**: Same principal components for all frames, may not adapt to varying content
3. **No spatial awareness**: Treats each pixel independently, ignores spatial correlations
4. **Fixed vocabulary**: Cannot represent features not in the training set
