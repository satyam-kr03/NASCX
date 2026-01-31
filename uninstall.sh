#!/bin/bash

# ==============================================================================
# NASCX Uninstaller
# ==============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASHRC="$HOME/.bashrc"
ENV_NAME="omnetpp"

log() { echo -e "${BLUE}[NASCX Uninstaller]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

echo -e "${RED}============================================================${NC}"
echo -e "${RED}              NASCX Cleanup & Uninstall                     ${NC}"
echo -e "${RED}============================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Clean up .bashrc
# ------------------------------------------------------------------------------
if [ -f "$BASHRC" ]; then
    log "Found .bashrc. Creating a backup at ${BASHRC}.bak_nascx..."
    cp "$BASHRC" "${BASHRC}.bak_nascx"

    log "Removing NASCX environment variables from .bashrc..."

    # We use sed to delete lines containing the specific paths used in install.sh
    # We also remove the comment marker
    sed -i '/# NASCX Environment Variables/d' "$BASHRC"
    sed -i '/# Omnet++ Environment Variables/d' "$BASHRC"
    sed -i '/omnetpp-6.2.0\/setenv/d' "$BASHRC"
    sed -i '/inet4.5\/setenv/d' "$BASHRC"
    sed -i '/simu5g-1.3.0/d' "$BASHRC"
    sed -i '/source setenv > \/dev\/null/d' "$BASHRC"
    sed -i '/popd > \/dev\/null/d' "$BASHRC"

    success ".bashrc cleaned."
else
    warn ".bashrc not found. Skipping path cleanup."
fi

# ------------------------------------------------------------------------------
# 2. Conda Environment Removal (Interactive - only if conda is available)
# ------------------------------------------------------------------------------
echo ""
log "Checking for Conda..."

if command -v conda &> /dev/null; then
    # Initialize conda for script usage
    eval "$(conda shell.bash hook)"

    if conda info --envs | grep -q "^$ENV_NAME "; then
        echo -e "${YELLOW}The Conda environment '$ENV_NAME' was found.${NC}"
        read -p "Do you want to delete this environment? (y/N): " confirm

        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            log "Removing Conda environment '$ENV_NAME'..."
            
            # Deactivate if currently active to prevent errors
            if [[ "$CONDA_DEFAULT_ENV" == "$ENV_NAME" ]]; then
                conda deactivate
            fi

            conda env remove -n $ENV_NAME -y
            success "Environment '$ENV_NAME' removed."
        else
            log "Skipping Conda environment removal."
        fi
    else
        log "Conda environment '$ENV_NAME' not found. Nothing to remove."
    fi
else
    log "Conda is not installed. Skipping Conda environment check."
fi

# ------------------------------------------------------------------------------
# 3. Final cleanup note
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}Uninstall steps completed.${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "1. Please run: ${BLUE}source ~/.bashrc${NC} (or restart terminal) to apply changes."
echo -e "2. The project files in '$(pwd)' were NOT deleted."
echo -e "   If you want to fully remove the project, run: cd .. && rm -rf NASCX"