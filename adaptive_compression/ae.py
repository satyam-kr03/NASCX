#!/usr/bin/env python3
"""
Autoencoder-based Video Compression

This script trains convolutional autoencoders for video frame compression
and evaluates the rate-distortion trade-off at different latent dimensions.
"""

# use package-qualified import so module can be executed from workspace root
from adaptive_compression.autoencoder.main import main

if __name__ == "__main__":
    main()
