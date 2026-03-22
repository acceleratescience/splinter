#!/bin/bash
# =============================================================================
# Setup Script for LiteLLM/vLLM Stack
# =============================================================================
#
# Run from repo root:  ./scripts/llm-service.sh
# Or from stack dir:   ./llm-service.sh (if you copy/symlink it there)
#
# =============================================================================

set -euo pipefail

# Determine script and stack directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're running from the scripts directory or the stack directory
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    # Running from repo root via ./scripts/llm-service.sh
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
    STACK_DIR="${REPO_ROOT}/stacks/llm-service"
else
    # Running directly from stack directory
    STACK_DIR="$SCRIPT_DIR"
fi

# nginx
if ! command -v nginx &> /dev/null; then
    echo "Nginx not found. Installing..."
    sudo apt-get update && sudo apt-get install -y nginx
fi

echo "=========================================="
echo "LiteLLM/vLLM Stack Setup"
echo "=========================================="
echo "Stack directory: ${STACK_DIR}"
echo ""

# Check for .env file
if [ ! -f "${STACK_DIR}/.env" ]; then
    echo "ERROR: .env file not found at ${STACK_DIR}/.env"
    echo ""
    echo "Create it from the example:"
    echo "  cp ${STACK_DIR}/.env.example ${STACK_DIR}/.env"
    echo "  nano ${STACK_DIR}/.env"
    exit 1
fi

# Load environment variables
export $(cat "${STACK_DIR}/.env" | grep -v '^#' | grep -v '^$' | xargs)

# Validate required variables
REQUIRED_VARS="POSTGRES_PASSWORD LITELLM_MASTER_KEY DOMAIN LITELLM_PORT"
for var in $REQUIRED_VARS; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set in .env"
        exit 1
    fi
done

echo "[1/7] Generating Nginx configuration..."
envsubst '${DOMAIN} ${LITELLM_PORT}' < "${STACK_DIR}/nginx.conf.template" > "${STACK_DIR}/${DOMAIN}"
echo "      Generated: ${STACK_DIR}/${DOMAIN}"

echo "[2/7] Installing security snippet..."
sudo mkdir -p /etc/nginx/snippets
sudo cp "${STACK_DIR}/security.conf.template" /etc/nginx/snippets/llm-security.conf

echo "[3/7] Installing Nginx configuration..."
sudo cp "${STACK_DIR}/${DOMAIN}" /etc/nginx/sites-available/
if [ ! -L "/etc/nginx/sites-enabled/${DOMAIN}" ]; then
    sudo ln -s "/etc/nginx/sites-available/${DOMAIN}" /etc/nginx/sites-enabled/
fi

# Remove default Nginx site if present
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

echo "[4/7] Testing Nginx configuration..."
sudo nginx -t

echo "[5/7] Reloading Nginx..."
sudo systemctl reload nginx

echo "[6/7] Installing and configuring fail2ban..."
if ! command -v fail2ban-server &> /dev/null; then
    sudo apt-get update && sudo apt-get install -y fail2ban
fi

sudo cp "${STACK_DIR}/fail2ban-jail.local" /etc/fail2ban/jail.local
sudo cp "${STACK_DIR}/filters/nginx-llm-blocked.conf" /etc/fail2ban/filter.d/
sudo cp "${STACK_DIR}/filters/nginx-llm-auth.conf" /etc/fail2ban/filter.d/
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

echo "[7/7] Starting Docker stack..."
cd "${STACK_DIR}"
docker compose up -d

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  View logs:          cd ${STACK_DIR} && docker compose logs -f"
echo "  Stop stack:         cd ${STACK_DIR} && docker compose down"
echo "  Restart stack:      cd ${STACK_DIR} && docker compose restart"
echo ""
echo "Next steps:"
echo "  1. Add TLS:         sudo certbot --nginx -d ${DOMAIN}"
echo "  2. Access admin UI: ssh -fN -L ${LITELLM_PORT}:localhost:${LITELLM_PORT} user@server"
echo "                      Then visit http://localhost:${LITELLM_PORT}/ui"
echo ""