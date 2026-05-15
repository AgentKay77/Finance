#!/usr/bin/env bash
# Safe SQLite backup using the `.backup` command (WAL-aware, no torn writes).
#
# Usage:
#   ./scripts/backup_db.sh [destination-dir]
#
# Reads BACKUP_DEST from the environment (default: ./backups). After the local
# snapshot is written, optionally rsyncs it to BACKUP_RSYNC_TARGET if set.
#
# Wire to cron, e.g. crontab -e:
#   0 3 * * * /home/pi/finance-hub/scripts/backup_db.sh >> /var/log/finance-backup.log 2>&1

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${DB_PATH:-${ROOT_DIR}/instance/finance_hub.db}"
DEST_DIR="${1:-${BACKUP_DEST:-${ROOT_DIR}/backups}}"
RSYNC_TARGET="${BACKUP_RSYNC_TARGET:-}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Database not found at ${DB_PATH}" >&2
  exit 1
fi

mkdir -p "${DEST_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${DEST_DIR}/finance_hub_${TIMESTAMP}.db"

# `.backup` handles WAL safely, unlike a raw `cp`.
sqlite3 "${DB_PATH}" ".backup '${OUT_FILE}'"
gzip --force "${OUT_FILE}"

echo "Wrote ${OUT_FILE}.gz"

if [[ -n "${RSYNC_TARGET}" ]]; then
  rsync -av --remove-source-files "${OUT_FILE}.gz" "${RSYNC_TARGET}/"
  echo "Synced to ${RSYNC_TARGET}"
fi

# Retain the most recent 30 daily snapshots locally.
find "${DEST_DIR}" -name 'finance_hub_*.db.gz' -mtime +30 -delete || true
