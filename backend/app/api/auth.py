"""Users and login (Task 5.1): local accounts, bearer tokens, and the accounts each user has.

Passwords are hashed with scrypt (Python's hashlib). POST /auth/login hands out a random bearer
token that expires after TOKEN_TTL_HOURS; only its SHA-256 is stored (`auth_tokens`), so a copy
of the database holds no usable logins, and logging out deletes it. Protected endpoints take a
`CurrentUser` argument: no valid token, no request.

Admins create users and link their GitHub / Jira / Slack accounts with `make add-user` and
`make link-account` (scripts/users.py). Users can't link accounts themselves: from Phase 6 their
linked accounts decide what they may search, so a self-claimed account would leak a colleague's
channels. Every learning run merges a user's accounts into one person (`link_identities`).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.engine import get_db
from app.db.schema import AuthToken, User, UserSourceIdentity

router = APIRouter()
bearer = HTTPBearer()  # no `Authorization: Bearer …` header -> 401

USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")
ACCOUNT_ID = {  # what follows "github:" / "jira:" / "slack:" in the authors the connectors store
    "github": re.compile(r"[A-Za-z0-9-]{1,39}"),  # login
    "jira": re.compile(r"[A-Za-z0-9:_.-]{1,128}"),  # accountId
    "slack": re.compile(r"[UW][A-Z0-9]{2,30}"),  # user id
}
MIN_PASSWORD = 8
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 5  # OWASP's scrypt minimum: 16 MiB per hash
NO_HASH = f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${'0' * 32}${'0' * 128}"  # matches nothing

DB = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]


# --- passwords and tokens -------------------------------------------------------------------


def hash_password(password: str) -> str:
    """`scrypt$n$r$p$salt$hash`: the parameters travel with the hash, so they can be raised."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Hashes even when there is no stored hash, so timing doesn't tell which usernames exist."""
    _, n, r, p, salt, digest = (stored or NO_HASH).split("$")
    test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
    return stored is not None and hmac.compare_digest(test.hex(), digest)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(credentials: Credentials, session: DB) -> User:
    """The user whose unexpired token the request carries; anything else is a 401."""
    user = session.scalar(
        select(User)
        .join(AuthToken, AuthToken.user_id == User.id)
        .where(
            AuthToken.token_hash == _digest(credentials.credentials),
            AuthToken.expires_at > func.now(),
        )
    )
    if user is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(current_user)]


# --- endpoints ------------------------------------------------------------------------------


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1024)


@router.post("/auth/login")
def login(body: Login, session: DB) -> dict[str, Any]:
    user = session.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not verify_password(body.password, user.password_hash if user else None):
        raise HTTPException(401, "Wrong username or password")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().token_ttl_hours)
    session.execute(delete(AuthToken).where(AuthToken.expires_at <= func.now()))  # tidy up
    session.add(AuthToken(user_id=user.id, token_hash=_digest(token), expires_at=expires_at))
    session.commit()
    return {"token": token, "expires_at": expires_at}


@router.post("/auth/logout", status_code=204)
def logout(credentials: Credentials, _: CurrentUser, session: DB) -> None:
    token_hash = _digest(credentials.credentials)
    session.execute(delete(AuthToken).where(AuthToken.token_hash == token_hash))
    session.commit()


@router.get("/me")
def me(user: CurrentUser, session: DB) -> dict[str, Any]:
    """Who is logged in, and the accounts an admin linked to them."""
    accounts = session.scalars(
        select(UserSourceIdentity)
        .where(UserSourceIdentity.user_id == user.id)
        .order_by(UserSourceIdentity.id)
    )
    return {
        "username": user.username,
        "display_name": user.display_name,
        "accounts": [
            {"tool": a.source_kind, "id": a.external_id, "display_name": a.display_name}
            for a in accounts
        ],
    }


# --- admin (scripts/users.py) ---------------------------------------------------------------


def add_user(session: Session, username: str, password: str, display_name: str = "") -> User:
    username = username.strip().lower()
    if not USERNAME.fullmatch(username):
        raise ValueError("A username is letters, digits, '.', '_' or '-' (at most 100).")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"A password needs at least {MIN_PASSWORD} characters.")
    if session.scalar(select(User.id).where(User.username == username)):
        raise ValueError(f"User {username} already exists.")
    user = User(
        username=username,
        display_name=display_name.strip() or None,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    return user


def link_account(
    session: Session, username: str, tool: str, account_id: str, display_name: str = ""
) -> UserSourceIdentity:
    """Link a GitHub login, Jira account id or Slack user id to a user; again = rename it."""
    user = session.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None:
        raise ValueError(f"No user {username}.")
    tool, account_id = tool.strip().lower(), account_id.strip()
    if tool not in ACCOUNT_ID:
        raise ValueError(f"The tool is one of: {', '.join(ACCOUNT_ID)}.")
    if not ACCOUNT_ID[tool].fullmatch(account_id):
        raise ValueError(f"{account_id!r} doesn't look like a {tool} account id.")
    linked = session.scalar(
        select(UserSourceIdentity).where(
            UserSourceIdentity.source_kind == tool, UserSourceIdentity.external_id == account_id
        )
    )
    if linked and linked.user_id != user.id:
        raise ValueError(f"{tool}:{account_id} is already linked to another user.")
    linked = linked or UserSourceIdentity(user_id=user.id, source_kind=tool, external_id=account_id)
    linked.display_name = display_name.strip() or linked.display_name
    session.add(linked)
    session.commit()
    return linked
