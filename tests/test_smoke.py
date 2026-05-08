"""Phase 1 smoke tests: app boots, auth + PWA shell are wired."""

from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from app.extensions import db
from app.models import User


def test_healthz(client: FlaskClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"


def test_root_redirects_anonymous_to_login(client: FlaskClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_manifest_served(client: FlaskClient) -> None:
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.mimetype == "application/manifest+json"
    assert b"Finance Hub" in resp.data


def test_service_worker_served(client: FlaskClient) -> None:
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert resp.mimetype == "application/javascript"
    assert resp.headers.get("Service-Worker-Allowed") == "/"


def test_register_login_logout_flow(app: Flask, client: FlaskClient) -> None:
    register = client.post(
        "/auth/register",
        data={
            "display_name": "Pat",
            "email": "pat@example.com",
            "password": "supersecret1",
            "confirm": "supersecret1",
        },
        follow_redirects=False,
    )
    assert register.status_code == 302

    with app.app_context():
        user = db.session.query(User).filter_by(email="pat@example.com").one()
        assert user.check_password("supersecret1")
        assert not user.password_hash.startswith("supersecret")

    logout = client.post("/auth/logout", follow_redirects=False)
    assert logout.status_code == 302

    bad = client.post(
        "/auth/login",
        data={"email": "pat@example.com", "password": "wrong"},
        follow_redirects=True,
    )
    assert b"incorrect" in bad.data.lower()

    good = client.post(
        "/auth/login",
        data={"email": "pat@example.com", "password": "supersecret1"},
        follow_redirects=False,
    )
    assert good.status_code == 302

    home = client.get("/")
    assert home.status_code == 200
    assert b"Welcome" in home.data


def test_password_too_short_rejected(client: FlaskClient) -> None:
    resp = client.post(
        "/auth/register",
        data={
            "display_name": "Short",
            "email": "short@example.com",
            "password": "short",
            "confirm": "short",
        },
    )
    assert resp.status_code == 200
    assert b"at least 8" in resp.data


def test_login_next_param_rejects_external_redirect(app: Flask, client: FlaskClient) -> None:
    with app.app_context():
        user = User(email="redir@example.com", display_name="R")
        user.set_password("supersecret1")
        db.session.add(user)
        db.session.commit()

    resp = client.post(
        "/auth/login?next=https://evil.example.com/x",
        data={"email": "redir@example.com", "password": "supersecret1"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]
