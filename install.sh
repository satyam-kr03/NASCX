#!/bin/bash

# ==============================================================================
# Installer: OMNeT++ 6.2.0, INET 4.5.4, Simu5G 1.3.0
# ==============================================================================

set -e  # Exit immediately if a command exits with a non-zero status

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
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

log "Starting installation in: $PROJECT_ROOT"

# ------------------------------------------------------------------------------
# 1. Prerequisite Checks
# ------------------------------------------------------------------------------
log "Checking prerequisites..."

if ! command -v conda &> /dev/null; then
    error "Conda is not installed or not in your PATH. Please install Miniconda or Anaconda first."
fi

# Initialize Conda for this script session
eval "$(conda shell.bash hook)"

# ------------------------------------------------------------------------------
# 2. GUI Installation Option
# ------------------------------------------------------------------------------
echo -e "${BLUE}[Installer]${NC} Do you want to install OMNeT++ with GUI support (IDE)?"
echo -e "  This requires Qt libraries and will enable the graphical IDE."
echo -e "  Choose 'no' for headless/command-line only installation."
read -p "Install with GUI support? (yes/no) [default: no]: " GUI_CHOICE

# Default to 'no' if empty
GUI_CHOICE=${GUI_CHOICE:-no}

# Normalize input
GUI_CHOICE=$(echo "$GUI_CHOICE" | tr '[:upper:]' '[:lower:]')

if [[ "$GUI_CHOICE" == "yes" || "$GUI_CHOICE" == "y" ]]; then
    WITH_QTENV="yes"
    WITH_OSG="yes"
    log "GUI support enabled. Qt libraries will be required."
else
    WITH_QTENV="no"
    WITH_OSG="no"
    log "GUI support disabled. Command-line only installation."
fi

# ------------------------------------------------------------------------------
# 3. Conda Environment Setup
# ------------------------------------------------------------------------------
ENV_NAME="omnetpp"

if conda info --envs | grep -q "^$ENV_NAME "; then
    log "Conda environment '$ENV_NAME' already exists. Activating..."
    conda activate $ENV_NAME
else
    log "Creating Conda environment '$ENV_NAME' with Python 3.12..."
    conda create -n $ENV_NAME python=3.12 -y
    conda activate $ENV_NAME
fi

log "Installing build dependencies..."
if [[ "$WITH_QTENV" == "yes" ]]; then
    log "Installing Qt5 for GUI support..."
    conda install -c conda-forge bison flex pyqt=5 python-devtools -y
else
    conda install -c conda-forge bison flex python-devtools -y
fi

# ------------------------------------------------------------------------------
# 4. Download and Build OMNeT++ 6.2.0
# ------------------------------------------------------------------------------
OMNETPP_VERSION="6.2.0"
OMNETPP_DIR="$PROJECT_ROOT/omnetpp-6.2.0"
OMNETPP_TGZ="omnetpp-${OMNETPP_VERSION}-linux-x86_64.tgz"
OMNETPP_URL="https://github.com/omnetpp/omnetpp/releases/download/omnetpp-${OMNETPP_VERSION}/${OMNETPP_TGZ}"

if [ ! -d "$OMNETPP_DIR" ]; then
    log "OMNeT++ ${OMNETPP_VERSION} not found. Downloading..."
    cd "$PROJECT_ROOT"
    
    if [ ! -f "$OMNETPP_TGZ" ]; then
        wget "$OMNETPP_URL" || error "Failed to download OMNeT++"
    fi
    
    log "Extracting OMNeT++..."
    tar xzf "$OMNETPP_TGZ" || error "Failed to extract OMNeT++"
    
    log "Cleaning up downloaded archive..."
    rm -f "$OMNETPP_TGZ"
else
    log "OMNeT++ ${OMNETPP_VERSION} directory already exists."
fi

log "Building OMNeT++ ${OMNETPP_VERSION}..."
cd "$OMNETPP_DIR"

