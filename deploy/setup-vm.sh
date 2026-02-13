#!/bin/bash
# MasterSales VM Setup Script
# Run on a fresh Ubuntu 22.04+ server
# Usage: curl -sSL <raw-url> | bash

set -e

echo "=================================="
echo "  MasterSales VM Setup"
echo "=================================="

# --- System packages ---
echo "[1/6] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpangocairo-1.0-0 libgtk-3-0 libxshmfence1 \
    nginx certbot python3-certbot-nginx
# libasound2 was renamed in Ubuntu 24.04+
sudo apt-get install -y libasound2 2>/dev/null || sudo apt-get install -y libasound2t64

# --- Clone project ---
echo "[2/6] Cloning MasterSales..."
cd /opt
if [ -d "mastersales" ]; then
    cd mastersales && git pull
else
    sudo git clone https://github.com/Evan-Kun/mastersales.git
    sudo chown -R $USER:$USER mastersales
    cd mastersales
fi

# --- Python environment ---
echo "[3/6] Setting up Python environment..."
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- Playwright browser ---
echo "[4/6] Installing Playwright Chromium..."
playwright install chromium

# --- Environment config ---
echo "[5/6] Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ⚠ Edit /opt/mastersales/.env to configure settings"
    echo "  LinkedIn credentials can also be set via the web UI"
fi

# --- Systemd service ---
echo "[6/6] Setting up systemd service..."
sudo tee /etc/systemd/system/mastersales.service > /dev/null <<'UNIT'
[Unit]
Description=MasterSales Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mastersales
Environment=PATH=/opt/mastersales/venv/bin:/usr/bin:/bin
ExecStart=/opt/mastersales/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8899
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable mastersales
sudo systemctl start mastersales

# --- Nginx reverse proxy ---
echo "Setting up Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/mastersales > /dev/null <<'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8899;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/mastersales /etc/nginx/sites-enabled/mastersales
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=================================="
echo "  Setup Complete!"
echo "=================================="
echo ""
echo "  App running at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status mastersales    # Check status"
echo "    sudo journalctl -u mastersales -f    # View logs"
echo "    sudo systemctl restart mastersales   # Restart app"
echo ""
echo "  To update:"
echo "    cd /opt/mastersales && git pull && sudo systemctl restart mastersales"
echo ""
echo "  To add HTTPS (if you have a domain):"
echo "    sudo certbot --nginx -d yourdomain.com"
echo ""
