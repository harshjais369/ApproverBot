#!/bin/bash
# restore-db.sh — Restore SQLite DB from a backup file into the Docker container
# Usage: ./restore-db.sh [path/to/backup.db]

set -e

BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" ]]; then
    # Find latest backup in backups/ dir
    BACKUP_FILE=$(ls -t backups/*.db 2>/dev/null | head -n 1)
fi

if [[ -z "$BACKUP_FILE" ]] || [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Usage: ./restore-db.sh <path_to_backup.db>"
    echo "Error: No .db backup file specified or found."
    exit 1
fi

echo ">>> Restoring DB from: $BACKUP_FILE"

echo ">>> Stopping bot container..."
docker compose stop bot 2>/dev/null || true

echo ">>> Removing stale WAL/SHM journal files..."
docker compose run --rm --user root bot rm -f /app/data/approverbot.db-wal /app/data/approverbot.db-shm /app/data/approverbot.db-journal

echo ">>> Copying $BACKUP_FILE into bot container..."
docker cp "$BACKUP_FILE" approverbot-bot-1:/app/data/approverbot.db

echo ">>> Removing any copied WAL/SHM files and fixing permissions..."
docker compose run --rm --user root bot sh -c "rm -f /app/data/approverbot.db-wal /app/data/approverbot.db-shm /app/data/approverbot.db-journal && chown -R botuser:botgroup /app/data"

echo ">>> Starting bot container..."
docker compose start bot

echo ""
echo "Done! Database restored successfully."
echo "Check logs: docker compose logs -f bot"
