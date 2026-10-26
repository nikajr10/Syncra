"""Tasks 9.4 and 10.5 (backend): an admin adds sources, sees them sync and what went wrong,
links accounts; everyone else gets 403."""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.api.admin import connector_builder
from app.api.auth import add_user
from app.api.chat import chat_models
from app.api.main import app
from app.chat.intent import SMALL_TALK
from app.config.settings import get_settings
from app.db.schema import Source
from tests.fakes import FakeConnector, api, item, login_as


class Broken:
    def fetch_new(self, since_cursor: str | None) -> tuple:
        raise ConnectionError("slack is down")

    def members(self) -> list[str]:
        return []


@pytest.fixture
def root(db_session: Session) -> Iterator[dict[str, str]]:
    """Headers of a logged-in admin."""
    add_user(db_session, "root", "correct horse", is_admin=True)
    token = api.post("/auth/login", json={"username": "root", "password": "correct horse"})
    yield {"Authorization": f"Bearer {token.json()['token']}"}
    app.dependency_overrides.clear()


def test_an_admin_adds_a_source_and_sees_it_sync(root: dict[str, str]) -> None:
    connectors = {"C1": FakeConnector([item(1), item(2)]), "C2": Broken()}
    app.dependency_overrides[connector_builder] = lambda: lambda s: connectors[s.external_id]

    added = api.post("/admin/sources", json={"kind": "slack", "external_id": "C1",
                                             "name": "#eng"}, headers=root)  # fmt: skip
    assert added.status_code == 201 and added.json()["last_synced_at"] is None
    source = added.json()["id"]
    assert api.post(f"/admin/sources/{source}/sync", headers=root).status_code == 202

    listed = api.get("/admin/sources", headers=root).json()
    assert set(listed["tools"]) == {"github", "jira", "slack"}
    [eng] = listed["sources"]
    assert eng["name"] == "#eng" and eng["last_synced_at"] and eng["last_error"] is None
    assert eng["items"] == 2 and eng["members"] == 1

    broken = api.post("/admin/sources", json={"kind": "slack", "external_id": "C2"}, headers=root)
    api.post(f"/admin/sources/{broken.json()['id']}/sync", headers=root)
    listed = api.get("/admin/sources", headers=root).json()["sources"]
    errors = {s["external_id"]: s["last_error"] for s in listed}
    assert errors == {"C1": None, "C2": "ConnectionError: slack is down"}


def test_sources_are_checked_and_can_be_paused(root: dict[str, str], db_session: Session) -> None:
    for bad in ({"kind": "github", "external_id": "../etc"}, {"kind": "jira", "external_id": "x"},
                {"kind": "teams", "external_id": "T1"}):  # fmt: skip
        assert api.post("/admin/sources", json=bad, headers=root).status_code == 422
    body = {"kind": "jira", "external_id": "PAY"}
    source = api.post("/admin/sources", json=body, headers=root).json()["id"]
    assert api.post("/admin/sources", json=body, headers=root).status_code == 409
    paused = api.patch(f"/admin/sources/{source}", json={"enabled": False}, headers=root)
    assert paused.json()["enabled"] is False and db_session.get(Source, source).enabled is False
    assert api.post("/admin/sources/999/sync", headers=root).status_code == 404


def test_an_admin_links_accounts(root: dict[str, str], db_session: Session) -> None:
    login_as(db_session, "alice")
    linked = api.post("/admin/users/alice/accounts",
                      json={"tool": "slack", "account_id": "U01", "display_name": "Alice"},
                      headers=root)  # fmt: skip
    assert linked.status_code == 201 and linked.json()["id"] == "U01"
    users = {u["username"]: u for u in api.get("/admin/users", headers=root).json()}
    assert users["alice"]["accounts"] == [{"tool": "slack", "id": "U01", "display_name": "Alice"}]
    assert users["root"]["is_admin"] and not users["alice"]["is_admin"]

    def link(username: str, account: str) -> int:
        body = {"tool": "slack", "account_id": account}
        return api.post(f"/admin/users/{username}/accounts", json=body, headers=root).status_code

    assert link("nobody", "U02") == 404
    assert link("alice", "not-an-id") == 422
    login_as(db_session, "bob")
    assert link("bob", "U01") == 422  # already alice's


def test_only_admins(db_session: Session) -> None:
    alice = login_as(db_session, "alice")
    calls = [("get", "/admin/sources"), ("post", "/admin/sources"),
             ("patch", "/admin/sources/1"), ("post", "/admin/sources/1/sync"),
             ("get", "/admin/users"), ("post", "/admin/users/alice/accounts"),
             ("get", "/admin/status")]  # fmt: skip
    for method, path in calls:
        assert api.request(method, path, json={}, headers=alice).status_code == 403, path


def test_a_failed_sync_and_a_slow_answer_are_visible_to_an_admin(
    root: dict[str, str], db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[connector_builder] = lambda: lambda s: Broken()
    source = api.post("/admin/sources", json={"kind": "slack", "external_id": "C2"}, headers=root)
    api.post(f"/admin/sources/{source.json()['id']}/sync", headers=root)

    monkeypatch.setattr(get_settings(), "slow_answer_seconds", 0.0)  # every answer is "slow"
    alice = login_as(db_session, "alice")
    chat = api.post("/chat/sessions", json={}, headers=alice).json()["id"]
    app.dependency_overrides[chat_models] = lambda: {
        "classify": lambda m: [SMALL_TALK], "detect": lambda t: [0.0] * len(t)
    }  # fmt: skip
    api.post(f"/chat/sessions/{chat}/messages", json={"message": "hi"}, headers=alice)

    status = api.get("/admin/status", headers=root).json()
    kinds = {e["kind"]: e for e in status["events"]}
    assert "slack is down" in kinds["sync_failed"]["message"]
    slow = kinds["slow_answer"]
    assert slow["details"]["chat_id"] == chat
    assert {"memory", "guard", "intent", "total"} <= set(slow["details"]["timings"])
    assert status["sources"][0]["last_error"] == "ConnectionError: slack is down"
    assert api.get("/admin/status", headers=alice).status_code == 403
