#!/usr/bin/env bash
# CRZ Monitor — Production Deployment Script
# Idempotent: safe to run multiple times.
# Reads configuration from .env file in the deploy directory.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

INSTALL_DIR="/opt/crz-monitor"
SERVICE_USER="crz"
REPO_URL="https://github.com/garadice/CRZcheck.git"
REQUIRED_VARS="DATABASE_URL POSTGRES_PASSWORD APP_ENV"
MIN_DISK_GB=10

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

bail() {
    log_error "$@"
    exit 1
}

# ── Step 1: Preflight Checks ──────────────────────────────────────────────────

preflight_checks() {
    log_info "Running preflight checks..."

    if [[ $EUID -ne 0 ]]; then
        bail "This script must be run as root or with sudo."
    fi

    if [[ ! -f /etc/debian_version ]] && [[ ! -f /etc/lsb-release ]]; then
        bail "Unsupported OS. This script requires Debian or Ubuntu."
    fi

    if ! command -v docker &>/dev/null; then
        bail "Docker is not installed. Install it first: https://docs.docker.com/engine/install/"
    fi
    log_info "Docker: $(docker --version)"

    if ! docker compose version &>/dev/null; then
        bail "Docker Compose v2 is not available. Install the docker-compose-plugin package."
    fi
    log_info "Docker Compose: $(docker compose version --short)"

    local deploy_dir
    deploy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    if [[ ! -f "${deploy_dir}/.env" ]]; then
        bail ".env file not found in ${deploy_dir}"
    fi
    log_info ".env file found: ${deploy_dir}/.env"

    for var in ${REQUIRED_VARS}; do
        local val
        val=$(grep -E "^${var}=" "${deploy_dir}/.env" 2>/dev/null | head -1 | cut -d'=' -f2-)
        if [[ -z "${val}" ]]; then
            bail "Required variable ${var} is missing or empty in .env"
        fi
    done
    log_info "Required .env variables present"

    local available_gb
    available_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ "${available_gb}" -lt "${MIN_DISK_GB}" ]]; then
        bail "Insufficient disk space: ${available_gb} GB available, ${MIN_DISK_GB} GB required."
    fi
    log_info "Disk space: ${available_gb} GB available (>= ${MIN_DISK_GB} GB)"

    log_info "Preflight checks passed."
}

# ── Step 2: Create System User ────────────────────────────────────────────────

create_system_user() {
    if id "${SERVICE_USER}" &>/dev/null; then
        log_info "User '${SERVICE_USER}' already exists."
    else
        log_info "Creating system user '${SERVICE_USER}'..."
        useradd -r -m -d "${INSTALL_DIR}" -s /bin/bash "${SERVICE_USER}"
    fi

    if ! groups "${SERVICE_USER}" &>/dev/null | grep -q '\bdocker\b'; then
        usermod -aG docker "${SERVICE_USER}"
        log_info "Added '${SERVICE_USER}' to docker group."
    fi
}

# ── Step 3: Clone / Update Repository ─────────────────────────────────────────

clone_or_update_repo() {
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        log_info "Updating repository at ${INSTALL_DIR}..."
        git -C "${INSTALL_DIR}" pull origin main
    else
        log_info "Cloning repository to ${INSTALL_DIR}..."
        if [[ -d "${INSTALL_DIR}" ]]; then
            mv "${INSTALL_DIR}" "${INSTALL_DIR}.bak.$(date +%Y%m%d%H%M%S)"
        fi
        git clone "${REPO_URL}" "${INSTALL_DIR}"
    fi
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
}

# ── Step 4: Set Up .env ───────────────────────────────────────────────────────

setup_env() {
    local deploy_dir
    deploy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local target_env="${INSTALL_DIR}/.env"

    if [[ ! -f "${target_env}" ]]; then
        if [[ -f "${INSTALL_DIR}/.env.production.example" ]]; then
            cp "${INSTALL_DIR}/.env.production.example" "${target_env}"
            log_info "Copied .env.production.example to .env"
        else
            cp "${deploy_dir}/.env" "${target_env}"
            log_info "Copied .env from deploy directory."
        fi
    else
        log_info ".env already exists at ${target_env}."
    fi

    for var in ${REQUIRED_VARS}; do
        local val
        val=$(grep -E "^${var}=" "${target_env}" 2>/dev/null | head -1 | cut -d'=' -f2-)
        if [[ -z "${val}" ]]; then
            bail "Required variable ${var} is missing or empty in ${target_env}"
        fi
    done

    chmod 600 "${target_env}"
    chown "${SERVICE_USER}:${SERVICE_USER}" "${target_env}"
    log_info ".env permissions set to 600."
}

