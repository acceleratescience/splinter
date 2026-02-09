# Initial Setup

In this section, we walk through the process behind setting up the server so that it is ready to serve LLMs. It essentially involves a walkthrough the [`./scripts/setup.sh`](../scripts/setup.sh) file. This file installs and configures:
   - Base dependencies (git, htop, nvtop, tmux, etc.)
   - Docker with Compose plugin
   - NVIDIA drivers
   - NVIDIA Container Toolkit


```bash
set -euo pipefail

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi
```
The set `-euo pipefail` line is a safety net:

`-e`: exit immediately if any command fails  
`-u`: treat unset variables as errors  
`-o pipefail`: if any command in a pipeline fails, the whole pipeline fails  

We also check that we are running as root.

```bash
# Configuration
DOCKER_USERS="${DOCKER_USERS:-ubuntu}"  # Comma-separated list, or set via env var
NVIDIA_DRIVER_VERSION="550"
KEYRING_DIR="/etc/apt/keyrings"
REPO_URL="https://github.com/acceleratescience/splinter.git"
REPO_PATH="/root/splinter"

# Detect architecture
ARCH=$(dpkg --print-architecture)
```
`DOCKER_USERS="${DOCKER_USERS:-ubuntu}"`
The :- syntax is bash's default value operator. It checks if DOCKER_USERS exists as an environment variable and has a value. If yes, use it. If no, fall back to ubuntu. This lets you customise without editing the script itself.

`NVIDIA_DRIVER_VERSION="550"`
Hardcoded driver version. The 550 series is the current production branch. Pinning it avoids surprises — you don't want a setup script pulling a different driver version six months from now and breaking something. When you want to upgrade, you change this deliberately.

`KEYRING_DIR="/etc/apt/keyrings"`
This is where modern Ubuntu expects third-party GPG keys to live. Older methods used apt-key add which dumped everything into one global keyring — messy and deprecated. The new approach stores each vendor's key as a separate file, and you reference it explicitly in the repo definition. More secure, easier to audit.

`REPO_URL and REPO_PATH`
Where to fetch your infrastructure code from, and where to put it locally. Using /root/ means it's only accessible to root, which makes sense for server config files you don't want regular users poking at.

`ARCH=$(dpkg --print-architecture)`
Command substitution. Runs dpkg --print-architecture, which outputs amd64 on standard x86_64 servers (or arm64 on ARM). That string gets stored in ARCH and used later when adding repositories, so apt fetches packages compiled for the right CPU architecture.


```bash
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
```
This section just installs some simple base dependencies. Many of these will already be installed by your sys-admin, but if you have a bare metal instance, you'll need them.

```bash
# ==================== Clone Repository ====================
echo ""
echo "[2/7] Cloning server infrastructure (Splinter) repository..."
if [ -d "${REPO_PATH}" ]; then
    cd "${REPO_PATH}"
    git pull
fi
```
This is handy to get new changes if any have been made.

```bash
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
```
This section takes care of the docker installation if it's not already available on your machine. The important section is adding users to the docker group. Without this, regular users cannot run Docker commands -- you'll get an error like:
```bash
permission denied while trying to connect to the Docker daemon socket
```
and you'd have to `sudo` every Docker command, which is tedious, and could cause permission problems where containers creae files as root. Obviously, doing this gives users root-equivalent access to the system, so only add users you trust. Typically, you wouldn't give access willy-nilly to people, so these users would be your core operators.

```bash
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
```
This takes care of the NVIDIA Drivers. At the top of the script, we set the version explicitely. You might have run `nvidia-smi` before, and get some output showing the driver and GPU versions, and some other information like power and VRAM usage. If this command works, then you already have the drivers. We usually need to reboot after installing the drivers. Don't worry, you won't suddenly be kicked off your server.

```bash
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
```
In order to use GPUs in a container, you need the NVIDIA Container Toolkit. Before this, GPU passthrough to Docker containers was difficult. This makes things easy. You can think of the NVIDIA Drivers and Container Toolkit as:

- The Drivers let the host machine actually able to use the GPUs  
- The Container Toolkit will let containers see them, but we still need to do some configuration:

```bash
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
```
By default, Docker uses the `runc` runtime, and it has no idea what a GPU is. It treats a graphics card like any other piece of "unknown" hardware and essentially ignores it for security and simplicity. This section says to Docker, "If I ever pass you flags mentioning GPUs (e.g. `--gpus all`), then use this special NVIDIA runtime." This runtime basically tells Docker what GPUs are and how to user them.

```bash
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
```
These final parts are just verifying that all of the previous steps worked. Hopefully, if there was an error, then it would tell you!

## The playbook
You can find an analogous file for the ansible playbook in [`./ansible/playbooks/setup.yml`](../ansible/playbooks/setup.yml). The steps and content are basically identical, but the format is in `yml` instead of a `sh` script.