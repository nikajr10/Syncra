"""Task 6.1: a user only ever gets chunks of items they may see, filtered inside the query."""

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import add_user, link_account
from app.chat.permissions import user_tags, visible
from app.db.schema import Chunk, Item, Source
from app.learning.connectors.github import GitHubConnector
from app.learning.connectors.jira import JiraConnector
from app.learning.connectors.slack import SlackConnector
from app.learning.sync import sync_source
from tests.fakes import FakeConnector, item


def _store(session: Session) -> None:
    """A private repo bob can see, a channel alice is in, a public repo: one chunk each."""
    sources = {
        "secret": Source(kind="github", name="acme/secret", external_id="acme/secret",
                         members=["github:bob"]),
        "eng": Source(kind="slack", name="#eng", external_id="C1", members=["slack:U01"]),
        "oss": Source(kind="github", name="acme/oss", external_id="acme/oss"),
    }  # fmt: skip
    session.add_all(sources.values())
    session.flush()
    for name, source in sources.items():
        tags = [source.access_tag] + (["public"] if name == "oss" else [])
        row = Item(source_id=source.id, external_id=name, type="issue", text=name,
                   access_tags=tags)  # fmt: skip
        session.add(row)
        session.flush()
        session.add(Chunk(item_id=row.id, position=0, text=f"{name} chunk"))
    session.commit()


def _search(session: Session, user_id: int) -> set[str]:
    query = select(Chunk.text).join(Item).where(visible(user_tags(session, user_id)))
    return set(session.scalars(query))


def test_users_only_get_chunks_they_may_see(db_session: Session) -> None:
    _store(db_session)
    alice = add_user(db_session, "alice", "correct horse")
    bob = add_user(db_session, "bob", "correct horse")
    carol = add_user(db_session, "carol", "correct horse")  # no linked accounts
    link_account(db_session, "alice", "slack", "U01")
    link_account(db_session, "bob", "github", "bob")

    assert _search(db_session, alice.id) == {"eng chunk", "oss chunk"}
    assert _search(db_session, bob.id) == {"secret chunk", "oss chunk"}
    assert _search(db_session, carol.id) == {"oss chunk"}
    assert user_tags(db_session, alice.id) == ["public", "slack:channel:C1"]


def test_leaving_a_channel_takes_effect_at_the_next_sync(db_session: Session) -> None:
    source = Source(kind="slack", name="#eng", external_id="C1", members=["slack:U09"])
    db_session.add(source)
    db_session.commit()
    alice = add_user(db_session, "alice", "correct horse")
    link_account(db_session, "alice", "slack", "U09")
    assert "slack:channel:C1" in user_tags(db_session, alice.id)

    sync_source(db_session, source, FakeConnector([item(1)]), scrub=lambda i: i)  # U1 only now

    assert source.members == ["slack:U1"]
    assert user_tags(db_session, alice.id) == ["public"]


def _transport(routes: dict[str, object]) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, json=routes[request.url.path]))


def test_connectors_list_members() -> None:
    slack = SlackConnector("C1", token="x", api_url="https://slack.test/api", transport=_transport(
        {"/api/conversations.members": {"ok": True, "members": ["U1", "U2"]}}
    ))  # fmt: skip
    assert slack.members() == ["slack:U1", "slack:U2"]

    repo = {"/repos/acme/secret": {"private": True},
            "/repos/acme/secret/collaborators": [{"login": "bob"}]}  # fmt: skip
    github = GitHubConnector("acme/secret", token="x", api_url="https://gh.test",
                             transport=_transport(repo))  # fmt: skip
    assert github.members() == ["github:bob"]
    oss = _transport({"/repos/acme/oss": {"private": False}})
    public = GitHubConnector("acme/oss", token="x", api_url="https://gh.test", transport=oss)
    assert public.members() == []  # its items are tagged public

    users = {"/rest/api/3/user/permission/search": [{"accountId": "a1"}, {"accountId": "a2"}]}
    jira = JiraConnector("PAY", base_url="https://jira.test", email="e", api_token="t",
                         transport=_transport(users))  # fmt: skip
    assert jira.members() == ["jira:a1", "jira:a2"]
