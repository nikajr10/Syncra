"""Admin endpoints (Tasks 9.4, 10.5): connect sources, watch them sync, link people's accounts,
and see what went wrong (failed syncs and learning runs, model errors, slow answers).

Only admins (`users.is_admin`, set by `make add-user`) may call these; anyone else gets 403.
The tools' credentials stay in `backend/.env`: `GET /admin/sources` says which are configured.
A new source syncs with the next learning run, or right away with `POST …/sync`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import monitor
from app.api.auth import DB, UNAUTHORIZED, Account, CurrentUser, link_account
from app.config.settings import get_settings
from app.db.engine import new_session
from app.db.schema import Event, Item, Source, User, UserSourceIdentity
from app.learning.connectors import EXTERNAL_ID, build_connector
from app.learning.sync import sync_source

log = logging.getLogger("syncra.admin")
FORBIDDEN = {403: {"description": "Admins only"}}
NOT_FOUND = {404: {"description": "No such source or user"}}


def admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    return user


router = APIRouter(
    prefix="/admin", tags=["Admin"], responses={**UNAUTHORIZED, **FORBIDDEN},
    dependencies=[Depends(admin)],
)  # fmt: skip
Kind = Literal["github", "jira", "slack"]


class NewSource(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Kind
    external_id: str = Field(
        description="GitHub owner/repo, Jira project key or Slack channel id",
        examples=["acme/payments"],
    )
    name: str | None = Field(default=None, max_length=200, description="Shown in answers")


class SourceChange(BaseModel):
    enabled: bool


class SourceView(BaseModel):
    id: int
    kind: str
    name: str
    external_id: str
    enabled: bool
    last_synced_at: datetime | None
    last_error: str | None = Field(description="Why the last sync failed; empty once one works")
    items: int = Field(description="Items stored from it")
    members: int = Field(description="Accounts that may see it, at the last sync")


class Sources(BaseModel):
    tools: dict[str, bool] = Field(description="Which tools have credentials in backend/.env")
    sources: list[SourceView]


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(description="sync_failed, learn_failed, model_error or slow_answer")
    message: str
    details: dict[str, Any]
    created_at: datetime


class Status(BaseModel):
    items: dict[str, int] = Field(
        description="Stored items by status: new, processed, noise, failed"
    )
    sources: list[SourceView]
    events: list[EventView] = Field(description="The latest problems, newest first")


class NewAccount(BaseModel):
    tool: Kind
    account_id: str = Field(examples=["alice"])
    display_name: str = ""


class UserView(BaseModel):
    username: str
    display_name: str | None
    is_admin: bool
    accounts: list[Account]


def configured_tools() -> dict[str, bool]:
    s = get_settings()
    return {
        "github": bool(s.github_token),
        "jira": bool(s.jira_base_url and s.jira_email and s.jira_api_token),
        "slack": bool(s.slack_bot_token),
    }


def _view(session: Session, source: Source) -> SourceView:
    items = session.scalar(select(func.count()).where(Item.source_id == source.id)) or 0
    return SourceView(
        id=source.id, kind=source.kind, name=source.name, external_id=source.external_id,
        enabled=source.enabled, last_synced_at=source.last_synced_at,
        last_error=source.last_error, items=items, members=len(source.members),
    )  # fmt: skip


def _source(session: Session, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    return source


@router.get("/sources", response_model=Sources, summary="List sources and their sync status")
def sources(session: DB) -> Sources:
    rows = session.scalars(select(Source).order_by(Source.kind, Source.name)).all()
    return Sources(tools=configured_tools(), sources=[_view(session, s) for s in rows])


BAD_ID = {422: {"description": "Not a valid id for that tool"}}


@router.post("/sources", status_code=201, response_model=SourceView, summary="Add a source",
             responses={409: {"description": "Already added"}, **BAD_ID})  # fmt: skip
def add_source(body: NewSource, session: DB) -> SourceView:
    """Connect a repo, project or channel. It syncs with the next learning run."""
    if not EXTERNAL_ID[body.kind].fullmatch(body.external_id):
        raise HTTPException(422, f"That doesn't look like a {body.kind} id")
    taken = select(Source.id).where(
        Source.kind == body.kind, Source.external_id == body.external_id
    )
    if session.scalar(taken):
        raise HTTPException(409, "This source is already added")
    source = Source(kind=body.kind, external_id=body.external_id,
                    name=body.name or body.external_id)  # fmt: skip
    session.add(source)
    session.commit()
    log.info("source %s %s added", source.kind, source.external_id)
    return _view(session, source)


@router.patch("/sources/{source_id}", response_model=SourceView, summary="Pause or resume a source",
              responses=NOT_FOUND)  # fmt: skip
def change_source(source_id: int, body: SourceChange, session: DB) -> SourceView:
    """A paused source isn't synced; what was learned from it stays searchable."""
    source = _source(session, source_id)
    source.enabled = body.enabled
    session.commit()
    return _view(session, source)


