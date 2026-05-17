#!/usr/bin/env bash
# Configure Caddy for CRZ Monitor
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="/etc/caddy"

if [ ! -f "${SCRIPT_DIR}/Caddyfile" ]; then
    echo "[ERROR] Caddyfile not found in ${SCRIPT_DIR}"
    exit 1
fi

# Check if Caddyfile has placeholder hash
if grep -q "<BCRYPT_HASH>" "${SCRIPT_DIR}/Caddyfile"; then
    echo "[ERROR] Caddyfile still contains <BCRYPT_HASH> placeholder."
    echo "Generate a hash: caddy hash-password --plaintext 'your-password'"
    echo "Then edit ${SCRIPT_DIR}/Caddyfile and replace <BCRYPT_HASH>"
    exit 1
fi

echo "[INFO] Copying Caddyfile to ${DEPLOY_DIR}..."
sudo cp "${SCRIPT_DIR}/Caddyfile" "${DEPLOY_DIR}/Caddyfile"

echo "[INFO] Validating Caddyfile..."
caddy validate --config "${DEPLOY_DIR}/Caddyfile" --adapter caddyfile

echo "[INFO] Restarting Caddy..."
sudo systemctl restart caddy

echo "[INFO] Caddy configured. Checking status..."
sudo systemctl status caddy --no-pager
