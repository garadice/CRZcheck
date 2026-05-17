#!/usr/bin/env bash
# CRZ Monitor Database Restore Script
# Usage: ./scripts/restore.sh [--test|--apply] <dump_file>
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-crz_db}"
DB_NAME="${DB_NAME:-crz_monitor}"
DB_USER="${DB_USER:-crz}"
TEST_DB_NAME="${DB_NAME}_test_verify"

log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

cleanup_test_db() {
    if docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "SELECT 1 FROM pg_database WHERE datname='${TEST_DB_NAME}'" -tA 2>/dev/null | grep -q 1; then
        log_info "Dropping test database: ${TEST_DB_NAME}"
        docker exec "${DB_CONTAINER}" dropdb -U "${DB_USER}" --if-exists "${TEST_DB_NAME}" 2>/dev/null || true
    fi
}

usage() {
    echo "Usage: $0 [--test|--apply] <dump_file>"
    echo ""
    echo "  --test   (default) Validate backup by restoring into a temp database"
    echo "  --apply  Restore backup into production database (destructive)"
    exit 1
}

MODE="--test"
DUMP_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            MODE="--test"
            shift
            ;;
        --apply)
            MODE="--apply"
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            ;;
        *)
            DUMP_FILE="$1"
            shift
            ;;
    esac
done

if [ -z "${DUMP_FILE}" ]; then
    log_error "No dump file specified"
    usage
fi

if [ ! -f "${DUMP_FILE}" ]; then
    log_error "Dump file not found: ${DUMP_FILE}"
    exit 1
fi

if [ ! -r "${DUMP_FILE}" ]; then
    log_error "Dump file not readable: ${DUMP_FILE}"
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    log_error "Container '${DB_CONTAINER}' is not running"
    exit 2
fi

DUMP_BASENAME=$(basename "${DUMP_FILE}")
log_info "Dump file: ${DUMP_BASENAME} ($(stat -c%s "${DUMP_FILE}" 2>/dev/null || stat -f%z "${DUMP_FILE}" 2>/dev/null) bytes)"

if [ "${MODE}" = "--test" ]; then
    log_info "Running in TEST mode (non-destructive)"
    trap cleanup_test_db EXIT

    log_info "Creating test database: ${TEST_DB_NAME}"
    docker exec "${DB_CONTAINER}" dropdb -U "${DB_USER}" --if-exists "${TEST_DB_NAME}" 2>/dev/null || true
    docker exec "${DB_CONTAINER}" createdb -U "${DB_USER}" "${TEST_DB_NAME}"

    log_info "Restoring dump into test database..."
    if ! docker exec -i "${DB_CONTAINER}" pg_restore -U "${DB_USER}" -d "${TEST_DB_NAME}" -c < "${DUMP_FILE}" 2>&1; then
        log_error "Restore to test database failed"
        exit 2
    fi

    log_info "Validating row counts..."
    VALIDATION_FAILED=0

    ROW_COUNTS=$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${TEST_DB_NAME}" -tA -c "
        SELECT 'contracts' AS t, count(*) FROM contracts
        UNION ALL SELECT 'organizations', count(*) FROM organizations
        UNION ALL SELECT 'suppliers', count(*) FROM suppliers
        UNION ALL SELECT 'ingestion_runs', count(*) FROM ingestion_runs;
    " 2>/dev/null)

    if [ -z "${ROW_COUNTS}" ]; then
        log_error "Could not retrieve row counts from test database"
        exit 3
    fi

    while IFS='|' read -r table count; do
        table=$(echo "${table}" | xargs)
        count=$(echo "${count}" | xargs)
        if [ "${count}" -eq 0 ]; then
            log_error "Table '${table}' has 0 rows -- backup may be incomplete"
            VALIDATION_FAILED=1
        else
            log_info "  ${table}: ${count} rows"
        fi
    done <<< "${ROW_COUNTS}"

    cleanup_test_db

    if [ "${VALIDATION_FAILED}" -eq 1 ]; then
        log_error "Validation failed: one or more tables have 0 rows"
        exit 3
    fi

    log_info "Test restore completed successfully"
    exit 0

elif [ "${MODE}" = "--apply" ]; then
    log_info "Running in APPLY mode (DESTRUCTIVE)"
    echo ""
    echo "WARNING: This will REPLACE the production database '${DB_NAME}'."
    echo "All current data will be lost."
    echo ""
    read -r -p "Type 'yes' to confirm: " CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
        log_info "Aborted by user"
        exit 0
    fi

    log_info "Stopping ingestion and dashboard services..."
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl stop crz-ingestion 2>/dev/null && log_info "Stopped crz-ingestion" || log_info "Could not stop crz-ingestion (may not exist)"
        sudo systemctl stop crz-dashboard 2>/dev/null && log_info "Stopped crz-dashboard" || log_info "Could not stop crz-dashboard (may not exist)"
    else
        log_info "systemctl not available -- skipping service stop"
    fi

    log_info "Terminating active connections to '${DB_NAME}'..."
    docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();
    " 2>/dev/null || log_info "No active connections to terminate"

    log_info "Dropping database: ${DB_NAME}"
    docker exec "${DB_CONTAINER}" dropdb -U "${DB_USER}" "${DB_NAME}"

    log_info "Creating database: ${DB_NAME}"
    docker exec "${DB_CONTAINER}" createdb -U "${DB_USER}" "${DB_NAME}"

    log_info "Restoring from dump..."
    if ! docker exec -i "${DB_CONTAINER}" pg_restore -U "${DB_USER}" -d "${DB_NAME}" < "${DUMP_FILE}" 2>&1; then
        log_error "Restore failed"
        exit 2
    fi

    log_info "Running alembic upgrade head..."
    if [ -d "alembic" ] && [ -f "alembic.ini" ]; then
        if command -v .venv/bin/alembic >/dev/null 2>&1; then
            .venv/bin/alembic upgrade head
        elif command -v alembic >/dev/null 2>&1; then
            alembic upgrade head
        else
            log_info "alembic not found -- skipping migration"
        fi
    else
        log_info "No alembic configuration found -- skipping migration"
    fi

    log_info "Restore completed successfully"
    log_info "Start services manually: sudo systemctl start crz-dashboard crz-ingestion"
    exit 0
fi
