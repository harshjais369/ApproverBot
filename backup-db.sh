#!/bin/bash
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

# Create a backup of the DB inside the container
docker exec approverbot-bot-1 python -c "import sqlite3; \
    src=sqlite3.connect('/app/data/approverbot.db'); \
    dst=sqlite3.connect('/tmp/approverbot-backup.db'); \
    src.backup(dst); dst.close(); src.close(); print('backup done')"

# Copy DB backup from the running container to host
docker cp approverbot-bot-1:/tmp/approverbot-backup.db "$BACKUP_DIR/approverbot_$(date +%Y%m%d_%H%M%S).db"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete

echo "DB backup done: $(ls -t $BACKUP_DIR | head -1)"