# ── Step 5: Virtual Environment + Dependencies ────────────────────────────────

install_dependencies() {
    if [[ -d "${INSTALL_DIR}/.venv" ]]; then
        log_info "Virtual environment already exists."
    else
        log_info "Creating virtual environment..."
        sudo -u "${SERVICE_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
    fi

    log_info "Installing dependencies..."
    sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/.venv/bin/pip" install -e "${INSTALL_DIR}"
}

# ── Step 6: Start PostgreSQL ──────────────────────────────────────────────────

start_postgres() {
    log_info "Starting PostgreSQL..."
    sudo -u "${SERVICE_USER}" -- docker compose \
        -f "${INSTALL_DIR}/docker-compose.yml" \
        -f "${INSTALL_DIR}/docker-compose.prod.yml" \
        up -d db

    log_info "Waiting for PostgreSQL to be ready..."
    local retries=5
    local delay=3
    local i
    for ((i = 1; i <= retries; i++)); do
        if docker exec crz_db pg_isready -U crz -d crz_monitor &>/dev/null; then
            log_info "PostgreSQL is ready."
            return 0
        fi
        log_info "Attempt ${i}/${retries}: PostgreSQL not ready, waiting ${delay}s..."
        sleep "${delay}"
    done
    bail "PostgreSQL did not become ready after ${retries} attempts."
}

# ── Step 7: Run Migrations ────────────────────────────────────────────────────

run_migrations() {
    log_info "Running database migrations..."
    sudo -u "${SERVICE_USER}" bash -c "cd ${INSTALL_DIR} && .venv/bin/alembic upgrade head"
    log_info "Migrations complete."
}

# ── Step 8: Install Systemd Units ─────────────────────────────────────────────

install_systemd_units() {
    log_info "Installing systemd unit files..."

    cat > /etc/systemd/system/crz-dashboard.service << 'UNIT'
[Unit]
Description=CRZ Monitor Dashboard (Streamlit)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=crz
Group=crz
WorkingDirectory=/opt/crz-monitor
ExecStart=/opt/crz-monitor/.venv/bin/streamlit run app/dashboard/Home.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
Restart=on-failure
RestartSec=10
MemoryMax=1G
Environment=APP_ENV=production
EnvironmentFile=-/opt/crz-monitor/.env

[Install]
WantedBy=multi-user.target
UNIT

    cat > /etc/systemd/system/crz-ingestion.service << 'UNIT'
[Unit]
Description=CRZ Data Ingestion
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=crz
Group=crz
WorkingDirectory=/opt/crz-monitor
ExecStart=/opt/crz-monitor/.venv/bin/python -m app.ingestion.jobs
TimeoutStartSec=4h
Environment=APP_ENV=production
Environment=LOG_LEVEL=INFO
EnvironmentFile=-/opt/crz-monitor/.env
UNIT

    cat > /etc/systemd/system/crz-ingestion.timer << 'UNIT'
[Unit]
Description=CRZ Daily Ingestion Timer

[Timer]
OnCalendar=*-*-* 02:00:00 Europe/Bratislava
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
UNIT

    systemctl daemon-reload
    log_info "Systemd units installed and daemon reloaded."

    systemctl enable crz-dashboard crz-ingestion.timer
    log_info "Enabled crz-dashboard and crz-ingestion.timer."
}

# ── Step 9: Print Next Steps ──────────────────────────────────────────────────

print_next_steps() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  CRZ Monitor — Deployment Complete${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Edit .env with a strong POSTGRES_PASSWORD:"
    echo "     nano ${INSTALL_DIR}/.env"
    echo ""
    echo "  2. Start the dashboard:"
    echo "     systemctl start crz-dashboard"
    echo ""
    echo "  3. Set up nginx as reverse proxy (see deployment checklist for config example)."
    echo ""
    echo "  4. Run the first ingestion:"
    echo "     sudo -u ${SERVICE_USER} ${INSTALL_DIR}/.venv/bin/python -m app.ingestion.jobs"
    echo ""
    echo "  5. Run the smoke test:"
    echo "     bash ${INSTALL_DIR}/scripts/smoke-test.sh"
    echo ""
    echo "  Note: No automated backups are configured."
    echo "  All data comes from the public CRZ API — if the database dies,"
    echo "  just re-ingest (takes ~4-8 hours for a full 90-day window)."
    echo "  You can run a manual backup anytime with: make backup"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

# ── Main ───────────────────────────────────────────────────────────────────────

main() {
    preflight_checks
    create_system_user
    clone_or_update_repo
    setup_env
    install_dependencies
    start_postgres
    run_migrations
    install_systemd_units
    print_next_steps
}

main "$@"
