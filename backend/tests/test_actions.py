"""Phase 8: an action request becomes a pending approval card; approve runs it, reject doesn't."""

import json
import logging
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.actions import action_runner
from app.api.auth import link_account
from app.api.chat import chat_models
from app.api.main import app
from app.chat.intent import ACTION
from app.chat.pipeline import CANT_DO
from app.db.schema import Source
from app.learning.connectors.jira import JiraConnector
from tests.fakes import api, fake_ollama, login_as

REQUEST = "open a jira ticket to add monitoring for payments"
PLAN = {
    "kind": "create_jira_ticket",
    "project": "PAY",
    "title": "Add monitoring for payments",
    "description": "Add monitoring and alerts for the payment service.",
}
REWRITE = json.dumps({"question": REQUEST})  # later messages in a chat are rewritten first
created: list[tuple[str, str, str]] = []


def _create(project: str, title: str, description: str) -> dict[str, str]:
    created.append((project, title, description))
    return {"key": "PAY-77", "link": "https://jira.test/browse/PAY-77"}


@pytest.fixture
def alice(db_session: Session) -> Iterator[tuple[str, dict[str, str]]]:
    """(messages url, headers) of alice's new chat; alice may see Jira project PAY, not SEC."""
    db_session.add_all([
        Source(kind="jira", name="Payments", external_id="PAY", members=["jira:acc-1"]),
        Source(kind="jira", name="Security", external_id="SEC", members=["jira:acc-9"]),
    ])  # fmt: skip
    db_session.commit()
    headers = login_as(db_session, "alice")
    link_account(db_session, "alice", "jira", "acc-1")
    chat_id = api.post("/chat/sessions", json={}, headers=headers).json()["id"]
    created.clear()
    app.dependency_overrides[action_runner] = lambda: _create
    yield f"/chat/sessions/{chat_id}/messages", headers
    app.dependency_overrides.clear()


def _ask(url: str, headers: dict[str, str], *replies: str, message: str = REQUEST) -> dict:
    client, requests = fake_ollama(*replies)
    detect = lambda texts: [0.0] * len(texts)  # noqa: E731
    app.dependency_overrides[chat_models] = lambda: {
        "classify": lambda m: [ACTION], "detect": detect, "client": client
    }  # fmt: skip
    reply = api.post(url, json={"message": message}, headers=headers).json()
    reply["_requests"] = requests
    return reply


def test_an_action_request_returns_a_filled_card_and_creates_nothing(
    alice: tuple[str, dict[str, str]],
) -> None:
    url, headers = alice
    reply = _ask(url, headers, json.dumps(PLAN))

    assert reply["path"] == ACTION
    card = reply["action"]
    assert card["status"] == "pending" and card["kind"] == "create_jira_ticket"
    assert card["payload"] == {k: v for k, v in PLAN.items() if k != "kind"}
    assert "PAY" in reply["reply"] and "Nothing happens until you approve" in reply["reply"]
    assert created == []  # nothing run yet
    sent = reply["_requests"][0]
    assert sent["model"] == "qwen3:8b" and "<projects>PAY (Payments)</projects>" in sent["prompt"]
    assert "SEC" not in sent["prompt"]  # a project alice can't see is never offered
    assert api.get("/actions", headers=headers).json()[0]["status"] == "pending"


def test_unsupported_requests_and_users_without_jira_get_no_card(
    alice: tuple[str, dict[str, str]], db_session: Session
) -> None:
    url, headers = alice
    unsupported = {"kind": "unsupported", "project": "", "title": "", "description": ""}
    assert _ask(url, headers, json.dumps(unsupported), message="merge PR #50")["reply"] == CANT_DO
    elsewhere = {**PLAN, "project": "SEC"}  # alice's only project wins over one she can't see
    planned = _ask(url, headers, REWRITE, json.dumps(elsewhere))["action"]
    assert planned["payload"]["project"] == "PAY"

    bob = login_as(db_session, "bob")  # no Jira account linked
    chat = api.post("/chat/sessions", json={}, headers=bob).json()["id"]
    reply = _ask(f"/chat/sessions/{chat}/messages", bob)  # no model call: fake has no replies
    assert reply["reply"] == CANT_DO and reply["action"] is None and reply["_requests"] == []
    assert [a["status"] for a in api.get("/actions", headers=headers).json()] == ["pending"]


def test_approve_runs_it_reject_does_nothing_both_logged(
    alice: tuple[str, dict[str, str]], db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    url, headers = alice
    first = _ask(url, headers, json.dumps(PLAN))["action"]["id"]
    second = _ask(url, headers, REWRITE, json.dumps(PLAN))["action"]["id"]
    bob = login_as(db_session, "bob")

    with caplog.at_level(logging.INFO, logger="syncra.actions"):
        assert api.post(f"/actions/{first}/approve", headers=bob).status_code == 404  # not his
        done = api.post(f"/actions/{first}/approve", headers=headers).json()
        rejected = api.post(f"/actions/{second}/reject", headers=headers).json()

    assert done["status"] == "done" and done["result"]["key"] == "PAY-77"
    assert created == [("PAY", PLAN["title"], PLAN["description"] +
                        "\n\nRequested by alice via Syncra.")]  # fmt: skip
    assert rejected["status"] == "rejected" and rejected["result"] is None and len(created) == 1
    assert api.post(f"/actions/{first}/approve", headers=headers).status_code == 409  # once only
    assert api.post(f"/actions/{second}/approve", headers=headers).status_code == 409
    assert f"action {first} approved by alice" in caplog.text
    assert f"action {first} done" in caplog.text
    assert f"action {second} rejected by alice" in caplog.text


def test_a_failing_run_is_recorded(alice: tuple[str, dict[str, str]]) -> None:
    url, headers = alice
    action = _ask(url, headers, json.dumps(PLAN))["action"]["id"]

    def broken(project: str, title: str, description: str) -> dict[str, str]:
        raise httpx.ConnectError("jira is down")

    app.dependency_overrides[action_runner] = lambda: broken
    failed = api.post(f"/actions/{action}/approve", headers=headers).json()
    assert failed["status"] == "failed" and "jira is down" in failed["result"]["error"]


def test_jira_create_issue() -> None:
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "1", "key": "PAY-78"})

    jira = JiraConnector("PAY", base_url="https://jira.test", email="e", api_token="t",
                         transport=httpx.MockTransport(handler))  # fmt: skip
    assert jira.create_issue("Add monitoring", "Why.\n\nRequested by alice.") == {
        "key": "PAY-78", "link": "https://jira.test/browse/PAY-78"
    }  # fmt: skip
    fields = sent[0]["fields"]
    assert fields["project"] == {"key": "PAY"} and fields["summary"] == "Add monitoring"
    assert fields["issuetype"] == {"name": "Task"} and len(fields["description"]["content"]) == 2
