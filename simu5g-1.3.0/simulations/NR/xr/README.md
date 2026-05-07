# AI-Driven Adaptive XR Streaming Optimization

This project introduces a holistic, end-to-end simulation and machine learning framework designed to dynamically optimize Virtual Reality (VR) and Extended Reality (XR) video streaming over simulated 5G networks.

By intelligently analyzing realtime physical-layer network metrics (such as CQI and transmission delay), the system decides precisely how aggressively to compress video frames before transmission. Crucially, because the system relies on dimensionality reduction techniques like Principal Component Analysis (PCA) instead of standard random packet dropping, it inherently prioritizes the **semantic importance of the frames**. It systematically sheds the least critical mathematical features of the video while aggressively retaining the variance that represents the core visual semantics, allowing a direct mathematical evaluation of QoE via Mean Squared Error (MSE).

---

## 1. Project Architecture Overview

The pipeline unifies low-level C++ network simulation (using **OMNeT++ / Simu5G**) alongside a robust Python-based Data Processing and Machine Learning ecosystem.

### A. The Core Network Simulator (C++)
Located in `src/apps/xr/`. 
Custom 5G applications were explicitly created to accurately mirror XR flows:
- **`XRTrafficSource`**: Generates massive video frame payloads directly corresponding to analyzed offline video traces. It has a unique `model` operation mode which queries an external Python application for instructions on how heavily to compress the next individual frame.
- **`XRTrafficReceiver`**: The destination sink handling fragment reassembly, latency calculations, and deadline enforcement. It continually monitors the User Equipment's live Channel Quality Indicator (DL CQI) internally mapping it back across the architecture via a unified `Binder` object.

**Documentation**: [XR App Implementation details](src/apps/xr/XR_App_Documentation.md)

### B. Traffic Compression Assessment
Located in `compression/`. 
Before network simulations can even run, the raw video traffic profiles must be understood. This Python pipeline extracts reference 360-video frames and tests exactly how much size reduction and distortion (MSE) occur when the frames are mathematically compressed utilizing differing layers of **Principal Component Analysis (PCA)** or **Autoencoder** dimensionality reduction techniques. This step establishes the direct correlation between semantic frame degradation and byte payload retention—mapping how visually "important" certain components are to the ultimate QoE under heavy network loads.
- **Outputs**: Maps component levels (e.g., 5 to 80) against packet size and image distortion, creating `pca_sweep_summary.csv` used as a blueprint by the simulators.

**Documentation**: [PCA Compression Pipeline](compression/README.md)

### C. Dataset Generation
Located in `dataset_generation/`.
To deploy an AI model predicting the perfect compression, we first need to learn what forces a network to fail. 
The generation script utilizes the `XRTrafficSource` in `random` mode and spans intense parallel simulations varying user loads (from 2 up to 10 endpoints). It injects thousands of chaotic, random compression combinations into the 5G model to measure real-world interference, generating massive datasets indicating which network states result in catastrophic late-frame delays.

**Documentation**: [Dataset Generation Pipeline](dataset_generation/README.md)

### D. Neural Network Classifier
Located in `learning/`.
This module absorbs the generated multi-user traces. Rather than arbitrarily predicting continuous numbers, the `classifier.py` architecture treats compression targeting as a discrete choice—selecting between 16 defined levels. 
Advanced mathematical concepts like **Ordinal Soft Labels** and **KL Divergence** are employed during training to ensure the PyTorch intelligence understands that predicting 25 components is relatively close to the correct answer of 30, but radically incorrect compared to predicting 80.
- **Outputs**: Trained weights deployed to inference servers targeting varying populations, natively query-able by OMNeT++ via REST (`model_server.py`).

**Documentation**: [Active Machine Learning Architecture](learning/README.md)

### E. Validation & Comparison
Located in `comparison/`.
The final stage of the workflow mathematically benchmarks the success of the model.
`run_comparison.py` simultaneously spawns massive numbers of network workloads. It contrasts assigning the entire network statically to locked compression limits against activating the live `model` prediction pipeline allowing every node to adapt dynamically to congestion.
- **Outputs**: Precise telemetry establishing exactly how much the adaptive AI model improved the QoE reliability ceiling.

**Documentation**: [Simulation Comparison Engine](comparison/README.md)

---

## 2. Standard Execution Flow

Building the stack logically follows the modules above:

1. **Profile Video Traffic**: Evaluate how differing components shrink payloads *(Compression Pipeline)*.
   `python -m compression.main`
2. **Rescale Outputs**: Align and conform dimensions (legacy compatibilities).
   `python compression/rescale.py --input traffic_files/pca/pca_sweep_summary_vietnam.csv --output traffic_files/pca/pca_sweep_summary_vietnam.csv --target-mbps 60 --fps 60`
3. **Capture Telemetry**: Force 5G networks into varying fail-states. *(Dataset Generation)*.
   `python dataset_generation/generate_dataset.py --repetitions 2`
4. **Clean Results**: Final prep.
   `python datasets/clean_dataset.py datasets/pca/dataset.csv datasets/pca/dataset.csv`
5. **Train**: Train the discrete Multi-User component classifier. *(Learning)*.
   `python learning/classifier.py`
6. **Deploy & Validate**: Host the model via FastAPI, and trigger the side-by-side performance parallel comparison. *(Comparison)*.
   `python comparison/run_comparison.py`
