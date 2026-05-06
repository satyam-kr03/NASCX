# Network-Aware Semantic Communication for XR in 6G Networks

A 5G/6G network simulation project using OMNeT++ 6.2.0, INET 4.5.4, and Simu5G 1.3.0. All frameworks are included and pre-configured for command-line use.

## Quick Start

### Prerequisites

- **Linux system** (Ubuntu/Debian recommended)
- **sudo privileges** (for installing system packages)

The installation script will automatically install:
- System dependencies (bison, flex, build-essential, pkg-config, wget, git)
- Qt6 libraries (optional, for GUI support)
- Miniconda (if not already installed)
- Python 3.12 environment

### Installation

1. **Clone the repository:**

```bash
git clone https://github.com/satyam-kr03/NASCX.git
cd NASCX
```

2. **Run the installation script:**

```bash
./install.sh
```

The script will:
- Prompt you to choose GUI support (Qt6-based IDE) or command-line only installation
- Install all required system dependencies automatically
- Install Miniconda (if not present)
- Download and build OMNeT++ 6.2.0
- Build INET 4.5.4 and Simu5G 1.3.0
- Configure your `~/.bashrc` for persistent environment setup

For detailed installation instructions and manual installation steps, see [docs/setup/INSTALL.md](docs/setup/INSTALL.md).

## Usage

Before starting, activate the conda environment:

```bash
conda activate omnetpp
```

### Running Simulations

Navigate to the Simu5G simulations directory:

```bash
cd simu5g-1.3.0/simulations
# Run your simulation scenarios here
```

### Running Examples

Test INET:
```bash
cd inet4.5/examples/inet/arp
./run
```

Test Simu5G:
```bash
cd simu5g-1.3.0/simulations
# Explore available examples
```

## Uninstallation

To remove the installation:

```bash
./uninstall.sh
```

## Project Structure

```
.
├── omnetpp-6.2.0/       # OMNeT++ simulator (pre-configured for CLI)
├── inet4.5/             # INET Framework
├── simu5g-1.3.0/        # Simu5G (5G NR simulation)
│   └── simulations/     # Simulation scenarios
├── install.sh           # Automated installation script
├── uninstall.sh         # Cleanup script
├── INSTALL.md           # Detailed installation guide
└── README.md
```

## Troubleshooting

For detailed troubleshooting steps, see [docs/setup/INSTALL.md](docs/setup/INSTALL.md).

Common issues:
- **Commands not found**: Restart your terminal or run `source ~/.bashrc`
- **Build errors**: Ensure conda environment is active: `conda activate omnetpp`
- **Permission errors**: Ensure you have sudo privileges for system package installation

## Configuration Notes

- **GUI Support**: You can choose to install with or without Qt6-based IDE during installation
- **Automatic Setup**: Miniconda and all dependencies are installed automatically
- **Python Environment**: Uses Python 3.12 in a dedicated conda environment (`omnetpp`)
- **Build Mode**: All frameworks are built in release mode by default

## Useful Commands

```bash
# Check OMNeT++ version
opp_run --version

# Rebuild from scratch
make clean && make makefiles && make

# Run in debug mode
make MODE=debug

# Launch IDE (optional)
omnetpp
```

## Version Information

| Component | Version |
|-----------|---------|
| OMNeT++ | 6.2.0 |
| INET | 4.5.4 |
| Simu5G | 1.3.0 |
| Python | 3.12 |

## References

- [OMNeT++ Documentation](https://docs.omnetpp.org/)
- [INET Framework](https://inet.omnetpp.org/)
- [Simu5G](https://simu5g.org/)

## License

Please refer to the individual licenses of OMNeT++, INET, and Simu5G.