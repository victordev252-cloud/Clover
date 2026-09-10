# Clover Video Splitter + Ameno Store Web Verification

Clover is a production-oriented Telegram video splitter written for Python 3.11+ and Pyrogram 2.x. It downloads media to isolated per-job directories, validates streams with FFprobe, processes one part at a time with FFmpeg, uploads each part, and removes temporary output.

The repository also includes `webapp.py`, a polished Flask email-verification web app for Ameno Store. The web app is intentionally separate from the Telegram bot so either service can run independently.

## Email setup

Copy `.env.example` to `.env`. Keep the real credentials only in `.env` and never commit that file. For Gmail, enable 2-Step Verification, create a Google App Password, and put the 16-character value in `MAIL_APP_PASSWORD`. The sender defaults to `victordev252@gmail.com`; change `MAIL_USERNAME` only if needed.

Run the web app with:

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python webapp.py
```

Open `http://127.0.0.1:5000`. The app provides email validation, secure random six-digit codes, hashed code storage, expiry, attempt limits, secure sessions, resend-by-signup flow, a professional HTML email, and `/health` for monitoring. SMTP failures are shown as a safe user-facing message and detailed credentials are never displayed.

Run the Telegram bot separately with `venv/bin/python bot.py`. Docker and systemd instructions for the bot remain available in the existing files.

## Tests

Run `pytest -q`. Tests do not require Telegram or SMTP credentials.
