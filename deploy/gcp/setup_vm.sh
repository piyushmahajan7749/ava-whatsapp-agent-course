#!/usr/bin/env bash
# Runs ON the GCP e2-micro VM (Debian). Idempotent — safe to re-run.
# Sets up: uv + Python 3.12, a slim venv (no torch), the app under systemd
# (always-on so the scheduler fires), and Caddy for automatic HTTPS at
# <external-IP>.sslip.io. Expects the app code at /opt/angc and secrets in
# /opt/angc/app.env (scp'd before running this).
set -euo pipefail

APP_DIR=/opt/angc
ENV_FILE=$APP_DIR/app.env
RUN_USER=$(whoami)

command -v curl >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq curl; }
sudo apt-get install -y -qq ca-certificates debian-keyring debian-archive-keyring apt-transport-https gnupg

echo "== uv + Python 3.12 + slim venv =="
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"
uv python install 3.12
[ -d .venv ] || uv venv --python 3.12 .venv
# Always (re)install to the pinned versions — idempotent, and picks up updates.
uv pip install --python .venv/bin/python -r deploy/gcp/requirements-runtime.txt

echo "== public hostname (<IP>.sslip.io) =="
IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
HOST="${IP//./-}.sslip.io"
echo "  -> $HOST"

echo "== operational env vars (append if missing) =="
mkdir -p "$APP_DIR/data"
set_kv() { grep -q "^$1=" "$ENV_FILE" 2>/dev/null || echo "$1=$2" | sudo tee -a "$ENV_FILE" >/dev/null; }
touch_env() { sudo touch "$ENV_FILE"; sudo chown "$RUN_USER" "$ENV_FILE"; sudo chmod 600 "$ENV_FILE"; }
touch_env
set_kv LLM_PROVIDER groq
set_kv TEXT_MODEL_NAME llama-3.3-70b-versatile
set_kv SMALL_TEXT_MODEL_NAME llama-3.1-8b-instant
set_kv ANGC_ADMIN_EMAIL director@angcgroup.com
set_kv ANGC_SCHEDULER_ENABLED true
set_kv ANGC_DB_PATH "$APP_DIR/data/angc_tasks.db"
set_kv ANGC_SQLITE_WAL true
# Dashboard URL is derived from the VM IP; replace any old value.
sudo sed -i '/^ANGC_DASHBOARD_URL=/d' "$ENV_FILE"
echo "ANGC_DASHBOARD_URL=https://$HOST" | sudo tee -a "$ENV_FILE" >/dev/null

echo "== systemd service (always-on) =="
sudo tee /etc/systemd/system/angc.service >/dev/null <<UNIT
[Unit]
Description=ANGC WhatsApp Executive Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONPATH=$APP_DIR/src
ExecStart=$APP_DIR/.venv/bin/uvicorn ai_companion.interfaces.whatsapp.webhook_endpoint:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5
User=$RUN_USER

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable angc
sudo systemctl restart angc

echo "== Caddy (automatic HTTPS) =="
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -qq && sudo apt-get install -y -qq caddy
fi
sudo tee /etc/caddy/Caddyfile >/dev/null <<CADDY
$HOST {
    reverse_proxy 127.0.0.1:8080
}
CADDY
sudo systemctl restart caddy

sleep 3
echo
echo "==================================================================="
echo " App URL:      https://$HOST"
echo " Webhook URL:  https://$HOST/whatsapp_response"
echo " Dashboard:    https://$HOST/login"
echo "==================================================================="
sudo systemctl --no-pager status angc | head -6 || true
