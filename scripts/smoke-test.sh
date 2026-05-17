#!/usr/bin/env bash
# CRZ Monitor — Post-deployment Smoke Test
# Run after deploying to verify all components are working.
# Exit codes: 0 = all PASS, 1 = any FAIL, 2 = WARN but no FAIL.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

INSTALL_DIR="/opt/crz-monitor"
VENV_BIN="${INSTALL_DIR}/.venv/bin"
DB_CONTAINER="${DB_CONTAINER:-crz_db}"
HAS_FAIL=0
HAS_WARN=0

pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    HAS_FAIL=1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
    HAS_WARN=1
}

# ── 1. Docker PostgreSQL ──────────────────────────────────────────────────────

check_docker_postgres() {
    local status
    status=$(docker ps --filter "name=${DB_CONTAINER}" --format '{{.Status}}' 2>/dev/null || true)

    if [[ "${status}" == *"healthy"* ]]; then
        pass "Docker PostgreSQL is healthy"
    else
        fail "Docker PostgreSQL is not healthy (status: ${status:-not found})"
        return
    fi

    if docker exec "${DB_CONTAINER}" pg_isready -U crz -d crz_monitor &>/dev/null; then
        pass "PostgreSQL accepts connections"
    else
        fail "PostgreSQL pg_isready check failed"
    fi
}

# ── 2. Database Migrations ────────────────────────────────────────────────────

check_migrations() {
    if sudo -u crz "${VENV_BIN}/alembic" current &>/dev/null; then
        pass "Database migrations up to date"
    else
        fail "Database migrations check failed (alembic current returned error)"
    fi
}

# ── 3. Streamlit Dashboard ───────────────────────────────────────────────────

check_dashboard() {
    if curl -sf -o /dev/null http://127.0.0.1:8501/_stcore/health 2>/dev/null; then
        pass "Streamlit dashboard responding on :8501"
    else
        fail "Streamlit dashboard not responding on :8501"
    fi

    local caddy_domain="${CADDY_DOMAIN:-crz.bacimo.net}"
    if curl -sf -o /dev/null "https://${caddy_domain}/_stcore/health" 2>/dev/null; then
        pass "Dashboard reachable via Caddy (https://${caddy_domain})"
    else
        warn "Dashboard not reachable via Caddy (may not be configured yet)"
    fi
}

# ── 4. Data Freshness ─────────────────────────────────────────────────────────

check_data_freshness() {
    local result
    result=$(sudo -u crz "${VENV_BIN}/python" -c "
from app.db.session import get_session_factory
from app.flags.freshness import check_data_freshness
s = get_session_factory()()
r = check_data_freshness(s)
print(r['status'])
s.close()
" 2>/dev/null) || true

    case "${result}" in
        fresh)
            pass "Data freshness: fresh"
            ;;
        no_data)
            warn "Data freshness: no_data (run first ingestion)"
            ;;
        stale)
            warn "Data freshness: stale (no recent ingestion)"
            ;;
        *)
            fail "Data freshness check returned unexpected result: ${result:-<empty>}"
            ;;
    esac
}

# ── 5. Systemd Services ──────────────────────────────────────────────────────

check_systemd_services() {
    local dashboard_active
    dashboard_active=$(systemctl is-active crz-dashboard 2>/dev/null || true)
    if [[ "${dashboard_active}" == "active" ]]; then
        pass "crz-dashboard service is active"
    else
        fail "crz-dashboard service is not active (status: ${dashboard_active:-unknown})"
    fi

    local timer_active
    timer_active=$(systemctl is-active crz-ingestion.timer 2>/dev/null || true)
    if [[ "${timer_active}" == "active" ]]; then
        pass "crz-ingestion.timer is active"
    else
        fail "crz-ingestion.timer is not active (status: ${timer_active:-unknown})"
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────────

main() {
    echo "CRZ Monitor — Smoke Test"
    echo "========================"
    echo ""

    check_docker_postgres
    check_migrations
    check_dashboard
    check_data_freshness
    check_systemd_services

    echo ""
    echo "========================"
    if [[ "${HAS_FAIL}" -eq 1 ]]; then
        echo -e "${RED}Result: FAIL — one or more checks did not pass${NC}"
        exit 1
    elif [[ "${HAS_WARN}" -eq 1 ]]; then
        echo -e "${YELLOW}Result: WARN — no failures but warnings present${NC}"
        exit 2
    else
        echo -e "${GREEN}Result: PASS — all checks passed${NC}"
        exit 0
    fi
}

main "$@"
