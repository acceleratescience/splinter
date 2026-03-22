#!/bin/bash
# =============================================================================
# GPU Server Base Setup Script
# =============================================================================
#
# Installs and configures:
#   - Base dependencies (git, htop, nvtop, tmux, etc.)
#   - Docker with Compose plugin
#   - NVIDIA drivers
#   - NVIDIA Container Toolkit
#
# Run with: sudo ./scripts/setup.sh
#
# =============================================================================

set -euo pipefail

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Configuration
DOCKER_USERS="${DOCKER_USERS:-ubuntu}"  # Comma-separated list, or set via env var
NVIDIA_DRIVER_VERSION="550"
KEYRING_DIR="/etc/apt/keyrings"
REPO_URL="https://github.com/acceleratescience/splinter.git"
REPO_PATH="/root/splinter"

# Detect architecture
ARCH=$(dpkg --print-architecture)

echo "=========================================="
echo "GPU Server Base Setup"
echo "=========================================="
echo "Architecture: ${ARCH}"
echo "Docker users: ${DOCKER_USERS}"
echo ""

# ==================== System Updates ====================
echo "[1/7] Installing base dependencies..."
apt-get update
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    htop \
    nvtop \
    tmux

# ==================== Clone Repository ====================
echo ""
echo "[2/7] Cloning server infrastructure (Splinter) repository..."
if [ -d "${REPO_PATH}" ]; then
    cd "${REPO_PATH}"
    git pull
fi

# ==================== Docker Installation ====================
echo ""
echo "[3/7] Installing Docker..."

# Create keyrings directory
mkdir -p "${KEYRING_DIR}"

# Add Docker GPG key
if [ ! -f "${KEYRING_DIR}/docker.asc" ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o "${KEYRING_DIR}/docker.asc"
    chmod 644 "${KEYRING_DIR}/docker.asc"
fi

# Add Docker repository
UBUNTU_CODENAME=$(lsb_release -cs)
echo "deb [arch=${ARCH} signed-by=${KEYRING_DIR}/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" > /etc/apt/sources.list.d/docker.list

# Install Docker
apt-get update
apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-compose-plugin

# Add users to docker group
IFS=',' read -ra USERS <<< "${DOCKER_USERS}"
for user in "${USERS[@]}"; do
    user=$(echo "$user" | xargs)  # Trim whitespace
    if id "$user" &>/dev/null; then
        usermod -aG docker "$user"
        echo "      Added ${user} to docker group"
    else
        echo "      Warning: User ${user} does not exist, skipping"
    fi
done

# ==================== NVIDIA Driver Installation ====================
echo ""
echo "[4/7] Installing NVIDIA driver ${NVIDIA_DRIVER_VERSION}..."

# Check if driver is already installed and working
if nvidia-smi &>/dev/null; then
    echo "      NVIDIA driver already installed and working"
    NEEDS_REBOOT=false
else
    apt-get install -y "nvidia-driver-${NVIDIA_DRIVER_VERSION}"
    NEEDS_REBOOT=true
fi

# ==================== NVIDIA Container Toolkit ====================
echo ""
echo "[5/7] Installing NVIDIA Container Toolkit..."

# Add NVIDIA GPG key
if [ ! -f "${KEYRING_DIR}/nvidia-container-toolkit.asc" ]; then
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o "${KEYRING_DIR}/nvidia-container-toolkit.asc"
    chmod 644 "${KEYRING_DIR}/nvidia-container-toolkit.asc"
fi

# Add NVIDIA repository
echo "deb [signed-by=${KEYRING_DIR}/nvidia-container-toolkit.asc] https://nvidia.github.io/libnvidia-container/stable/deb/\$(ARCH) /" > /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
apt-get update
apt-get install -y nvidia-container-toolkit

# ==================== Configure Docker for NVIDIA ====================
echo ""
echo "[6/7] Configuring Docker for NVIDIA runtime..."

# Configure only if not already configured
if ! grep -q "nvidia" /etc/docker/daemon.json 2>/dev/null; then
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    echo "      Docker configured for NVIDIA runtime"
else
    echo "      Docker already configured for NVIDIA runtime"
fi

# ==================== Verification ====================
echo ""
echo "[7/7] Verifying installation..."

# Check Docker
if docker --version &>/dev/null; then
    echo "      Docker: OK ($(docker --version | cut -d' ' -f3 | tr -d ','))"
else
    echo "      Docker: FAILED"
fi

# Check NVIDIA driver
if nvidia-smi &>/dev/null; then
    echo "      NVIDIA Driver: OK"
    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | while read line; do
        echo "        - ${line}"
    done
else
    echo "      NVIDIA Driver: NOT READY (reboot required)"
fi

# Check NVIDIA Container Toolkit
if docker info 2>/dev/null | grep -q nvidia; then
    echo "      NVIDIA Container Toolkit: OK"
else
    echo "      NVIDIA Container Toolkit: NOT READY (reboot may be required)"
fi

# ==================== Summary ====================
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""

if [ "${NEEDS_REBOOT:-false}" = true ]; then
    echo "*** REBOOT REQUIRED ***"
    echo ""
    echo "The NVIDIA driver was installed and requires a reboot."
    echo "Run: sudo reboot"
    echo ""
    echo "After reboot, verify with:"
    echo "  nvidia-smi"
    echo "  docker run --rm --gpus all nvidia/cuda:12.6.1-base-ubuntu24.04 nvidia-smi"
else
    echo "No reboot required."
    echo ""
    echo "Verify GPU access in Docker:"
    echo "  docker run --rm --gpus all nvidia/cuda:12.6.1-base-ubuntu24.04 nvidia-smi"
fi

echo ""
echo "Note: Users added to the docker group may need to log out"
echo "and back in, or run 'newgrp docker' to use Docker without sudo."
echo ""