def _sync(source_id: int) -> None:
    with new_session() as session:
        source = session.get(Source, source_id)
        try:
            sync_source(session, source, build_connector(source))
        except Exception as exc:  # recorded for the admin, like the scheduled job does
            session.rollback()
            log.exception("sync failed for %s %s", source.kind, source.name)
            source.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            session.commit()
            monitor.record("sync_failed", f"{source.kind} {source.name}: {source.last_error}",
                           source_id=source.id)  # fmt: skip


@router.post("/sources/{source_id}/sync", status_code=202, response_model=SourceView,
             summary="Sync a source now", responses=NOT_FOUND)  # fmt: skip
def sync_now(
    source_id: int,
    session: DB,
    background: BackgroundTasks,
) -> SourceView:
    """Fetch its new items now, after this answer; watch `last_synced_at` and `last_error` in
    *List sources*. The worker learns from them on its next run."""
    source = _source(session, source_id)
    background.add_task(_sync, source.id)
    return _view(session, source)


@router.get("/users", response_model=list[UserView], summary="List users and their accounts")
def users(session: DB) -> list[UserView]:
    links: dict[int, list[Account]] = {}
    for i in session.scalars(select(UserSourceIdentity).order_by(UserSourceIdentity.id)):
        links.setdefault(i.user_id, []).append(Account(tool=i.source_kind, id=i.external_id,
                                                       display_name=i.display_name))  # fmt: skip
    rows: Sequence[User] = session.scalars(select(User).order_by(User.username)).all()
    return [UserView(username=u.username, display_name=u.display_name, is_admin=u.is_admin,
                     accounts=links.get(u.id, [])) for u in rows]  # fmt: skip


@router.post("/users/{username}/accounts", status_code=201, response_model=Account,
             summary="Link an account to a user", responses={**NOT_FOUND, **BAD_ID})  # fmt: skip
def add_account(username: str, body: NewAccount, session: DB) -> Account:
    """Link a GitHub login, Jira accountId or Slack member id: it decides what the user may
    search. An account already linked to someone else is refused."""
    try:
        linked = link_account(session, username, body.tool, body.account_id, body.display_name)
    except ValueError as exc:
        raise HTTPException(404 if str(exc).startswith("No user") else 422, str(exc)) from exc
    log.info("linked %s:%s to %s", linked.source_kind, linked.external_id, username)
    return Account(tool=linked.source_kind, id=linked.external_id,
                   display_name=linked.display_name)  # fmt: skip


@router.get("/status", response_model=Status, summary="See what went wrong")
def status(session: DB, limit: int = 50) -> Status:
    """Items by status, every source's last sync and error, and the latest events: failed syncs
    and learning runs, model errors and answers slower than SLOW_ANSWER_SECONDS."""
    counts = dict(session.execute(select(Item.status, func.count()).group_by(Item.status)).all())
    rows = session.scalars(select(Source).order_by(Source.kind, Source.name)).all()
    events = session.scalars(
        select(Event).order_by(Event.id.desc()).limit(min(max(limit, 1), 500))
    ).all()
    return Status(
        items=counts,
        sources=[_view(session, s) for s in rows],
        events=[EventView.model_validate(e) for e in events],
    )
