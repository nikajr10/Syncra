"""Task 0.4: migrations run up and down on an empty database; one row in every table."""

from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import BACKEND_DIR
from app.db.engine import get_engine
from app.db.schema import (
    EMBEDDING_DIM,
    Action,
    AuthToken,
    Base,
    ChatMessage,
    ChatSession,
    Chunk,
    Decision,
    Edge,
    Entity,
    EntityAlias,
    Item,
    Source,
    SyncCursor,
    User,
    UserSourceIdentity,
)


def _public_tables() -> set[str]:
    with get_engine().connect() as conn:
        rows = conn.execute(text("select tablename from pg_tables where schemaname = 'public'"))
        return {r[0] for r in rows}


def test_migrations_run_down_and_up_cleanly(migrated_db: None) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.downgrade(cfg, "base")
    assert _public_tables() <= {"alembic_version"}
    command.upgrade(cfg, "head")
    assert set(Base.metadata.tables) <= _public_tables()


def test_insert_and_read_one_row_in_every_table(db_session: Session) -> None:
    session = db_session
    now = datetime.now(UTC)
    user = User(username="alice", display_name="Alice")
    session.add(user)
    session.flush()
    session.add(UserSourceIdentity(user_id=user.id, source_kind="github", external_id="alice"))
    session.add(AuthToken(user_id=user.id, token_hash="0" * 64, expires_at=now))

    source = Source(kind="github", name="acme/payments", external_id="acme/payments")
    session.add(source)
    session.flush()
    session.add(SyncCursor(source_id=source.id, cursor="2026-10-15T00:00:00Z"))

    item = Item(
        source_id=source.id,
        external_id="#42",
        type="pr",
        title="Add queue between checkout and payments",
        text="The payment provider times out under load, so we add a RabbitMQ queue.",
        author="github:alice",
        link="https://github.com/acme/payments/pull/42",
        created_at=now,
        access_tags=["github:repo:acme/payments"],
    )
    session.add(item)
    session.flush()

    vector = [0.0] * EMBEDDING_DIM
    vector[0] = 1.0
    session.add(Chunk(item_id=item.id, position=0, text=item.text, vector=vector))

    entity = Entity(type="service", name="payment service")
    session.add(entity)
    session.flush()
    session.add(EntityAlias(entity_id=entity.id, alias="payments-svc", source_kind="github"))
    session.add(
        Edge(
            src_type="entity",
            src_id=entity.id,
            relation="mentions",
            dst_type="item",
            dst_id=item.id,
            item_id=item.id,
        )
    )
    session.add(
        Decision(
            item_id=item.id,
            decision="Put a queue between checkout and payments",
            reason="provider timeouts under load",
            people=["alice", "bob"],
            link=item.link,
            decided_at=now,
        )
    )

    chat = ChatSession(user_id=user.id, title="payments")
    session.add(chat)
    session.flush()
    session.add(
        ChatMessage(
            session_id=chat.id,
            role="assistant",
            content="Because of provider timeouts [E1].",
            sources=[{"label": "E1", "link": item.link}],
            confidence="high",
        )
    )
    session.add(Action(user_id=user.id, session_id=chat.id, kind="create_jira_ticket"))
    session.flush()

    for model in Base.metadata.sorted_tables:
        count = session.execute(select(func.count()).select_from(model)).scalar_one()
        assert count == 1, f"expected one row in {model.name}"

    assert session.get(Item, item.id).access_tags == ["github:repo:acme/payments"]
    assert session.get(Action, 1).status == "pending"  # server default applied

    chunk = session.scalars(select(Chunk)).one()
    assert "queue" in chunk.tsv  # generated full-text column
    assert len(chunk.vector) == EMBEDDING_DIM

    # The two search indexes answer queries.
    nearest = session.scalars(
        select(Chunk).order_by(Chunk.vector.cosine_distance(vector)).limit(1)
    ).first()
    assert nearest is not None and "RabbitMQ" in nearest.text
    assert session.scalars(select(Chunk).where(Chunk.tsv.match("rabbitmq & queue"))).first()
    assert session.scalars(select(Chunk).where(Chunk.tsv.match("kubernetes"))).first() is None
