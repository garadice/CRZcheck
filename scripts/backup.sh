#!/usr/bin/env bash
# CRZ Monitor Database Backup Script
# Usage: ./scripts/backup.sh
# Creates a compressed pg_dump backup and validates it.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_CONTAINER="${DB_CONTAINER:-crz_db}"
DB_NAME="${DB_NAME:-crz_monitor}"
DB_USER="${DB_USER:-crz}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="${DB_NAME}_${TIMESTAMP}.dump"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    log_error "Container '${DB_CONTAINER}' is not running"
    exit 1
fi

mkdir -p "${BACKUP_DIR}"
log_info "Starting backup: ${FILENAME}"

if command -v pv >/dev/null 2>&1; then
    docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -Fc "${DB_NAME}" | pv > "${FILEPATH}"
else
    docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -Fc "${DB_NAME}" > "${FILEPATH}"
fi

if [ ! -s "${FILEPATH}" ]; then
    log_error "Backup file is empty: ${FILEPATH}"
    rm -f "${FILEPATH}"
    exit 1
fi

log_info "Validating backup..."
if docker exec -i "${DB_CONTAINER}" pg_restore --list < "${FILEPATH}" >/dev/null 2>&1; then
    log_info "Backup validation passed"
else
    FILESIZE=$(stat -c%s "${FILEPATH}" 2>/dev/null || stat -f%z "${FILEPATH}" 2>/dev/null || echo "unknown")
    log_error "Backup validation failed (pg_restore --list returned error)"
    log_error "File: ${FILEPATH} (${FILESIZE} bytes)"
    log_error "Attempting manual validation..."
    if docker exec -i "${DB_CONTAINER}" pg_restore --list < "${FILEPATH}" 2>&1 | tail -5; then
        log_error "Partial validation succeeded but backup may be incomplete"
    fi
    exit 2
fi

FILESIZE=$(stat -c%s "${FILEPATH}" 2>/dev/null || stat -f%z "${FILEPATH}" 2>/dev/null || echo "unknown")
log_info "Backup complete: ${FILEPATH} (${FILESIZE} bytes)"

DELETED_COUNT=$(find "${BACKUP_DIR}" -name "${DB_NAME}_*.dump" -mtime +"${RETENTION_DAYS}" -print -delete 2>/dev/null | wc -l || true)
if [ "${DELETED_COUNT}" -gt 0 ]; then
    log_info "Cleaned up ${DELETED_COUNT} backup(s) older than ${RETENTION_DAYS} days"
fi

exit 0
