"""Dependencies shared by the routes: the database session and the logged-in user.

Protected endpoints take a `CurrentUser` argument: no valid token, no request. Admin routers
add `Depends(require_admin)`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.db.models import AuthToken, User
from app.db.session import get_db

bearer = HTTPBearer(description="The `token` from POST /auth/login.")  # no header -> 401
UNAUTHORIZED = {401: {"description": "No valid token: missing, unknown or expired"}}
FORBIDDEN = {403: {"description": "Admins only"}}

DB = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]


def current_user(credentials: Credentials, session: DB) -> User:
    """The user whose unexpired token the request carries; anything else is a 401."""
    user = session.scalar(
        select(User)
        .join(AuthToken, AuthToken.user_id == User.id)
        .where(
            AuthToken.token_hash == token_digest(credentials.credentials),
            AuthToken.expires_at > func.now(),
        )
    )
    if user is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    return user
