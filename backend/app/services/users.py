"""Creating users and linking their GitHub / Jira / Slack accounts (scripts/users.py, admin API).

Users can't link accounts themselves: their linked accounts decide what they may search, so a
self-claimed account would leak a colleague's channels. Every learning run merges a user's
accounts into one person (`link_identities`).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import User, UserSourceIdentity

USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")
ACCOUNT_ID = {  # what follows "github:" / "jira:" / "slack:" in the authors the connectors store
    "github": re.compile(r"[A-Za-z0-9-]{1,39}"),  # login
    "jira": re.compile(r"[A-Za-z0-9:_.-]{1,128}"),  # accountId
    "slack": re.compile(r"[UW][A-Z0-9]{2,30}"),  # user id
}
MIN_PASSWORD = 8


def add_user(
    session: Session, username: str, password: str, display_name: str = "", is_admin: bool = False
) -> User:
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
        is_admin=is_admin,
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
