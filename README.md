# Network-Aware Semantic Communication for XR in 6G Networks

A 5G/6G network simulation project using OMNeT++ 6.2.0, INET 4.5.4, and Simu5G 1.3.0. All frameworks are included and pre-configured for command-line use.

## Quick Start

### Prerequisites

- Linux system (Ubuntu/Debian recommended)
- GCC/G++ compiler
- Python 3.x
- Miniconda or Anaconda

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

This will automatically build OMNeT++, INET, and Simu5G, and configure your environment.

For detailed installation instructions and manual installation steps, see [INSTALL.md](INSTALL.md).

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

For detailed troubleshooting steps, see [INSTALL.md](INSTALL.md).

Common issues:
- **Commands not found**: Run `source ~/.bashrc` or restart your terminal
- **Build errors**: Ensure conda environment is active: `conda activate omnetpp`
- **Missing configure.user**: Run `cp configure.user.dist configure.user` in omnetpp-6.2.0/

## Configuration Notes

- OMNeT++ has been pre-configured for command-line first usage
- Python bindings are disabled by default (can be enabled in `omnetpp-6.2.0/configure.user`)
- All frameworks are set up for release mode builds

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