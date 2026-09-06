#!/bin/bash
# Notara — OVH VPS deployment script
# Run as root on a fresh Ubuntu 22.04 VPS:
#   bash deploy.sh
set -e

DOMAIN="notara.io"
REPO="https://github.com/joaofmsilva1979/notara.git"
APP_DIR="/opt/notara"
APP_USER="notara"
EMAIL="davisthe8th@gmail.com"

echo ""
echo "  Notara — VPS deployment"
echo "  Domain: $DOMAIN"
echo ""

# ── System packages ───────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt update -y -q
apt install -y -q python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git ffmpeg

# ── App user ─────────────────────────────────────────────────
echo "[2/6] Creating app user..."
useradd -m -s /bin/bash "$APP_USER" 2>/dev/null || true

# ── Clone / update repo ───────────────────────────────────────
echo "[3/6] Fetching code from GitHub..."
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO" "$APP_DIR"
fi
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

# ── Python environment ────────────────────────────────────────
echo "[4/6] Installing Python packages (this takes a few minutes)..."
sudo -u "$APP_USER" python3.11 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/api/requirements.txt" -q

# ── systemd service ───────────────────────────────────────────
echo "[5/6] Setting up systemd service..."
cat > /etc/systemd/system/notara.service << EOF
[Unit]
Description=Notara
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable notara
systemctl restart notara

# ── nginx ─────────────────────────────────────────────────────
echo "[6/6] Configuring nginx + SSL..."
cat > /etc/nginx/sites-available/notara << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 160M;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/notara /etc/nginx/sites-enabled/notara
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL" --redirect

echo ""
echo "  ✓ Notara is live at https://$DOMAIN"
echo "  To update after a git push: bash /opt/notara/update.sh"
echo ""
