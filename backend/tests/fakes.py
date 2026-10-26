"""Fakes and helpers shared by tests. No network, no real services."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import add_user
from app.api.main import app
from app.db.schema import Chunk, Decision, Edge, Entity, Item
from app.learning.connectors.base import RawItem
from app.models.gateway import OllamaClient

api = TestClient(app)


def login_as(session: Session, username: str) -> dict[str, str]:
    """Create the user and log in: the headers that carry their token."""
    add_user(session, username, "correct horse")
    response = api.post("/auth/login", json={"username": username, "password": "correct horse"})
    return {"Authorization": f"Bearer {response.json()['token']}"}


def fake_ollama(*replies: str) -> tuple[OllamaClient, list[dict]]:
    """A client whose Ollama answers `replies` in turn (word by word when streaming); returns it
    and the requests it got."""
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        reply = replies[len(requests) - 1]
        if requests[-1]["stream"]:  # streamed word by word
            lines = [{"response": w, "done": False} for w in re.findall(r"\S+\s*", reply)]
            lines.append({"response": "", "done": True})
            return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines))
        return httpx.Response(200, json={"response": reply, "done": True})

    client = OllamaClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return client, requests


def fake_ollama_stream(*pieces: str) -> tuple[OllamaClient, list[dict]]:
    """A client whose Ollama streams `pieces` one line each, then "done"; and the requests."""
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        lines = [{"response": p, "done": False} for p in pieces] + [{"response": "", "done": True}]
        return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines))

    client = OllamaClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return client, requests


def item(n: int, text: str = "", **overrides: object) -> RawItem:
    base = dict(
        external_id=str(n),
        type="message",
        text=text or f"message {n}",
        author="slack:U1",
        created_at=datetime(2026, 10, 1, 0, 0, n, tzinfo=UTC),
        link=f"https://example.test/{n}",
        access_tags=("slack:channel:C1",),
    )
    return RawItem(**{**base, **overrides})


class FakeConnector:
    """Items with numeric external ids; the cursor is the highest id handed out so far."""

    def __init__(self, items: list[RawItem]) -> None:
        self.items = items
        self.calls: list[str | None] = []

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        self.calls.append(since_cursor)
        start = int(since_cursor) if since_cursor else 0
        new = [i for i in self.items if int(i.external_id) > start]
        return new, (new[-1].external_id if new else since_cursor)

    def members(self) -> list[str]:
        return ["slack:U1"]


class Feed:
    """A source whose items arrive in order: each fetch returns what it hasn't handed out yet."""

    def __init__(self, *items: RawItem) -> None:
        self.items = list(items)

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        start = int(since_cursor or 0)
        return self.items[start:], str(len(self.items))

    def members(self) -> list[str]:
        return ["slack:U1"]


def graph_links(session: Session) -> list[tuple[str, str, str]]:
    """Every knowledge-graph link as (from, relation, to) with readable names, duplicates kept."""
    session.expire_all()  # other sessions may have written
    items = {i.id: i.external_id for i in session.scalars(select(Item))}
    name = {("entity", e.id): e.name for e in session.scalars(select(Entity))}
    name |= {("item", i): external for i, external in items.items()}
    name |= {
        ("chunk", c.id): f"chunk of {items[c.item_id]}" for c in session.scalars(select(Chunk))
    }
    name |= {
        ("decision", d.id): f"decision on {items[d.item_id]}"
        for d in session.scalars(select(Decision))
    }
    return sorted(
        (name[e.src_type, e.src_id], e.relation, name[e.dst_type, e.dst_id])
        for e in session.scalars(select(Edge))
    )
