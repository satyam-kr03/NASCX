# Variable Rate Autoencoder for Video Compression

## Overview

This module implements a **convolutional autoencoder with residual connections** for variable-rate video frame compression. The autoencoder learns to encode video frames into a compact latent representation and can reconstruct them at different compression levels by selectively keeping the most important latent coefficients.

## Architecture

### Network Design

The autoencoder consists of three main components:

#### 1. Residual Block
- Two convolutional layers with batch normalization
- Skip connection for gradient flow
- ReLU activation

```
Input → Conv3x3 → BN → ReLU → Conv3x3 → BN → (+) → ReLU → Output
  ↓                                            ↑
  └────────────────────────────────────────────┘
```

#### 2. Encoder
Progressive downsampling from 224×224 to 7×7:

| Layer | Input Size | Output Size | Channels |
|-------|-----------|-------------|----------|
| Conv1 + ResBlock | 224×224 | 112×112 | 3 → 64 |
| Conv2 + ResBlock | 112×112 | 56×56 | 64 → 128 |
| Conv3 + ResBlock | 56×56 | 28×28 | 128 → 256 |
| Conv4 | 28×28 | 14×14 | 256 → 512 |
| Conv5 | 14×14 | 7×7 | 512 → latent_channels |

#### 3. Decoder
Progressive upsampling from 7×7 back to 224×224:

| Layer | Input Size | Output Size | Channels |
|-------|-----------|-------------|----------|
| ConvTranspose1 | 7×7 | 14×14 | latent_channels → 512 |
| ConvTranspose2 + ResBlock | 14×14 | 28×28 | 512 → 256 |
| ConvTranspose3 + ResBlock | 28×28 | 56×56 | 256 → 128 |
| ConvTranspose4 + ResBlock | 56×56 | 112×112 | 128 → 64 |
| ConvTranspose5 | 112×112 | 224×224 | 64 → 3 |

### Variable Rate Compression

The key innovation is the **variable rate compression mechanism**:

1. Encode the frame to get the latent representation
2. Flatten the latent tensor into a 1D vector
3. Sort coefficients by absolute magnitude
4. Keep only the top-k coefficients based on `keep_ratio`
5. Zero out the remaining coefficients
6. Decode the modified latent representation

This allows adjusting the compression rate **without retraining** the model.

## Module Structure

```
autoencoder/
├── __init__.py      # Constants and configuration
├── models.py        # Neural network architectures
├── data.py          # Video loading and preprocessing
├── train.py         # Training loop
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
| `DEFAULT_LATENT_CHANNELS` | 128 | Number of latent channels |
| `DEFAULT_BATCH_SIZE` | 16 | Training batch size |
| `DEFAULT_NUM_EPOCHS` | 40 | Number of training epochs |
| `DEFAULT_LEARNING_RATE` | 0.001 | Initial learning rate |
| `DEFAULT_TRAIN_RATIO` | 0.15 | Ratio of frames for training |
| `DEFAULT_KEEP_RATIOS` | 0.05 to 0.80 | 16 compression levels |

## Usage

### Command Line

```bash
# Run with default settings
python autoencoder.py

# Custom video and parameters
python autoencoder.py \
    --video-path /path/to/video.mp4 \
    --latent-channels 128 \
    --batch-size 16 \
    --num-epochs 40 \
    --learning-rate 0.001 \
    --train-ratio 0.15 \
    --output-csv results.csv \
    --output-plot analysis.png
```

### Programmatic API

```python
import torch
from autoencoder.models import VariableRateAutoencoder
from autoencoder.data import load_data, FrameDataset
from autoencoder.train import train_model
from autoencoder.evaluate import evaluate_compression

# Load data
frames_train, frames_test = load_data(video_path, train_ratio=0.15)

# Create model
model = VariableRateAutoencoder(latent_channels=128)
model.to(device)

# Train
dataset = FrameDataset(frames_train)
dataloader = DataLoader(dataset, batch_size=16, shuffle=True)
train_model(model, dataloader, device, num_epochs=40)

# Evaluate at different compression levels
results = evaluate_compression(model, frames_test, device)
```

## Output Format

### CSV Results
The evaluation produces a CSV file with columns:

| Column | Description |
|--------|-------------|
| `frame` | Frame index (1-based) |
| `keep_ratio` | Ratio of coefficients kept (0.05 to 1.0) |
| `mse` | Mean Squared Error (pixel scale 0-255) |
| `size_bytes` | Compressed size in bytes |

**Note**: For each frame, an additional row is included with the original uncompressed frame size where `keep_ratio` = 1.0, `mse` = 0, and `size_bytes` = `img_size × img_size × 3 × 4`.

### Visualization
A PNG file with two plots:
1. **MSE by Frame**: Reconstruction error across frames for each keep ratio
2. **Rate-Distortion Curve**: Average MSE vs. compressed size

## Training Details

- **Loss Function**: Mean Squared Error (MSE)
- **Optimizer**: Adam with learning rate 0.001
- **Scheduler**: ReduceLROnPlateau (factor=0.5, patience=3)
- **Data Split**: 15% training, 85% testing (shuffled)

## Performance Characteristics

| Keep Ratio | Typical MSE | Compressed Size |
|------------|-------------|-----------------|
| 0.80 | ~400 | ~20KB |
| 0.50 | ~470 | ~12KB |
| 0.20 | ~1800 | ~5KB |
| 0.05 | ~4100 | ~1.2KB |

*Values are approximate and depend on video content.*

## Dependencies

- PyTorch
- NumPy
- Pandas
- Matplotlib
- PyAV (for video reading)
- tqdm (for progress bars)

## File Locations

- **Entry Point**: `adaptive_compression/autoencoder.py`
- **Module**: `adaptive_compression/autoencoder/`
- **Default Video**: `data/sintel_trailer-1080p.mp4`
- **Output**: `autoencoder/varrate_compression_results.csv`
- **Plot**: `autoencoder/varrate_compression_analysis.png`