# Copy configure.user.dist to configure.user if it doesn't exist
if [ ! -f "configure.user" ]; then
    log "Generating configure.user with selected options..."
    cp configure.user.dist configure.user
fi

# Modify configure.user based on GUI choice
sed -i "s/^WITH_QTENV=.*/WITH_QTENV=$WITH_QTENV/" configure.user
sed -i "s/^WITH_OSG=.*/WITH_OSG=$WITH_OSG/" configure.user

log "Configuration: WITH_QTENV=$WITH_QTENV, WITH_OSG=$WITH_OSG"

# Source setenv to set up PATH and libraries for the build process
source setenv

# Install Python requirements for OMNeT++ AFTER sourcing setenv
# This ensures packages are installed for the Python that configure will find
log "Installing Python requirements for OMNeT++..."
python3 -m pip install --upgrade -r "$OMNETPP_DIR/python/requirements.txt"

# Ensure conda's lib directory is in the library path for Python embedding support
# This is needed because conda's python3-config assumes libpython is in a standard path
# LIBRARY_PATH is used at link time, LD_LIBRARY_PATH at runtime
export LIBRARY_PATH="$CONDA_PREFIX/lib:$LIBRARY_PATH"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

# Configure and Build
./configure
make -j$(nproc)

# ------------------------------------------------------------------------------
# 5. Build INET 4.5
# ------------------------------------------------------------------------------
log "Building INET 4.5..."

if [ ! -d "$PROJECT_ROOT/inet4.5" ]; then
    error "Directory inet4.5 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/inet4.5"
# Re-source OMNeT++ setenv just in case
source setenv
source "$OMNETPP_DIR/setenv"

make makefiles
make MODE=release -j$(nproc)

# ------------------------------------------------------------------------------
# 6. Build Simu5G 1.3.0
# ------------------------------------------------------------------------------
log "Building Simu5G 1.3.0..."

if [ ! -d "$PROJECT_ROOT/simu5g-1.3.0" ]; then
    error "Directory simu5g-1.3.0 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/simu5g-1.3.0"
source "$OMNETPP_DIR/setenv"

make makefiles
make MODE=release -j$(nproc)

# ------------------------------------------------------------------------------
# 7. Final Configuration (Persistence)
# ------------------------------------------------------------------------------
log "Configuring ~/.bashrc for persistence..."

BASHRC="$HOME/.bashrc"
MARKER="# Omnet++ Environment Variables"

# Helper function to append safely
append_if_missing() {
    grep -qF "$1" "$BASHRC" || echo "$1" >> "$BASHRC"
}

# Add a header comment if not present
grep -qF "$MARKER" "$BASHRC" || echo -e "\n$MARKER" >> "$BASHRC"

# Add source commands using the absolute PROJECT_ROOT
append_if_missing "source $OMNETPP_DIR/setenv > /dev/null 2>&1"
append_if_missing "source $PROJECT_ROOT/inet4.5/setenv > /dev/null 2>&1"

# ------------------------------------------------------------------------------
# 8. Completion
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "Configuration: GUI Support = $WITH_QTENV"
echo -e "\nNext steps:"
echo -e "1. Apply environment changes: ${BLUE}source ~/.bashrc${NC}"
echo -e "2. Activate the conda environment: ${BLUE}conda activate $ENV_NAME${NC}"
if [[ "$WITH_QTENV" == "yes" ]]; then
    echo -e "3. To launch the IDE, run: ${BLUE}omnetpp${NC}"
    echo -e "4. To test CLI, run: ${BLUE}cd simu5g-1.3.0 && . setenv && which simu5g${NC}"
else
    echo -e "3. To test, run: ${BLUE}cd simu5g-1.3.0 && . setenv && which simu5g${NC}"
    echo -e "\nNote: GUI/IDE not installed. Use command-line tools (opp_run, etc.)"
fi
