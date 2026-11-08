#!/usr/bin/env bash
set -e

echo "=========================================="
echo "  Deploying Sponsor Finder on VPS Host"
echo "=========================================="

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# 1. Setup virtualenv if not present
if [ ! -d ".venv" ]; then
    echo "[+] Creating Python 3 virtual environment..."
    python3 -m venv .venv
fi

# 2. Upgrade pip and install dependencies
echo "[+] Installing application dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 3. Create required data and logs directories
mkdir -p data/proposals logs

# 4. Initialize Database & Seed Catalog
echo "[+] Initializing Database & Seed Sponsors..."
.venv/bin/python -c "
import asyncio
from app.database.db import init_db
asyncio.run(init_db())
print('Database initialized and seeded.')
"

# 5. Install systemd service if running as root / with sudo
if [ "$(id -u)" -eq 0 ]; then
    echo "[+] Installing systemd service..."
    cp sponsor-finder.service /etc/systemd/system/sponsor-finder.service
    systemctl daemon-reload
    systemctl enable sponsor-finder.service
    systemctl restart sponsor-finder.service
    echo "[+] Sponsor Finder service started successfully!"
    systemctl status sponsor-finder.service --no-pager
else
    echo "[!] Not running as root. You can run the application directly with:"
    echo "    .venv/bin/python main.py all"
fi

echo "=========================================="
echo "  Deployment Completed!"
echo "=========================================="
