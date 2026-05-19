#!/usr/bin/env bash
# CRZ Monitor — Freshness check script
# Run from cron to detect when ingestion stops working.
#
# Example cron entry (every 30 minutes):
#   */30 * * * * cd /opt/crz-monitor && ./scripts/check-freshness.sh || logger -t crz-freshness "ALERT: data stale"
set -euo pipefail

cd "$(dirname "$0")/.."
exec .venv/bin/python -m app.alerts.freshness_alert
