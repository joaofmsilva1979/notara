#!/bin/bash
# Run on the OVH VPS after pushing changes to GitHub:
#   bash /opt/notara/update.sh
set -e

APP_DIR="/opt/notara"
APP_USER="notara"

echo "Pulling latest code..."
git -C "$APP_DIR" pull

echo "Updating Python packages..."
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/api/requirements.txt" -q

echo "Restarting Notara..."
systemctl restart notara

echo "Done. Notara is updated."
