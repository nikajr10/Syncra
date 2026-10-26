"""Login (Task 5.1): local accounts and bearer tokens.

POST /auth/login hands out a random bearer token that expires after TOKEN_TTL_HOURS (see
`app.core.security`); logging out deletes it. Admins create users and link their accounts with
`make add-user` and `make link-account` (`app.services.users`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, func, select

from app.api.deps import DB, UNAUTHORIZED, Credentials, CurrentUser
from app.core.config import get_settings
from app.core.security import new_token, token_digest, verify_password
from app.db.models import AuthToken, User, UserSourceIdentity
from app.schemas.auth import Account, Login, Me, Token

router = APIRouter(tags=["Login"])


@router.post(
    "/auth/login",
    summary="Log in",
    responses={401: {"description": "Wrong username or password"}},
)
def login(body: Login, session: DB) -> Token:
    """Check the username and password and hand out a token that works for TOKEN_TTL_HOURS."""
    user = session.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not verify_password(body.password, user.password_hash if user else None):
        raise HTTPException(401, "Wrong username or password")
    token = new_token()
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().token_ttl_hours)
    session.execute(delete(AuthToken).where(AuthToken.expires_at <= func.now()))  # tidy up
    session.add(AuthToken(user_id=user.id, token_hash=token_digest(token), expires_at=expires_at))
    session.commit()
    return Token(token=token, expires_at=expires_at)


@router.post("/auth/logout", status_code=204, summary="Log out", responses=UNAUTHORIZED)
def logout(credentials: Credentials, _: CurrentUser, session: DB) -> None:
    """The token stops working at once."""
    token_hash = token_digest(credentials.credentials)
    session.execute(delete(AuthToken).where(AuthToken.token_hash == token_hash))
    session.commit()


@router.get("/me", summary="Who am I?", responses=UNAUTHORIZED)
def me(user: CurrentUser, session: DB) -> Me:
    """Who is logged in, and the accounts an admin linked to them."""
    accounts = session.scalars(
        select(UserSourceIdentity)
        .where(UserSourceIdentity.user_id == user.id)
        .order_by(UserSourceIdentity.id)
    )
    return Me(
        username=user.username,
        display_name=user.display_name,
        is_admin=user.is_admin,
        accounts=[
            Account(tool=a.source_kind, id=a.external_id, display_name=a.display_name)
            for a in accounts
        ],
    )
