"""Task 2.1: triage training data. Task 2.2: rule pre-filter, triage step, trained classifier."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.schema import Item, Source
from app.learning import triage
from app.learning.sync import save_items
from app.models import gateway
from tests.fakes import item


def test_triage_data_has_both_labels_well_represented() -> None:
    texts, labels = triage.examples()
    assert set(labels) == {"useful", "noise"}
    assert 100 <= len(texts) <= 300
    assert all(isinstance(t, str) and t.strip() for t in texts)  # unquoted "a: b" is a dict
    assert len(set(texts)) == len(texts)  # no duplicates, so no text carries both labels
    assert min(labels.count("useful"), labels.count("noise")) >= 0.4 * len(texts)


def _item(text: str, type: str = "message", author: str = "slack:U1", **fields: object) -> Item:
    return Item(type=type, text=text, author=author, **fields)


def test_rules_catch_empty_items_and_bots_but_not_bot_threads() -> None:
    assert triage.is_obvious_noise(_item(" \n"))
    assert triage.is_obvious_noise(_item("Bump lodash", "pr", "github:dependabot[bot]"))
    assert triage.is_obvious_noise(_item("Build #12 passed", author="slack:B0CI"))
    thread = "slack:B0CI: error rate 7%\nslack:U2: root cause is a retry storm, capping retries"
    assert not triage.is_obvious_noise(_item(thread, "thread", "slack:B0CI"))
    assert not triage.is_obvious_noise(_item("", "pr", "github:alice", title="Add refunds"))
    assert not triage.is_obvious_noise(_item("thanks!"))  # left to the classifier


def test_triage_marks_noise_and_skips_it(db_session: Session) -> None:
    source = Source(kind="slack", name="#eng", external_id="C1")
    db_session.add(source)
    db_session.commit()
    decision = "We cap payment retries at 3 because the provider double-charges"
    items = [item(1, decision), item(2, "thanks!"), item(3, "Build passed", author="slack:B0CI")]
    save_items(db_session, source, items, "3")
    seen: list[str] = []

    def fake(texts: list[str]) -> list[str]:
        seen.extend(texts)
        return ["noise" if text == "thanks!" else "useful" for text in texts]

    useful = triage.triage_new_items(db_session, fake)

    assert [i.external_id for i in useful] == ["1"]
    assert seen == [decision, "thanks!"]  # the bot message never reached the classifier
    status = {i.external_id: i.status for i in db_session.scalars(select(Item))}
    assert status == {"1": "new", "2": "noise", "3": "noise"}

    seen.clear()
    triage.triage_new_items(db_session, fake)
    assert seen == [decision]  # noise is skipped from now on


def test_trained_classifier_is_accurate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway.get_settings(), "trained_models_dir", tmp_path)
    try:
        assert triage.train() >= 0.9  # on the held-out 20% of config/triage.yaml
        assert (tmp_path / "triage" / "model_head.pkl").exists()
        approval = _item("approved:", "review", "github:bob", title="PR #9 review: approved")
        outage = _item("Moving the ledger to the new cluster on Saturday, 5 min of downtime.")
        labels = triage.triage([_item("thanks a lot!"), outage, approval])
        assert labels == ["noise", "useful", "useful"]
    finally:
        gateway.load_setfit.cache_clear()  # it was loaded from tmp_path
