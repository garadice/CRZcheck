#!/usr/bin/env bash
# Install Caddy web server on Debian/Ubuntu
set -euo pipefail

echo "[INFO] Installing Caddy..."

sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

echo "[INFO] Caddy installed: $(caddy version)"
echo "[INFO] Copy Caddyfile to /etc/caddy/Caddyfile and run: sudo systemctl restart caddy"
