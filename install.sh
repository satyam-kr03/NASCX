#!/bin/bash

# ==============================================================================
# NASCX Installer: OMNeT++ 6.2.0, INET 4.5.4, Simu5G 1.3.0
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
    echo -e "${BLUE}[NASCX Installer]${NC} $1"
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
# 2. Conda Environment Setup
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
conda install -c conda-forge bison flex -y

# ------------------------------------------------------------------------------
# 3. Build OMNeT++ 6.2.0
# ------------------------------------------------------------------------------
log "Building OMNeT++ 6.2.0..."

if [ ! -d "$PROJECT_ROOT/omnetpp-6.2.0" ]; then
    error "Directory omnetpp-6.2.0 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/omnetpp-6.2.0"

# Copy configure.user if it doesn't exist
if [ ! -f "configure.user" ]; then
    cp configure.user.dist configure.user
fi

# Source setenv to set up PATH and libraries for the build process
source setenv

# Configure and Build
./configure
make -j$(nproc)

# ------------------------------------------------------------------------------
# 4. Build INET 4.5
# ------------------------------------------------------------------------------
log "Building INET 4.5..."

if [ ! -d "$PROJECT_ROOT/inet4.5" ]; then
    error "Directory inet4.5 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/inet4.5"
# Re-source OMNeT++ setenv just in case
source setenv
source "$PROJECT_ROOT/omnetpp-6.2.0/setenv"

make makefiles
make MODE=release -j$(nproc)

# ------------------------------------------------------------------------------
# 5. Build Simu5G 1.3.0
# ------------------------------------------------------------------------------
log "Building Simu5G 1.3.0..."

if [ ! -d "$PROJECT_ROOT/simu5g-1.3.0" ]; then
    error "Directory simu5g-1.3.0 not found in $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT/simu5g-1.3.0"
source "$PROJECT_ROOT/omnetpp-6.2.0/setenv"

make makefiles
make MODE=release -j$(nproc)

# ------------------------------------------------------------------------------
# 6. Final Configuration (Persistence)
# ------------------------------------------------------------------------------
log "Configuring ~/.bashrc for persistence..."

BASHRC="$HOME/.bashrc"
MARKER="# NASCX Environment Variables"

# Helper function to append safely
append_if_missing() {
    grep -qF "$1" "$BASHRC" || echo "$1" >> "$BASHRC"
}

# Add a header comment if not present
grep -qF "$MARKER" "$BASHRC" || echo -e "\n$MARKER" >> "$BASHRC"

# Add source commands using the absolute PROJECT_ROOT
append_if_missing "source $PROJECT_ROOT/omnetpp-6.2.0/setenv > /dev/null 2>&1"
append_if_missing "source $PROJECT_ROOT/inet4.5/setenv > /dev/null 2>&1"
append_if_missing ". $PROJECT_ROOT/simu5g-1.3.0/setenv > /dev/null 2>&1"

# ------------------------------------------------------------------------------
# 7. Completion
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "1. Please restart your terminal or run: ${BLUE}source ~/.bashrc${NC}"
echo -e "2. To start working, always activate the env: ${BLUE}conda activate $ENV_NAME${NC}"
echo -e "3. To test, run: ${BLUE}cd simu5g-1.3.0/simulations && ./run${NC} (if a run script exists)"
