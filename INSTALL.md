# Installation Guide

Detailed installation instructions for the NASCX project.

## Prerequisites

- Linux system (Ubuntu/Debian recommended)
- GCC/G++ compiler
- Python 3.x
- Miniconda or Anaconda

## Automated Installation (Recommended)

The easiest way to install is using the provided installation script:

```bash
./install.sh
```

This will automatically:
1. Create and configure the Conda environment
2. Build OMNeT++ 6.2.0
3. Build INET 4.5.4
4. Build Simu5G 1.3.0
5. Configure your shell environment

## Manual Installation

If you prefer to install manually or need to customize the installation, follow these steps:

### 1. Install Dependencies using Conda

```bash
# Create and activate environment
conda create -n omnetpp python=3.12
conda activate omnetpp

# Install build tools
conda install -c conda-forge bison flex python-devel
```

### 2. Build OMNeT++

```bash
cd omnetpp-6.2.0

# Create configure.user from template (required)
cp configure.user.dist configure.user

# Set up environment and build
source setenv
./configure
make -j$(nproc)
cd ..
```

### 3. Build INET

```bash
cd inet4.5
source ../omnetpp-6.2.0/setenv
make makefiles
make MODE=release -j$(nproc)
cd ..
```

### 4. Build Simu5G

```bash
cd simu5g-1.3.0
source ../omnetpp-6.2.0/setenv
make makefiles
make MODE=release -j$(nproc)
cd ..
```

### 5. Add Frameworks to Your PATH

The install script automatically adds these to your `~/.bashrc`. If installing manually, add:

```bash
echo 'source ~/NASCX/omnetpp-6.2.0/setenv > /dev/null 2>&1' >> ~/.bashrc
echo 'source ~/NASCX/inet4.5/setenv > /dev/null 2>&1' >> ~/.bashrc
source ~/.bashrc
```

**Note:** Replace `~/NASCX` with your actual project path if different.

## Uninstallation

To remove the NASCX installation:

```bash
./uninstall.sh
```

This will:
- Clean up shell environment variables from `~/.bashrc`
- Optionally remove the Conda environment
- Create a backup of your `~/.bashrc` file

## Troubleshooting

### Error: "does not look like an OMNeT++ root directory"

This happens if `configure.user` is missing. Run:
```bash
cd omnetpp-6.2.0
cp configure.user.dist configure.user
source setenv
```

### Commands not found after terminal restart

Make sure the installation script completed successfully and run:
```bash
source ~/.bashrc
```

### Build errors

Ensure your conda environment is activated:
```bash
conda activate omnetpp
```

Clean and rebuild if needed:
```bash
make clean && make makefiles && make
```

### Environment conflicts

If you have multiple package managers (conda, nix, etc.), make sure only conda is active:
```bash
conda deactivate  # deactivate all
conda activate omnetpp  # activate only omnetpp env
```

## Configuration Notes

- OMNeT++ has been pre-configured for command-line first usage
- Python bindings are disabled by default (can be enabled in `omnetpp-6.2.0/configure.user`)
- All frameworks are set up for release mode builds

## Build Customization

To build in debug mode instead of release:
```bash
make MODE=debug -j$(nproc)
```

To rebuild from scratch:
```bash
make clean && make makefiles && make
```
