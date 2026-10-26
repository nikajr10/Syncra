"""Actions (Phase 8): Syncra proposes, the user approves, and only then does anything run.

`plan` (8.1) turns an `action` message into a structured action with Qwen3: so far one kind,
`create_jira_ticket` {project, title, description}, in a Jira project the user may see. It is
saved as `pending` and shown as an approval card; nothing is created yet.

`approve` / `reject` (8.2) settle a pending action. Approving checks again that the user may see
the project, creates the ticket and records the result (`done`, or `failed` with the error).
Every step is logged.
"""

from __future__ import annotations

import logging
import re
from string import Template
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_prompt
from app.db.models import Action, ChatSession, Source, User
from app.ml import gateway
from app.services.chat.permissions import user_tags

log = logging.getLogger("syncra.actions")

CREATE_JIRA_TICKET = "create_jira_ticket"
TAG = re.compile(r"</?\s*(?:projects|request)\b[^>]*>", re.I)


class Plan(BaseModel):
    """The JSON the action planner must answer with."""

    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Literal["create_jira_ticket", "unsupported"]
    project: str = Field(default="", max_length=50)
    title: str = Field(default="", max_length=255)  # Jira's summary limit
    description: str = Field(default="", max_length=5000)


SCHEMA = Plan.model_json_schema()


def card(action: Action) -> dict[str, Any]:
    """What the user sees: the action, its status and, once run, its result."""
    return {
        "id": action.id,
        "session_id": action.session_id,
        "kind": action.kind,
        "payload": action.payload,
        "status": action.status,
        "result": action.result,
    }


def jira_projects(session: Session, user_id: int) -> dict[str, str]:
    """{key: name} of the Jira projects the user may see."""
    tags = set(user_tags(session, user_id))
    sources = session.scalars(select(Source).where(Source.kind == "jira").order_by(Source.name))
    return {s.external_id: s.name for s in sources if s.access_tag in tags}


def plan(session: Session, chat: ChatSession, request: str) -> Action | None:
    """A pending action for `request` (flushed, not committed), or None when it isn't one Syncra
    can do. Raises `OllamaError` when Ollama is down."""
    projects = jira_projects(session, chat.user_id)
    if not projects:
        return None
    prompt = get_prompt("action_planner")
    listed = ", ".join(f"{key} ({TAG.sub('', name)})" for key, name in projects.items())
    user = Template(prompt.prompt).substitute(projects=listed, request=TAG.sub("", request))
    reply = gateway.chat_ollama().generate(
        "action_planner", user, system=prompt.system, json_mode=SCHEMA
    )
    try:
        planned = Plan.model_validate_json(reply)
    except ValidationError as exc:
        log.warning("action planner gave unusable JSON: %s", exc)
        return None
    if len(projects) == 1 and planned.project not in projects:
        planned.project = next(iter(projects))
    if planned.kind != CREATE_JIRA_TICKET or planned.project not in projects or not planned.title:
        return None
    action = Action(
        user_id=chat.user_id,
        session_id=chat.id,
        kind=CREATE_JIRA_TICKET,
        payload=planned.model_dump(exclude={"kind"}),
    )
    session.add(action)
    session.flush()
    log.info("action %s planned for user %s: %s", action.id, chat.user_id, action.payload)
    return action


# --- approve / reject (Task 8.2) -------------------------------------------------------------


class NotPending(Exception):
    """The action was already approved, rejected, done or failed."""


def _jira_create(project: str, title: str, description: str) -> dict[str, Any]:
    from app.connectors.jira import JiraConnector

    return JiraConnector(project).create_issue(title, description)


def own_pending(session: Session, user: User, action_id: int) -> Action | None:
    """The user's action, locked for this transaction; None if it isn't theirs or doesn't exist.
    Raises `NotPending` when it was already settled."""
    action = session.scalar(
        select(Action).where(Action.id == action_id, Action.user_id == user.id).with_for_update()
    )
    if action is not None and action.status != "pending":
        raise NotPending(action.status)
    return action


def reject(session: Session, action: Action, user: User) -> Action:
    action.status = "rejected"
    session.commit()
    log.info("action %s rejected by %s", action.id, user.username)
    return action


def approve(session: Session, action: Action, user: User) -> Action:
    """Run the approved action with the user's permissions and record the result."""
    payload = action.payload
    log.info("action %s approved by %s: %s", action.id, user.username, payload)
    action.status = "approved"
    session.commit()  # recorded even if running it crashes the process
    if payload["project"] not in jira_projects(session, user.id):
        action.status, action.result = "failed", {"error": "You can't see that Jira project."}
    else:
        description = f"{payload['description']}\n\nRequested by {user.username} via Syncra."
        try:
            action.result = _jira_create(payload["project"], payload["title"], description)
            action.status = "done"
        except Exception as exc:  # Jira down, no permission, bad project: recorded, not raised
            log.exception("action %s failed", action.id)
            action.status, action.result = "failed", {"error": f"{type(exc).__name__}: {exc}"}
    session.commit()
    log.info("action %s %s: %s", action.id, action.status, action.result)
    return action
