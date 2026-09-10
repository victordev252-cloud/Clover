import os

os.environ["WEB_DATABASE_PATH"] = "/tmp/clover-test-webapp.db"
os.environ["WEB_SECRET_KEY"] = "test-secret"

from webapp import app, db, hash_code


def setup_function():
    try:
        os.remove("/tmp/clover-test-webapp.db")
    except FileNotFoundError:
        pass


def test_health():
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_signup_requires_email_configuration(monkeypatch):
    monkeypatch.setattr("webapp.send_verification_email", lambda recipient, code: (_ for _ in ()).throw(RuntimeError("missing")))
    response = app.test_client().post("/signup", data={"email": "person@example.com"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Email could not be sent" in response.data


def test_verify_success(monkeypatch):
    monkeypatch.setattr("webapp.send_verification_email", lambda recipient, code: None)
    client = app.test_client()
    client.post("/signup", data={"email": "person@example.com"})
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE email=?", ("person@example.com",)).fetchone()
    # Test the same stored hash mechanism without exposing code in the app UI.
    with db() as connection:
        connection.execute("UPDATE users SET code_hash=? WHERE email=?", (hash_code("123456"), "person@example.com"))
    response = client.post("/verify", data={"code": "123456"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data
