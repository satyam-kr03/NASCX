#!/bin/bash

# ==============================================================================
# Installer: OMNeT++ 6.2.0, INET 4.5.4, Simu5G 1.3.0
# For clean Ubuntu/Debian systems with automatic dependency installation
# ==============================================================================

set -e  # Exit immediately if a command exits with a non-zero status

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the absolute path of the project root
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

log() {
    echo -e "${BLUE}[Installer]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log "Starting installation in: $PROJECT_ROOT"
log "This script will install system dependencies and Miniconda automatically."

# ------------------------------------------------------------------------------
# 1. Check if running on Ubuntu/Debian
# ------------------------------------------------------------------------------
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    log "Detected OS: $OS"
else
    warn "Cannot detect OS. Assuming Debian/Ubuntu-based system."
    OS="unknown"
fi

# ------------------------------------------------------------------------------
# 2. GUI Installation Option
# ------------------------------------------------------------------------------
echo -e "${BLUE}[Installer]${NC} Do you want to install OMNeT++ with GUI support (IDE)?"
echo -e "  This requires Qt6 libraries and will enable the graphical IDE."
echo -e "  Choose 'no' for headless/command-line only installation."
read -p "Install with GUI support? (yes/no) [default: yes]: " GUI_CHOICE

# Default to 'yes'
GUI_CHOICE=${GUI_CHOICE:-yes}

# Normalize input
GUI_CHOICE=$(echo "$GUI_CHOICE" | tr '[:upper:]' '[:lower:]')

if [[ "$GUI_CHOICE" == "yes" || "$GUI_CHOICE" == "y" ]]; then
    WITH_QTENV="yes"
    WITH_OSG="yes"
    log "GUI support enabled. Qt6 libraries will be installed."
else
    WITH_QTENV="no"
    WITH_OSG="no"
    log "GUI support disabled. Command-line only installation."
fi

# ------------------------------------------------------------------------------
# 3. Install System Dependencies
# ------------------------------------------------------------------------------
log "Installing system dependencies..."

if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
    # Check if we have sudo privileges
    if ! sudo -n true 2>/dev/null; then
        warn "This script requires sudo privileges to install system packages."
        warn "You may be prompted for your password."
    fi
    
    log "Updating package lists..."
    sudo apt-get update
    
    # Base dependencies
    BASE_DEPS="bison flex build-essential pkg-config wget git"
    
    # GUI dependencies
    if [[ "$WITH_QTENV" == "yes" ]]; then
        GUI_DEPS="qt6-base-dev qt6-base-dev-tools libopenscenegraph-dev"
        ALL_DEPS="$BASE_DEPS $GUI_DEPS"
    else
        ALL_DEPS="$BASE_DEPS"
    fi
    
    log "Installing packages: $ALL_DEPS"
    sudo apt-get install -y $ALL_DEPS
    
    log "System dependencies installed successfully."
else
    warn "Unsupported OS: $OS"
    warn "Please manually install: bison flex build-essential pkg-config wget git"
    if [[ "$WITH_QTENV" == "yes" ]]; then
        warn "For GUI support, also install: qt6-base-dev qt6-base-dev-tools libopenscenegraph-dev"
    fi
    read -p "Continue anyway? (y/N): " CONTINUE_CHOICE
    if [[ ! "$CONTINUE_CHOICE" =~ ^[Yy]$ ]]; then
        error "Installation aborted."
    fi
fi

# ------------------------------------------------------------------------------
# 4. Install Miniconda
# ------------------------------------------------------------------------------
MINICONDA_DIR="$HOME/miniconda3"
ENV_NAME="omnetpp"

if [ -d "$MINICONDA_DIR" ] && [ -f "$MINICONDA_DIR/bin/conda" ]; then
    log "Miniconda already installed at $MINICONDA_DIR"
    # Initialize conda for this session
    source "$MINICONDA_DIR/bin/activate"
    eval "$(conda shell.bash hook)"
else
    log "Installing Miniconda..."
    
    mkdir -p "$MINICONDA_DIR"
    MINICONDA_INSTALLER="$MINICONDA_DIR/miniconda.sh"
    
    log "Downloading Miniconda installer..."
    wget -q --show-progress https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O "$MINICONDA_INSTALLER"
    
    log "Installing Miniconda (this may take a few minutes)..."
    bash "$MINICONDA_INSTALLER" -b -u -p "$MINICONDA_DIR"
    
    log "Cleaning up installer..."
    rm -f "$MINICONDA_INSTALLER"
    
    log "Initializing Conda..."
    source "$MINICONDA_DIR/bin/activate"
    conda init --all
    
    log "Miniconda installed successfully."
fi

# Ensure conda is available in this session
eval "$(conda shell.bash hook)"

# ------------------------------------------------------------------------------
# 5. Create and Configure Conda Environment
# ------------------------------------------------------------------------------
log "Setting up Conda environment '$ENV_NAME'..."

# Configure conda to avoid ToS prompts
conda config --set channel_priority flexible 2>/dev/null || true

if conda info --envs | grep -q "^$ENV_NAME "; then
    log "Conda environment '$ENV_NAME' already exists. Activating..."
    conda activate $ENV_NAME
else
    log "Creating Conda environment '$ENV_NAME' with Python 3.12..."
    conda create -n $ENV_NAME python=3.12 -y
    conda activate $ENV_NAME
fi

log "Installing build dependencies via Conda..."
if [[ "$WITH_QTENV" == "yes" ]]; then
    log "Installing Qt5 support for Conda environment..."
    conda install -c conda-forge bison flex pyqt=5 -y
else
    conda install -c conda-forge bison flex -y
fi

log "Conda environment configured successfully."

# ------------------------------------------------------------------------------
# 6. Download and Build OMNeT++ 6.2.0
# ------------------------------------------------------------------------------
OMNETPP_VERSION="6.2.0"
OMNETPP_DIR="$PROJECT_ROOT/omnetpp-${OMNETPP_VERSION}"
OMNETPP_TGZ="omnetpp-${OMNETPP_VERSION}-linux-x86_64.tgz"
OMNETPP_URL="https://github.com/omnetpp/omnetpp/releases/download/omnetpp-${OMNETPP_VERSION}/${OMNETPP_TGZ}"

if [ ! -d "$OMNETPP_DIR" ]; then
    log "OMNeT++ ${OMNETPP_VERSION} not found. Downloading..."
    cd "$PROJECT_ROOT"
    
    if [ ! -f "$OMNETPP_TGZ" ]; then
        log "Downloading OMNeT++ ${OMNETPP_VERSION}..."
        wget --show-progress "$OMNETPP_URL" || error "Failed to download OMNeT++"
    fi
    
    log "Extracting OMNeT++..."
    tar xzf "$OMNETPP_TGZ" || error "Failed to extract OMNeT++"
    
    log "Cleaning up downloaded archive..."
    rm -f "$OMNETPP_TGZ"
else
    log "OMNeT++ ${OMNETPP_VERSION} directory already exists."
fi

log "Configuring and building OMNeT++ ${OMNETPP_VERSION}..."
cd "$OMNETPP_DIR"

# Create configure.user with appropriate settings
log "Generating configure.user with selected options..."
cat > configure.user << EOF
# Generated by install.sh
WITH_QTENV=$WITH_QTENV
WITH_OSG=$WITH_OSG
EOF

log "Configuration: WITH_QTENV=$WITH_QTENV, WITH_OSG=$WITH_OSG"

# Source setenv to set up PATH and libraries for the build process
source setenv

# Install Python requirements for OMNeT++
log "Installing Python requirements for OMNeT++..."
if [ -f "$OMNETPP_DIR/python/requirements.txt" ]; then
    python3 -m pip install --upgrade pip
    python3 -m pip install --upgrade -r "$OMNETPP_DIR/python/requirements.txt"
else
    warn "Python requirements.txt not found, skipping Python package installation."
fi

# Set library paths for Conda
if [[ -n "$CONDA_PREFIX" ]]; then
    export LIBRARY_PATH="$CONDA_PREFIX/lib:${LIBRARY_PATH:-}"
    export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
    log "Configured library paths for Conda environment."
fi

# Configure and Build
log "Running ./configure (this may take a few minutes)..."
./configure

log "Building OMNeT++ with $(nproc) parallel jobs..."
make -j$(nproc)

log "OMNeT++ built successfully."

# ------------------------------------------------------------------------------
# 7. Build INET 4.5
# ------------------------------------------------------------------------------
log "Building INET 4.5..."

if [ ! -d "$PROJECT_ROOT/inet4.5" ]; then
    error "Directory inet4.5 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/inet4.5"

# Ensure OMNeT++ environment is set
source "$OMNETPP_DIR/setenv"

# Check if INET has its own setenv
if [ -f "setenv" ]; then
    source setenv
fi

log "Generating makefiles for INET..."
make makefiles

log "Building INET in release mode..."
make MODE=release -j$(nproc)

log "INET built successfully."

# ------------------------------------------------------------------------------
# 8. Build Simu5G 1.3.0
# ------------------------------------------------------------------------------
log "Building Simu5G 1.3.0..."

if [ ! -d "$PROJECT_ROOT/simu5g-1.3.0" ]; then
    error "Directory simu5g-1.3.0 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/simu5g-1.3.0"

# Ensure OMNeT++ environment is set
source "$OMNETPP_DIR/setenv"

log "Generating makefiles for Simu5G..."
make makefiles

log "Building Simu5G in release mode..."
make MODE=release -j$(nproc)

log "Simu5G built successfully."

# ------------------------------------------------------------------------------
# 9. Final Configuration (Persistence)
# ------------------------------------------------------------------------------
log "Configuring ~/.bashrc for persistence..."

BASHRC="$HOME/.bashrc"
MARKER="# OMNeT++ Environment Variables"

# Helper function to append safely
append_if_missing() {
    grep -qF "$1" "$BASHRC" || echo "$1" >> "$BASHRC"
}

# Add a header comment if not present
if ! grep -qF "$MARKER" "$BASHRC"; then
    echo -e "\n$MARKER" >> "$BASHRC"
fi

# Add Conda initialization if not present
if ! grep -q "conda initialize" "$BASHRC"; then
    log "Adding Conda initialization to ~/.bashrc..."
    cat >> "$BASHRC" << 'EOF'

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('$HOME/miniconda3/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        . "$HOME/miniconda3/etc/profile.d/conda.sh"
    else
        export PATH="$HOME/miniconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<
EOF
fi

# Add OMNeT++ environment sourcing
append_if_missing "# Source OMNeT++ environment"
append_if_missing "source $OMNETPP_DIR/setenv > /dev/null 2>&1"

# Add INET environment sourcing
append_if_missing "# Source INET environment"
append_if_missing "source $PROJECT_ROOT/inet4.5/setenv > /dev/null 2>&1"

# Add Simu5G environment sourcing (needs pushd/popd due to relative paths)
append_if_missing "# Source Simu5G environment"
append_if_missing "pushd $PROJECT_ROOT/simu5g-1.3.0 > /dev/null 2>&1"
append_if_missing "source setenv > /dev/null 2>&1"
append_if_missing "popd > /dev/null 2>&1"

log "Environment configuration added to ~/.bashrc"

# ------------------------------------------------------------------------------
# 10. Completion
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "Configuration:"
echo -e "  - GUI Support: $WITH_QTENV"
echo -e "  - Conda Environment: $ENV_NAME"
echo -e "  - OMNeT++ Location: $OMNETPP_DIR"
echo -e "\n${BLUE}Next steps:${NC}"
echo -e "1. ${GREEN}Restart your terminal${NC} or run: ${BLUE}source ~/.bashrc${NC}"
echo -e "2. Activate the conda environment: ${BLUE}conda activate $ENV_NAME${NC}"

if [[ "$WITH_QTENV" == "yes" ]]; then
    echo -e "3. To launch the OMNeT++ IDE: ${BLUE}omnetpp${NC}"
    echo -e "4. To test CLI: ${BLUE}cd $PROJECT_ROOT/simu5g-1.3.0 && . setenv && which simu5g${NC}"
else
    echo -e "3. To test: ${BLUE}cd $PROJECT_ROOT/simu5g-1.3.0 && . setenv && which simu5g${NC}"
    echo -e "\n${YELLOW}Note:${NC} GUI/IDE not installed. Use command-line tools (opp_run, etc.)"
fi

echo -e "\n${GREEN}All dependencies, Miniconda, and software have been installed successfully!${NC}"
echo -e "${BLUE}============================================================${NC}"
