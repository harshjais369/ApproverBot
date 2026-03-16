#!/bin/bash
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

# Copy DB from the running container
docker compose -f ~/ApproverBot/docker-compose.yml \
    exec -T bot cp /app/data/approverbot.db /tmp/backup.db

docker compose -f ~/ApproverBot/docker-compose.yml \
    cp bot:/tmp/backup.db "$BACKUP_DIR/approverbot_$(date +%Y%m%d_%H%M%S).db"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete

echo "DB backup done: $(ls -t $BACKUP_DIR | head -1)"
