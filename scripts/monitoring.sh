#!/bin/bash
# =============================================================================
# Setup Script for Monitoring Stack (Prometheus, Grafana, Node Exporter, DCGM)
# =============================================================================
#
# Run from repo root:  ./scripts/monitoring.sh
# Or from stack dir:   ./monitoring.sh (if you copy/symlink it there)
#
# =============================================================================

set -euo pipefail

# Determine script and stack directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're running from the scripts directory or the stack directory
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    # Running from repo root via ./scripts/monitoring.sh
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
    STACK_DIR="${REPO_ROOT}/stacks/monitoring"
else
    # Running directly from stack directory
    STACK_DIR="$SCRIPT_DIR"
fi

echo "=========================================="
echo "Monitoring Stack Setup"
echo "=========================================="
echo "Stack directory: ${STACK_DIR}"
echo ""

# ==================== Pre-flight Checks ====================
echo "[1/6] Running pre-flight checks..."

# Check Docker is running
if ! systemctl is-active --quiet docker; then
    echo "ERROR: Docker is not running"
    echo "Start it with: sudo systemctl start docker"
    exit 1
fi
echo "      Docker: OK"

# Check NVIDIA Container Toolkit
if ! docker info --format '{{.Runtimes}}' | grep -q nvidia; then
    echo "ERROR: NVIDIA Container Toolkit not configured"
    exit 1
fi
echo "      NVIDIA runtime: OK"

# Test GPU access
if ! command -v nvidia-smi &> /dev/null || ! nvidia-smi > /dev/null 2>&1; then
    echo "ERROR: Cannot access GPU (nvidia-smi failed)"
    exit 1
fi
echo "      GPU access: OK"

# Check stack directory exists
if [ ! -f "${STACK_DIR}/docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found at ${STACK_DIR}"
    exit 1
fi
echo "      Stack files: OK"

# ==================== Deploy Stack ====================
echo ""
echo "[2/6] Pulling latest Docker images..."
cd "${STACK_DIR}"
docker compose pull

echo ""
echo "[3/6] Starting monitoring stack..."
docker compose up -d

# ==================== Health Checks ====================
echo ""
echo "[4/6] Waiting for Prometheus..."
for i in {1..12}; do
    if curl -sf http://localhost:9090/-/ready > /dev/null 2>&1; then
        echo "      Prometheus: OK"
        break
    fi
    if [ $i -eq 12 ]; then
        echo "      Prometheus: TIMEOUT (check logs with: docker logs monitoring-prom)"
    fi
    sleep 5
done

echo "[5/6] Waiting for Grafana..."
for i in {1..12}; do
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "      Grafana: OK"
        break
    fi
    if [ $i -eq 12 ]; then
        echo "      Grafana: TIMEOUT (check logs with: docker logs monitoring-grafana)"
    fi
    sleep 5
done

echo "[6/6] Checking exporters..."
if curl -sf http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "      Node Exporter: OK"
else
    echo "      Node Exporter: FAILED"
fi

if curl -sf http://localhost:9400/metrics > /dev/null 2>&1; then
    echo "      DCGM Exporter: OK"
else
    echo "      DCGM Exporter: FAILED"
fi

echo ""
echo "=========================================="
echo "Monitoring Stack Deployed Successfully!"
echo "=========================================="
echo ""
echo "Security Note:"
echo "  All services are bound to 127.0.0.1 for security."
echo "  To access them from your laptop, use an SSH tunnel:"
echo "  ssh -L 3000:localhost:3000 user@$(hostname -I | awk '{print $1}')"
echo ""
echo "Services (via tunnel):"
echo "  - Grafana:       http://localhost:3000"
echo "  - Prometheus:    http://localhost:9090"
echo ""
echo "Grafana default credentials: admin / admin"
echo ""
echo "Next steps in Grafana:"
echo "  1. Add Data Source -> Prometheus"
echo "  2. URL: http://prometheus:9090  <-- (Use internal Docker DNS)"
echo "  3. Import Dashboards: 1860 (Node), 12239 (GPU)"
echo ""