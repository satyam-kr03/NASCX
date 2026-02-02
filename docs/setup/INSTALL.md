# Installation Guide

Detailed installation instructions for the NASCX project.

## Prerequisites

### For Automated Installation

- **Linux system** (Ubuntu/Debian recommended)
- **sudo privileges** (for installing system packages)

The installation script will automatically install all other dependencies.

### For Manual Installation

If you choose manual installation, you'll need:
- GCC/G++ compiler
- Python 3.x
- Miniconda or Anaconda
- bison, flex, build-essential, pkg-config, wget, git

## Automated Installation (Recommended)

The easiest way to install is using the provided installation script:

```bash
./install.sh
```

### What the Script Does

The installation script will:

1. **Detect your OS** and verify it's Ubuntu/Debian-based
2. **Prompt for GUI support**: Choose whether to install Qt6-based IDE or command-line only
3. **Install system dependencies** automatically via apt-get:
   - Base: bison, flex, build-essential, pkg-config, wget, git
   - GUI (if selected): qt6-base-dev, qt6-base-dev-tools, libopenscenegraph-dev
4. **Install Miniconda** (if not already installed at `~/miniconda3`)
5. **Create conda environment** named `omnetpp` with Python 3.12
6. **Download OMNeT++ 6.2.0** from official GitHub releases
7. **Build OMNeT++** with your selected configuration (GUI or CLI-only)
8. **Build INET 4.5.4** in release mode
9. **Build Simu5G 1.3.0** in release mode
10. **Configure ~/.bashrc** for persistent environment setup

The entire process is fully automated and requires minimal user interaction.

## Manual Installation

If you prefer to install manually or need to customize the installation, follow these steps:

### 1. Install System Dependencies

For Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y bison flex build-essential pkg-config wget git

# For GUI support (optional):
sudo apt-get install -y qt6-base-dev qt6-base-dev-tools libopenscenegraph-dev
```

### 2. Install Miniconda (if not already installed)

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
source ~/miniconda3/bin/activate
conda init --all
```

### 3. Create Conda Environment

```bash
# Create and activate environment
conda create -n omnetpp python=3.12
conda activate omnetpp

# Install build tools
conda install -c conda-forge bison flex -y

# For GUI support (optional):
conda install -c conda-forge pyqt=5 -y
```

### 4. Download and Build OMNeT++

```bash
cd /path/to/NASCX

# Download OMNeT++ 6.2.0
wget https://github.com/omnetpp/omnetpp/releases/download/omnetpp-6.2.0/omnetpp-6.2.0-linux-x86_64.tgz
tar xzf omnetpp-6.2.0-linux-x86_64.tgz
rm omnetpp-6.2.0-linux-x86_64.tgz

cd omnetpp-6.2.0

# Create configure.user with your preferences
cat > configure.user << EOF
WITH_QTENV=yes  # Set to 'no' for CLI-only
WITH_OSG=yes    # Set to 'no' for CLI-only
EOF

# Set up environment and build
source setenv

# Install Python requirements
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r python/requirements.txt

# Configure and build
./configure
make -j$(nproc)
cd ..
```

### 5. Build INET

```bash
cd inet4.5
source ../omnetpp-6.2.0/setenv
make makefiles
make MODE=release -j$(nproc)
cd ..
```

### 6. Build Simu5G

```bash
cd simu5g-1.3.0
source ../omnetpp-6.2.0/setenv
make makefiles
make MODE=release -j$(nproc)
cd ..
```

### 7. Configure Environment Persistence

The install script automatically adds these to your `~/.bashrc`. If installing manually, add:

```bash
# Add to ~/.bashrc
echo '# OMNeT++ Environment Variables' >> ~/.bashrc
echo 'source /path/to/NASCX/omnetpp-6.2.0/setenv > /dev/null 2>&1' >> ~/.bashrc
echo 'source /path/to/NASCX/inet4.5/setenv > /dev/null 2>&1' >> ~/.bashrc
echo 'pushd /path/to/NASCX/simu5g-1.3.0 > /dev/null 2>&1' >> ~/.bashrc
echo 'source setenv > /dev/null 2>&1' >> ~/.bashrc
echo 'popd > /dev/null 2>&1' >> ~/.bashrc
source ~/.bashrc
```

**Note:** Replace `/path/to/NASCX` with your actual project path.

## Uninstallation

To remove the NASCX installation:

```bash
./uninstall.sh
```

This will:
- Remove OMNeT++, INET, and Simu5G build directories
- Clean up environment variables from `~/.bashrc`
- Optionally remove the Conda environment
- Optionally remove Miniconda installation
- Create a backup of your `~/.bashrc` file before making changes

## Troubleshooting

### Permission denied during system package installation

The install script requires sudo privileges. Make sure you can run:
```bash
sudo apt-get update
```

If prompted, enter your password.

### Miniconda installation fails

If you already have conda installed elsewhere, the script will detect and use it. If installation fails:
```bash
# Remove partial installation
rm -rf ~/miniconda3
# Run install script again
./install.sh
```

### OMNeT++ download fails

If the download is interrupted, remove the partial download and try again:
```bash
rm -f omnetpp-6.2.0-linux-x86_64.tgz
./install.sh
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
cd omnetpp-6.2.0  # or inet4.5 or simu5g-1.3.0
make clean && make makefiles && make
```

### Environment conflicts

If you have multiple package managers (conda, nix, etc.), make sure only conda is active:
```bash
conda deactivate  # deactivate all
conda activate omnetpp  # activate only omnetpp env
```

### GUI/IDE not working

If you chose GUI support but the IDE doesn't work:
```bash
# Verify Qt6 is installed
dpkg -l | grep qt6-base-dev

# If missing, install manually:
sudo apt-get install -y qt6-base-dev qt6-base-dev-tools libopenscenegraph-dev

# Rebuild OMNeT++ with GUI support
cd omnetpp-6.2.0
make clean
./configure
make -j$(nproc)
```

## Configuration Notes

- **GUI Support**: The install script prompts you to choose between GUI (Qt6-based IDE) or command-line only installation
- **Automatic Downloads**: OMNeT++ is automatically downloaded from official GitHub releases
- **Python Environment**: Uses Python 3.12 in a dedicated conda environment (`omnetpp`)
- **Build Mode**: All frameworks are built in release mode by default
- **Environment Persistence**: All environment variables are automatically added to `~/.bashrc`

## Build Customization

To build in debug mode instead of release:
```bash
make MODE=debug -j$(nproc)
```

To rebuild from scratch:
```bash
make clean && make makefiles && make
```
