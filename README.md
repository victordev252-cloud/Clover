# 🍀 Clover Video Splitter

Clover is a production-oriented Telegram video splitter written for Python 3.11+ and Pyrogram 2.x. It downloads media to an isolated per-job directory, validates the actual stream with FFprobe, processes one part at a time with FFmpeg, uploads each part, and removes temporary output immediately.

## Important correction

A Telegram bot cannot pass an ordinary uploaded file directly to local FFmpeg without obtaining the media first. Clover therefore uses controlled disk-backed downloads and never loads the entire video into RAM. SQLite stores metadata only; video bytes remain in `data/jobs/<user>/<job>/` and are removed in `finally` cleanup.

## Setup

On Ubuntu/Debian, install `python3 python3-venv python3-pip ffmpeg`, copy `.env.example` to `.env`, configure `API_ID`, `API_HASH`, `BOT_TOKEN`, and `ADMIN_IDS`, then run `./install.sh`. Start with `venv/bin/python bot.py`. On Termux, use `pkg update && pkg install python ffmpeg`, clone the project, run `python -m venv venv`, `pip install -r requirements.txt`, configure `.env`, and run `python bot.py`; root is not required.

Docker users can run `docker compose up -d --build`. The `.env` file is never copied into the image. For systemd, install under `/opt/clover`, set ownership to a dedicated service account, and use the included service file.

## Controls and safety

Clover enforces per-user active-job limits, a bounded worker queue, configurable file limits, FFprobe validation, safe argument-array subprocess execution (no shell), path-safe names, WAL SQLite, rotating logs, and cleanup after success, cancellation, FFmpeg failure, upload failure, or unexpected exceptions. Fast mode uses stream copy and may cut on keyframes; compatible mode is available in the media service for exact re-encoding workflows.

The current default intake path uses two equal parts so the bot is immediately usable. The service utilities already support arbitrary equal-part and fixed-duration ranges; a next UI iteration can expose those choices as callback-driven settings without changing the processing core.

## Tests

Run `pytest -q`. Tests are intentionally independent of Telegram credentials and FFmpeg media files.
