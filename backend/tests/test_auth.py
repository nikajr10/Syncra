"""Task 5.1: users, login with bearer tokens, accounts linked by an admin."""

import hashlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.auth import add_user, hash_password, link_account, verify_password
from app.api.main import app
from app.db.schema import AuthToken, UserSourceIdentity

PUBLIC = {"/health", "/auth/login"}
client = TestClient(app)


def _login(username: str = "alice", password: str = "correct horse") -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_passwords_are_salted_scrypt_hashes() -> None:
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first.startswith("scrypt$16384$8$5$") and first != second  # salted
    assert "correct horse" not in first
    assert verify_password("correct horse", first) and verify_password("correct horse", second)
    assert not verify_password("correct horsE", first)
    assert not verify_password("correct horse", None)  # no password set: never matches


def test_login_me_and_logout(db_session: Session) -> None:
    add_user(db_session, " Alice ", "correct horse", "Alice Chen")
    link_account(db_session, "alice", "slack", "U01", "Alice Chen")
    link_account(db_session, "alice", "github", "alice-gh")

    wrong = client.post("/auth/login", json={"username": "alice", "password": "wrong horse"})
    nobody = client.post("/auth/login", json={"username": "bob", "password": "correct horse"})
    assert wrong.status_code == nobody.status_code == 401
    assert wrong.json() == nobody.json() == {"detail": "Wrong username or password"}

    headers = _login("ALICE")  # usernames are case-insensitive
    assert client.get("/me", headers=headers).json() == {
        "username": "alice",
        "display_name": "Alice Chen",
        "accounts": [
            {"tool": "slack", "id": "U01", "display_name": "Alice Chen"},
            {"tool": "github", "id": "alice-gh", "display_name": None},
        ],
    }
    token = headers["Authorization"].removeprefix("Bearer ")
    assert db_session.scalars(select(AuthToken.token_hash)).all() == [
        hashlib.sha256(token.encode()).hexdigest()  # only the hash is stored
    ]

    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).status_code == 401
    assert db_session.scalars(select(AuthToken)).all() == []


def test_expired_tokens_stop_working_and_are_tidied_up(db_session: Session) -> None:
    add_user(db_session, "alice", "correct horse")
    old = _login()
    db_session.execute(update(AuthToken).values(expires_at="2000-01-01T00:00:00Z"))
    db_session.commit()
    assert client.get("/me", headers=old).status_code == 401

    assert client.get("/me", headers=_login()).status_code == 200
    assert len(db_session.scalars(select(AuthToken)).all()) == 1  # the expired one was deleted


def test_protected_endpoints_reject_requests_without_a_valid_token(db_session: Session) -> None:
    add_user(db_session, "alice", "correct horse")
    _login()  # a valid token exists, just not in these requests
    endpoints = [
        (method, path)
        for path, operations in app.openapi()["paths"].items()  # every endpoint, routers included
        for method in operations
        if path not in PUBLIC
    ]
    assert endpoints
    for method, path in endpoints:
        url = re.sub(r"\{[^}]+\}", "1", path)
        for headers in ({}, {"Authorization": "Bearer not-a-token"}, {"Authorization": "x"}):
            response = client.request(method, url, headers=headers)
            assert response.status_code == 401, (method, path, headers)
            assert response.headers["www-authenticate"] == "Bearer"


def test_add_user_checks_its_input(db_session: Session) -> None:
    add_user(db_session, "alice", "correct horse")
    with pytest.raises(ValueError, match="already exists"):
        add_user(db_session, "Alice", "another horse")
    with pytest.raises(ValueError, match="at least 8"):
        add_user(db_session, "bob", "short")
    with pytest.raises(ValueError, match="username"):
        add_user(db_session, "bob smith", "correct horse")


def test_link_account_checks_its_input(db_session: Session) -> None:
    add_user(db_session, "alice", "correct horse")
    add_user(db_session, "bob", "correct horse")
    link_account(db_session, "alice", "slack", "U01")
    with pytest.raises(ValueError, match="No user"):
        link_account(db_session, "carol", "slack", "U02")
    with pytest.raises(ValueError, match="one of"):
        link_account(db_session, "alice", "gitlab", "alice")
    for tool, bad in [("slack", "slack:U01"), ("slack", "B0BOT"), ("github", "a b"), ("jira", "")]:
        with pytest.raises(ValueError, match="account id"):
            link_account(db_session, "alice", tool, bad)
    with pytest.raises(ValueError, match="another user"):  # nobody can take over an account
        link_account(db_session, "bob", "slack", "U01")

    link_account(db_session, "alice", "slack", "U01", "Alice Chen")  # again: renamed, not added
    [account] = db_session.scalars(select(UserSourceIdentity)).all()
    assert (account.external_id, account.display_name) == ("U01", "Alice Chen")
