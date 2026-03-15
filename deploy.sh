#!/bin/bash
# deploy.sh — First-time setup AND updates for ApproverBot on Docker
# Usage:
#   First time:  ./deploy.sh init yourdomain.com admin@yourdomain.com
#   Update only: ./deploy.sh update

set -e

DOMAIN="${2:-}"
EMAIL="${3:-}"
NGINX_CONF="./nginx/nginx.conf"
NGINX_INIT_CONF="./nginx/nginx-init.conf"

# ── helper ──────────────────────────────────────────────────────────────────
confirm() {
    read -r -p "$1 [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

# ── update (rebuild + restart) ───────────────────────────────────────────────
if [[ "$1" == "update" ]]; then
    echo ">>> Pulling latest code..."
    git pull
    echo ">>> Rebuilding and restarting bot..."
    docker compose build --no-cache bot
    docker compose up -d bot
    echo "Done. Logs: docker compose logs -f bot"
    exit 0
fi

# ── init (first-time full setup) ─────────────────────────────────────────────
if [[ "$1" != "init" ]] || [[ -z "$DOMAIN" ]] || [[ -z "$EMAIL" ]]; then
    echo "Usage:"
    echo "  First-time setup: ./deploy.sh init <domain> <email>"
    echo "  Update:           ./deploy.sh update"
    exit 1
fi

echo ">>> Replacing YOUR_DOMAIN placeholder in nginx configs..."
sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" "$NGINX_CONF" "$NGINX_INIT_CONF"

echo ">>> Copying init nginx config (HTTP only)..."
cp "$NGINX_CONF" "${NGINX_CONF}.bak"
cp "$NGINX_INIT_CONF" "$NGINX_CONF"

echo ">>> Starting nginx for ACME challenge..."
docker compose up -d nginx

echo ">>> Waiting for nginx to be ready..."
sleep 3

echo ">>> Obtaining SSL certificate from Let's Encrypt..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo ">>> Restoring production nginx config (HTTPS)..."
cp "${NGINX_CONF}.bak" "$NGINX_CONF"
rm -f "${NGINX_CONF}.bak"

echo ">>> Starting all services..."
docker compose up -d

echo ""
echo "Done! Services running:"
docker compose ps
echo ""
echo "Useful commands:"
echo "  View logs:    docker compose logs -f bot"
echo "  Stop all:     docker compose down"
echo "  Update bot:   ./deploy.sh update"
