"""Admin endpoints (Tasks 9.4, 10.5): connect sources, watch them sync, link people's accounts,
and see what went wrong (failed syncs and learning runs, model errors, slow answers).

Only admins (`users.is_admin`, set by `make add-user`) may call these; anyone else gets 403.
The tools' credentials stay in `backend/.env`: `GET /admin/sources` says which are configured.
A new source syncs with the next learning run, or right away with `POST …/sync`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, FORBIDDEN, UNAUTHORIZED, require_admin
from app.connectors import EXTERNAL_ID, build_connector
from app.core import monitor
from app.core.config import get_settings
from app.db.models import Event, Item, Source, User, UserSourceIdentity
from app.db.session import new_session
from app.schemas.admin import (
    EventView,
    NewAccount,
    NewSource,
    SourceChange,
    Sources,
    SourceView,
    Status,
    UserView,
)
from app.schemas.auth import Account
from app.services.learning.sync import sync_source
from app.services.users import link_account

log = logging.getLogger("syncra.admin")
NOT_FOUND = {404: {"description": "No such source or user"}}


router = APIRouter(
    prefix="/admin", responses={**UNAUTHORIZED, **FORBIDDEN},
    dependencies=[Depends(require_admin)],
)  # fmt: skip


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


@router.get("/sources", response_model=Sources, tags=["Sources"], summary="List sources")
def sources(session: DB) -> Sources:
    rows = session.scalars(select(Source).order_by(Source.kind, Source.name)).all()
    return Sources(tools=configured_tools(), sources=[_view(session, s) for s in rows])


BAD_ID = {422: {"description": "Not a valid id for that tool"}}


@router.post("/sources", status_code=201, response_model=SourceView, tags=["Sources"],
             summary="Create source",
             responses={409: {"description": "Already added"}, **BAD_ID})  # fmt: skip
def add_source(body: NewSource, session: DB) -> SourceView:
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


@router.patch("/sources/{source_id}", response_model=SourceView, tags=["Sources"],
              summary="Update source", responses=NOT_FOUND)  # fmt: skip
def change_source(source_id: int, body: SourceChange, session: DB) -> SourceView:
    """Pause or resume syncing."""
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
             tags=["Sources"], summary="Sync source", responses=NOT_FOUND)  # fmt: skip
def sync_now(
    source_id: int,
    session: DB,
    background: BackgroundTasks,
) -> SourceView:
    """Runs in the background; check `last_synced_at` and `last_error` in *List sources*."""
    source = _source(session, source_id)
    background.add_task(_sync, source.id)
    return _view(session, source)


@router.get("/users", response_model=list[UserView], tags=["Users"], summary="List users")
def users(session: DB) -> list[UserView]:
    links: dict[int, list[Account]] = {}
    for i in session.scalars(select(UserSourceIdentity).order_by(UserSourceIdentity.id)):
        links.setdefault(i.user_id, []).append(Account(tool=i.source_kind, id=i.external_id,
                                                       display_name=i.display_name))  # fmt: skip
    rows: Sequence[User] = session.scalars(select(User).order_by(User.username)).all()
    return [UserView(username=u.username, display_name=u.display_name, is_admin=u.is_admin,
                     accounts=links.get(u.id, [])) for u in rows]  # fmt: skip


@router.post("/users/{username}/accounts", status_code=201, response_model=Account,
             tags=["Users"], summary="Link account", responses={**NOT_FOUND, **BAD_ID})  # fmt: skip
def add_account(username: str, body: NewAccount, session: DB) -> Account:
    """GitHub login, Jira accountId or Slack member ID. An account belongs to one user."""
    try:
        linked = link_account(session, username, body.tool, body.account_id, body.display_name)
    except ValueError as exc:
        raise HTTPException(404 if str(exc).startswith("No user") else 422, str(exc)) from exc
    log.info("linked %s:%s to %s", linked.source_kind, linked.external_id, username)
    return Account(tool=linked.source_kind, id=linked.external_id,
                   display_name=linked.display_name)  # fmt: skip


@router.get("/status", response_model=Status, tags=["Status"], summary="System status")
def status(session: DB, limit: int = 50) -> Status:
    """Item counts by status, source sync state and the latest error events."""
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
