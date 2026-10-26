"""Action endpoints (Task 8.2): see your approval cards, approve or reject them.

An action is planned in the chat (`path: action`) and waits as `pending`. Approving runs it
with your own permissions and records the result; rejecting does nothing. Someone else's action
answers 404, exactly like one that doesn't exist; an action already settled answers 409.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, UNAUTHORIZED, CurrentUser
from app.db.models import Action
from app.schemas.actions import Card
from app.services.chat import actions

router = APIRouter(prefix="/actions", tags=["Actions"], responses=UNAUTHORIZED)
NOT_FOUND = {404: {"description": "Not one of your actions"}}
SETTLED = {409: {"description": "Already approved, rejected, done or failed"}}


def _pending(session: DB, user: CurrentUser, action_id: int) -> Action:
    try:
        action = actions.own_pending(session, user, action_id)
    except actions.NotPending as exc:
        raise HTTPException(409, f"This action is already {exc}") from exc
    if action is None:
        raise HTTPException(404, "Action not found")
    return action


@router.get("", response_model=list[Card], summary="List my actions")
def my_actions(user: CurrentUser, session: DB) -> Sequence[Action]:
    """Your actions, newest first."""
    return session.scalars(
        select(Action).where(Action.user_id == user.id).order_by(Action.id.desc())
    ).all()


@router.post(
    "/{action_id}/approve", response_model=Card, summary="Approve and run an action",
    responses={**NOT_FOUND, **SETTLED},
)  # fmt: skip
def approve(
    action_id: int,
    user: CurrentUser,
    session: DB,
) -> Action:
    """Run a pending action with your permissions. `status` ends as `done` with the result
    (the new ticket's key and link) or `failed` with the error."""
    return actions.approve(session, _pending(session, user, action_id), user)


@router.post(
    "/{action_id}/reject", response_model=Card, summary="Reject an action",
    responses={**NOT_FOUND, **SETTLED},
)  # fmt: skip
def reject(action_id: int, user: CurrentUser, session: DB) -> Action:
    """Drop a pending action: nothing is run."""
    return actions.reject(session, _pending(session, user, action_id), user)
