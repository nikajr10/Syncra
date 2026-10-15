"""Entity linking (Task 4.1): one entity per real thing, however it is written (names + SBERT).

Names are normalised first: camelCase and separators split, lower case, `svc` -> service, plural
`s` dropped. `PaymentService`, `payment-service` and `payments-svc` all get the key
`paymentservice`. Names whose keys still differ are compared with SBERT (`entity_linker`); at least
its `threshold` similar and with the same numbers (`billing v1` is not `billing v2`), they are one
entity. Services, tools and projects link across those types, because GLiNER mixes them up. People
link only to people, by exact name or by account. Every name an entity was found under is kept as
an alias.

People's accounts (`github:alice`, `slack:U01`, `jira:<accountId>`) are aliases of person entities
too. `link_identities` merges the accounts each Syncra user linked (`user_source_identities`) into
one person, with their display names as aliases.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

import numpy as np
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config.settings import get_models_config
from app.db.schema import Entity, EntityAlias, UserSourceIdentity
from app.learning.entities import PERSON, FoundEntity
from app.models import gateway

ACCOUNT = re.compile(r"(github|jira|slack):\S+")  # item authors, decision people, Slack mentions
ABBREVIATIONS = {"svc": "service", "k8s": "kubernetes", "db": "database"}
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")  # PaymentService, HTTPServer
WORD = re.compile(r"[a-z0-9+#]+")  # keeps C++ and C# apart
DIGITS = re.compile(r"\d+")

_vectors: dict[str, np.ndarray] = {}  # SBERT vector per name, kept for the process


def words(name: str) -> list[str]:
    """`payments-svc` -> [payments, service]; `PaymentService` -> [payment, service]."""
    return [ABBREVIATIONS.get(w, w) for w in WORD.findall(CAMEL.sub(" ", name).lower())]


def _singular(word: str) -> str:
    plural = len(word) > 3 and word[-1] == "s" and word[-2:] not in ("ss", "us", "is")
    return word[:-1] if plural else word


def key(name: str) -> str:
    """What every name of one thing shares: `PaymentService`, `payments-svc` -> `paymentservice`."""
    return "".join(_singular(w) for w in words(name))


def keys_in(text: str, longest: int = 6) -> set[str]:
    """The key of every run of up to `longest` words in `text`: the names it may mention."""
    w = [_singular(word) for word in words(text)]
    return {
        "".join(w[i:j]) for i in range(len(w)) for j in range(i + 1, min(i + longest, len(w)) + 1)
    }


def link_entities(session: Session, found: Iterable[FoundEntity]) -> dict[tuple[str, str], int]:
    """The entity id of every found (name, type): new names become entities or aliases."""
    by_key, things = _name_aliases(session)
    linked: dict[tuple[str, str], int] = {}
    for entity in found:
        is_person = entity.type == PERSON
        if (entity.name, entity.type) in linked or not key(entity.name):
            continue
        if is_person and ACCOUNT.fullmatch(entity.name):
            linked[entity.name, entity.type] = link_people(session, [entity.name])[entity.name]
            continue
        spoken = " ".join(words(entity.name))
        entity_id = by_key.get((is_person, key(entity.name)))
        if entity_id is None and not is_person:  # people's names are too alike for SBERT
            entity_id = _similar(spoken, things)
        if entity_id is None:
            entity_id = _new_entity(session, entity.type, entity.name)
        _add_alias(session, entity_id, entity.name)
        by_key.setdefault((is_person, key(entity.name)), entity_id)
        if not is_person:
            things.append((spoken, entity_id))
        linked[entity.name, entity.type] = entity_id
    return linked


def link_people(session: Session, accounts: Iterable[str]) -> dict[str, int]:
    """The person entity of each account (`github:alice`, `slack:U01`, …); new accounts get one."""
    accounts = list(dict.fromkeys(accounts))
    people = dict(
        session.execute(
            select(EntityAlias.alias, EntityAlias.entity_id)
            .join(Entity, Entity.id == EntityAlias.entity_id)
            .where(EntityAlias.alias.in_(accounts), Entity.type == PERSON)
        ).all()
    )
    for account in accounts:
        if account not in people:
            people[account] = _new_entity(session, PERSON, account)
            _add_alias(session, people[account], account, account.split(":", 1)[0])
    return people


def link_identities(session: Session) -> None:
    """One person per Syncra user: merge the person entities of the accounts they linked, and of
    people known only by their display name. Every account and display name stays an alias."""
    by_user = defaultdict(list)
    for identity in session.scalars(select(UserSourceIdentity).order_by(UserSourceIdentity.id)):
        by_user[identity.user_id].append(identity)
    for identities in by_user.values():
        accounts = {f"{i.source_kind}:{i.external_id}": i.source_kind for i in identities}
        names = {i.display_name for i in identities if i.display_name}
        ids = set(
            session.scalars(
                select(EntityAlias.entity_id).where(EntityAlias.alias.in_(list(accounts)))
            )
        )
        if not ids:
            continue  # none of their accounts has shown up yet
        name_keys = {key(name) for name in names}
        ids |= {eid for eid, alias in _name_only_people(session) if key(alias) in name_keys}
        keep, *others = sorted(ids)
        for other in others:
            _merge(session, keep, other)
        if others:
            session.expire_all()  # the merge rewrote rows behind the ORM's back
        for account, kind in accounts.items():
            _add_alias(session, keep, account, kind)
        for name in names:
            _add_alias(session, keep, name)


# --- helpers ---------------------------------------------------------------------------------


def _name_aliases(session: Session) -> tuple[dict[tuple[bool, str], int], list[tuple[str, int]]]:
    """({(is person, key): entity id}, [(spoken name, entity id) of services, tools, projects])."""
    # ponytail: every name alias is loaded per call; store keys + SBERT vectors in entity_aliases
    # if entities reach the tens of thousands.
    rows = session.execute(
        select(EntityAlias.alias, EntityAlias.entity_id, Entity.type)
        .join(Entity, Entity.id == EntityAlias.entity_id)
        .where(EntityAlias.source_kind.is_(None))  # names, not accounts
        .order_by(EntityAlias.entity_id)
    ).all()
    by_key: dict[tuple[bool, str], int] = {}
    things = []
    for alias, entity_id, type_ in rows:
        by_key.setdefault((type_ == PERSON, key(alias)), entity_id)  # same name twice: oldest
        if type_ != PERSON:
            things.append((" ".join(words(alias)), entity_id))
    return by_key, things


def _similar(name: str, candidates: list[tuple[str, int]]) -> int | None:
    """The entity of the candidate most like `name` (SBERT): if alike enough, with equal numbers."""
    digits = DIGITS.findall(name)
    candidates = [(c, eid) for c, eid in candidates if DIGITS.findall(c) == digits]
    if not candidates:
        return None
    new = [n for n in dict.fromkeys([name, *(c for c, _ in candidates)]) if n not in _vectors]
    if new:
        _vectors.update(zip(new, np.asarray(gateway.embed("entity_linker", new)), strict=True))
    scores = np.stack([_vectors[c] for c, _ in candidates]) @ _vectors[name]  # cosine: normalised
    best = int(scores.argmax())
    threshold = get_models_config()["entity_linker"].threshold
    return candidates[best][1] if scores[best] >= threshold else None


def _new_entity(session: Session, type_: str, name: str) -> int:
    entity = Entity(type=type_, name=name)
    session.add(entity)
    session.flush()
    return entity.id


def _add_alias(
    session: Session, entity_id: int, alias: str, source_kind: str | None = None
) -> None:
    session.execute(
        insert(EntityAlias)
        .values(entity_id=entity_id, alias=alias, source_kind=source_kind)
        .on_conflict_do_nothing()
    )


def _name_only_people(session: Session) -> list[tuple[int, str]]:
    """(entity id, alias) of the people no account is linked to yet."""
    with_account = select(EntityAlias.entity_id).where(EntityAlias.source_kind.is_not(None))
    return session.execute(
        select(EntityAlias.entity_id, EntityAlias.alias)
        .join(Entity, Entity.id == EntityAlias.entity_id)
        .where(Entity.type == PERSON, EntityAlias.entity_id.not_in(with_account))
    ).all()


def _merge(session: Session, keep: int, drop: int) -> None:
    """Give `drop`'s aliases and links to `keep`, then delete `drop`."""
    ids = {"keep": keep, "drop": drop}
    session.execute(
        text(
            "UPDATE entity_aliases a SET entity_id = :keep WHERE entity_id = :drop AND NOT EXISTS "
            "(SELECT 1 FROM entity_aliases b WHERE b.entity_id = :keep AND b.alias = a.alias)"
        ),
        ids,
    )
    for end, other in (("src", "dst"), ("dst", "src")):  # links keep already has are dropped
        session.execute(
            text(
                f"UPDATE edges e SET {end}_id = :keep WHERE {end}_type = 'entity' "
                f"AND {end}_id = :drop AND NOT EXISTS (SELECT 1 FROM edges f "
                f"WHERE f.{end}_type = 'entity' AND f.{end}_id = :keep AND f.relation = e.relation "
                f"AND f.{other}_type = e.{other}_type AND f.{other}_id = e.{other}_id)"
            ),
            ids,
        )
    session.execute(
        text(
            "DELETE FROM edges WHERE (src_type = 'entity' AND src_id = :drop) "
            "OR (dst_type = 'entity' AND dst_id = :drop)"
        ),
        ids,
    )
    session.execute(delete(Entity).where(Entity.id == drop))  # its leftover aliases go with it
