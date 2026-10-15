"""Task 4.1: one entity per thing however it is written; different things stay apart; people's
accounts are linked through the identities Syncra users linked."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.schema import Edge, Entity, EntityAlias, User, UserSourceIdentity
from app.learning.entities import FoundEntity, find_entities
from app.learning.link import key, link_entities, link_identities, link_people


def _services(*names: str) -> list[FoundEntity]:
    return [FoundEntity(name, "service", 0.9) for name in names]


def _aliases(session: Session, entity_id: int) -> set[str]:
    query = select(EntityAlias.alias).where(EntityAlias.entity_id == entity_id)
    return set(session.scalars(query))


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_names_are_normalised_to_one_key() -> None:
    assert key("payments-svc") == key("payment service") == key("PaymentService")
    assert key("gRPC") == key("grpc") and key("Node.js") == key("NodeJS")
    assert key("C++") != key("C#") and key("billing-v1") != key("billing-v2")


def test_three_names_for_one_service_become_one_entity(db_session: Session) -> None:
    linked = link_entities(
        db_session, _services("payments-svc", "payment service", "PaymentService")
    )

    [entity_id] = set(linked.values())
    assert _aliases(db_session, entity_id) == {"payments-svc", "payment service", "PaymentService"}

    # Later runs find it again: by its normalised name, or by meaning (SBERT, 0.92 similar).
    again = link_entities(db_session, _services("Payment-Service", "payment processing service"))
    assert set(again.values()) == {entity_id}
    assert _count(db_session, Entity) == 1


def test_different_services_stay_separate(db_session: Session) -> None:
    # SBERT scores payment vs billing service 0.79, billing v1 vs v2 0.90 (kept apart by numbers).
    names = (
        "payment service",
        "billing service",
        "notification service",
        "billing-v1",
        "billing-v2",
    )
    assert len(set(link_entities(db_session, _services(*names)).values())) == len(names)


def test_services_and_tools_link_across_types_but_never_to_people(db_session: Session) -> None:
    linked = link_entities(
        db_session,
        [
            FoundEntity("RabbitMQ", "tool", 0.9),
            FoundEntity("rabbitmq", "service", 0.8),  # GLiNER mixes the two up
            FoundEntity("Jordan", "project", 0.7),
            FoundEntity("Jordan", "person", 0.9),
        ],
    )

    assert linked["RabbitMQ", "tool"] == linked["rabbitmq", "service"]
    assert db_session.get(Entity, linked["rabbitmq", "service"]).type == "tool"  # first seen
    assert linked["Jordan", "project"] != linked["Jordan", "person"]


def test_peoples_accounts_are_merged_through_their_identities(db_session: Session) -> None:
    people = link_people(db_session, ["github:alice", "slack:U01", "github:bob"])
    assert len(set(people.values())) == 3  # nothing says who is who yet
    [name_only] = link_entities(db_session, [FoundEntity("Alice Chen", "person", 0.9)]).values()
    link = Edge(
        src_type="entity",
        src_id=people["slack:U01"],
        relation="authored",
        dst_type="item",
        dst_id=7,
    )
    db_session.add(link)
    alice = User(username="alice")
    db_session.add(alice)
    db_session.flush()
    db_session.add_all(
        UserSourceIdentity(user_id=alice.id, source_kind=kind, external_id=account, display_name=n)
        for kind, account, n in [
            ("github", "alice", None),
            ("slack", "U01", "Alice Chen"),
            ("jira", "5b10ac8d", "Alice Chen"),  # hasn't written anything yet
        ]
    )

    link_identities(db_session)

    person = people["github:alice"]
    assert _aliases(db_session, person) == {
        "github:alice",
        "slack:U01",
        "jira:5b10ac8d",
        "Alice Chen",
    }
    assert db_session.get(Entity, name_only) is None  # merged into her
    assert link.src_id == person  # her links moved with her (and the session saw it)
    assert set(link_people(db_session, ["slack:U01", "jira:5b10ac8d"]).values()) == {person}
    assert link_entities(db_session, [FoundEntity("alice chen", "person", 0.9)]) == {
        ("alice chen", "person"): person
    }
    assert people["github:bob"] != person
    assert _count(db_session, Entity) == 2


def test_slack_mentions_are_people_found_by_account(db_session: Session) -> None:
    [found] = find_entities(["slack:U01: <@U03> can you update the Grafana dashboard?"])
    assert FoundEntity("slack:U03", "person", 1.0) in found

    linked = link_entities(db_session, found)
    assert linked["slack:U03", "person"] == link_people(db_session, ["slack:U03"])["slack:U03"]
