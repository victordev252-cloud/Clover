#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'Python 3 is required'; exit 1; }
command -v ffmpeg >/dev/null || { echo 'FFmpeg is required (Ubuntu: sudo apt install ffmpeg; Termux: pkg install ffmpeg)'; exit 1; }
command -v ffprobe >/dev/null || { echo 'FFprobe is required'; exit 1; }
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
mkdir -p data/jobs data/temp logs
if [[ ! -f .env ]]; then cp .env.example .env; echo 'Created .env; edit BOT_TOKEN, API_ID, API_HASH, and ADMIN_IDS before starting.'; fi
./venv/bin/python - <<'PY'
from config import Settings
from database.db import Database
import asyncio
cfg=Settings.from_env() if __import__('os').environ.get('BOT_TOKEN') else None
if cfg: cfg.prepare(); asyncio.run(Database(cfg.database_path).init())
PY
echo 'Clover installed. Configure .env, then run: ./venv/bin/python bot.py'
