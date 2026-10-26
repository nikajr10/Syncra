"""GET /chat/suggestions: questions from decisions the user may see, never from private ones."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.api.auth import link_account
from app.api.chat import same_topic
from app.db.schema import Decision, Item, Source
from tests.fakes import api, login_as


def _store(session: Session) -> None:
    pay = Source(kind="jira", name="Payments", external_id="PAY", members=["jira:acc-alice"])
    secret = Source(kind="github", name="acme/secret", external_id="acme/secret", members=[])
    session.add_all([pay, secret])
    session.flush()

    def add(source: Source, key: str, kind: str, title: str, day: int, decided: bool) -> None:
        when = datetime(2026, 9, day, tzinfo=UTC)
        item = Item(source_id=source.id, external_id=key, type=kind, title=title, text=title,
                    access_tags=[source.access_tag], created_at=when)  # fmt: skip
        session.add(item)
        session.flush()
        if decided:
            session.add(Decision(item_id=item.id, decision=title, decided_at=when))

    add(pay, "PAY-1", "issue", "Rate limit the public API", 1, decided=True)
    add(pay, "PAY-2", "issue", "Rate limit the public API per API key", 2, decided=True)  # same
    add(pay, "PAY-3", "issue", "Cap refund retries at 3", 3, decided=True)
    add(pay, "PAY-4", "issue", "Explain error E4012", 4, decided=False)
    add(secret, "#9", "pr", "Move auth to Keycloak", 5, decided=True)  # nobody may see it
    session.commit()


def test_suggestions_come_from_what_the_user_may_see(db_session: Session) -> None:
    _store(db_session)
    alice = login_as(db_session, "alice")
    link_account(db_session, "alice", "jira", "acc-alice")

    got = api.get("/chat/suggestions", headers=alice).json()

    assert got["questions"] == [
        'What did we decide about "Cap refund retries at 3"?',
        'What did we decide about "Rate limit the public API per API key"?',
        "What does PAY-4 say?",
    ]
    assert got["ticket_project"] == "PAY"
    assert "Keycloak" not in str(got)


def test_someone_who_sees_nothing_gets_no_suggestions(db_session: Session) -> None:
    _store(db_session)
    bob = login_as(db_session, "bob")
    assert api.get("/chat/suggestions", headers=bob).json() == {
        "questions": [], "ticket_project": None
    }  # fmt: skip
    assert api.get("/chat/suggestions").status_code == 401


def test_a_ticket_and_its_pr_are_one_topic() -> None:
    assert same_topic("Rate limit the public API", "Rate limit the public API per API key")
    assert same_topic("Retry failed merchant webhooks", "Retry policy for merchant webhooks")
    assert not same_topic("Upgrade payments-db to Postgres 16", "Upgrade Keycloak to 25.0.6")
