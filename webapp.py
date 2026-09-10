from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template_string, request, session, url_for

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("WEB_DATABASE_PATH", str(BASE_DIR / "data" / "webapp.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("WEB_SECRET_KEY", secrets.token_hex(32)),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("WEB_COOKIE_SECURE", "0") == "1",
)

SENDER_EMAIL = os.getenv("MAIL_USERNAME", "victordev252@gmail.com").strip()
SENDER_PASSWORD = os.getenv("MAIL_APP_PASSWORD", "").replace(" ", "").strip()
SMTP_HOST = os.getenv("MAIL_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("MAIL_PORT", "587"))
CODE_MINUTES = int(os.getenv("VERIFICATION_MINUTES", "15"))
MAX_ATTEMPTS = int(os.getenv("MAX_VERIFICATION_ATTEMPTS", "5"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def now() -> datetime:
    return datetime.now(timezone.utc)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def valid_email(email: str) -> bool:
    return len(email) <= 254 and email.count("@") == 1 and "." in email.rsplit("@", 1)[1]


def send_verification_email(recipient: str, code: str) -> None:
    if not SENDER_PASSWORD:
        raise RuntimeError("MAIL_APP_PASSWORD is not configured")

    message = EmailMessage()
    message["Subject"] = "Your Ameno Store verification code"
    message["From"] = SENDER_EMAIL
    message["To"] = recipient
    message.set_content(
        f"Your Ameno Store verification code is {code}. It expires in {CODE_MINUTES} minutes."
    )
    message.add_alternative(
        f"""<!doctype html><html><body style='margin:0;background:#050816;color:#e5e7eb;font-family:Arial,sans-serif'>
        <div style='max-width:560px;margin:32px auto;padding:36px;background:#111827;border:1px solid #26324a;border-radius:20px'>
          <div style='color:#a78bfa;font-size:22px;font-weight:700;margin-bottom:28px'>Ameno Store</div>
          <h1 style='font-size:26px;margin:0 0 14px;color:#fff'>Verify your email</h1>
          <p style='color:#aab4c5;line-height:1.6'>Use this one-time code to finish creating your account:</p>
          <div style='margin:28px 0;padding:22px;text-align:center;background:#070b16;border:1px solid #34415d;border-radius:14px'>
            <span style='font:700 36px monospace;letter-spacing:8px;color:#fff'>{code}</span>
          </div>
          <p style='color:#8893a7;font-size:13px;line-height:1.6'>This code expires in {CODE_MINUTES} minutes. If you did not request it, you can safely ignore this email.</p>
        </div></body></html>""",
        subtype="html",
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(message)


BASE = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{{ title }}</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at top,#172554,#050816 55%);font-family:Inter,ui-sans-serif,system-ui;color:#f8fafc;padding:24px}.card{width:min(100%,460px);padding:36px;background:rgba(15,23,42,.92);border:1px solid #26324a;border-radius:24px;box-shadow:0 24px 70px #0008}.brand{font-size:22px;font-weight:800;color:#a78bfa;margin-bottom:28px}.eyebrow{color:#94a3b8;font-size:13px;text-transform:uppercase;letter-spacing:.12em}h1{margin:8px 0 12px;font-size:30px}p{color:#aab4c5;line-height:1.6}label{display:block;color:#dbe4f0;font-size:14px;font-weight:600;margin:22px 0 8px}input{width:100%;padding:14px 16px;background:#070b16;border:1px solid #334155;border-radius:12px;color:white;font-size:16px;outline:none}input:focus{border-color:#8b5cf6;box-shadow:0 0 0 3px #8b5cf633}button,.button{display:block;width:100%;margin-top:22px;padding:14px;border:0;border-radius:12px;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;font-weight:700;font-size:15px;text-align:center;text-decoration:none;cursor:pointer}.muted{font-size:13px;color:#718096;text-align:center;margin-top:20px}.alert{padding:12px 14px;border-radius:12px;margin:16px 0;font-size:14px;background:#3f172a;color:#fecdd3;border:1px solid #881337}.alert.ok{background:#052e2b;color:#a7f3d0;border-color:#0f766e}.code{text-align:center;letter-spacing:10px;font-size:32px;font-family:monospace}.success{text-align:center;font-size:52px;color:#34d399}.actions{display:flex;gap:10px;margin-top:22px}.actions .button{margin:0}.secondary{background:#1e293b}
</style></head><body><main class='card'><div class='brand'>Ameno Store</div>{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class='alert {{ "ok" if category == "success" else "" }}'>{{ message }}</div>{% endfor %}{% endwith %}{{ content|safe }}</main></body></html>"""


def page(content: str, title: str = "Ameno Store"):
    return render_template_string(BASE, content=content, title=title)


@app.get("/")
def index():
    if session.get("verified_email"):
        return page(f"<div class='success'>✓</div><div class='eyebrow'>Account verified</div><h1>Welcome back</h1><p>Your email <strong>{session['verified_email']}</strong> has been verified successfully.</p><a class='button' href='{url_for('logout')}'>Sign out</a>", "Welcome")
    return redirect(url_for("signup"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not valid_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("signup"))
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = now() + timedelta(minutes=CODE_MINUTES)
        try:
            send_verification_email(email, code)
        except (OSError, smtplib.SMTPException, RuntimeError) as exc:
            app.logger.error("Unable to send verification email: %s", exc)
            flash("Email could not be sent. Check MAIL_APP_PASSWORD in your .env file.", "error")
            return redirect(url_for("signup"))
        with db() as connection:
            connection.execute("INSERT OR REPLACE INTO users(email,code_hash,expires_at,attempts,verified,created_at) VALUES(?,?,?,?,?,?)", (email, hash_code(code), expires.isoformat(), 0, 0, now().isoformat()))
        session["pending_email"] = email
        flash("Verification code sent. Check your inbox.", "success")
        return redirect(url_for("verify"))
    return page("<div class='eyebrow'>Secure sign up</div><h1>Create your account</h1><p>Enter your email and we will send you a one-time verification code.</p><form method='post'><label for='email'>Email address</label><input id='email' name='email' type='email' autocomplete='email' placeholder='you@example.com' required><button type='submit'>Send verification code</button></form>", "Sign up")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("signup"))
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        return redirect(url_for("signup"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        expired = now() > datetime.fromisoformat(user["expires_at"])
        if expired:
            flash("This code has expired. Request a new one.", "error")
        elif user["attempts"] >= MAX_ATTEMPTS:
            flash("Too many attempts. Request a new code.", "error")
        else:
            with db() as connection:
                connection.execute("UPDATE users SET attempts=attempts+1 WHERE email=?", (email,))
            if hmac.compare_digest(hash_code(code), user["code_hash"]):
                with db() as connection:
                    connection.execute("UPDATE users SET verified=1 WHERE email=?", (email,))
                session.pop("pending_email", None)
                session["verified_email"] = email
                return redirect(url_for("index"))
            flash("That code is not correct.", "error")
    content = f"<div class='eyebrow'>Step 2 of 2</div><h1>Check your email</h1><p>We sent a 6-digit code to <strong>{email}</strong>.</p><form method='post'><label for='code'>Verification code</label><input class='code' id='code' name='code' inputmode='numeric' pattern='[0-9]{{6}}' maxlength='6' autocomplete='one-time-code' required><button type='submit'>Verify email</button></form><p class='muted'>Code expires in {CODE_MINUTES} minutes.</p><div class='actions'><a class='button secondary' href='{url_for('signup')}'>Use another email</a></div>"
    return page(content, "Verify email")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("signup"))


@app.get("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("WEB_PORT", "5000")), debug=os.getenv("WEB_DEBUG", "0") == "1")
