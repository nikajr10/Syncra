"""Task 3.1: GLiNER finds people, services, tools and projects in PR and Slack text."""

import pytest

from app.config.settings import get_models_config
from app.learning.entities import find_entities

PR = (
    "Put a RabbitMQ queue between checkout and payments\n\n"
    "Alice Chen moved the PaymentService behind RabbitMQ so provider timeouts no longer fail "
    "orders. Deployed with Terraform. Part of Project Phoenix."
)
THREAD = (
    "slack:U01: should billing-api call the ledger over gRPC or keep REST?\n"
    "slack:U02: gRPC. Maria benchmarked it and p99 dropped 40%. Kafka for the events too.\n"
    "slack:U01: ok, gRPC and Kafka then. <@U03> can you update the Grafana dashboard?"
)


def test_finds_the_expected_entities_in_a_pr_and_a_slack_thread() -> None:
    pr, thread, thanks = find_entities([PR, THREAD, "thanks!"])

    assert {
        ("Alice Chen", "person"),
        ("PaymentService", "service"),
        ("Terraform", "tool"),
        ("Project Phoenix", "project"),
    } <= {(e.name, e.type) for e in pr}
    assert {("Maria", "person"), ("Kafka", "tool")} <= {(e.name, e.type) for e in thread}
    names = [e.name for e in thread]
    assert names.count("gRPC") == 1  # mentioned three times, reported once
    assert "slack" not in {n.lower() for n in names}  # `slack:U01:` prefixes are not mentions
    assert thanks == []
    spec = get_models_config()["entity_finder"]
    assert all(e.type in spec.labels and e.score >= spec.threshold for e in pr + thread)


def test_labels_and_threshold_come_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = get_models_config()["entity_finder"]
    monkeypatch.setattr(spec, "labels", ["person"])
    monkeypatch.setattr(spec, "threshold", 0.9)  # Alice Chen scores ~0.98, the rest lower

    assert [(e.name, e.type) for e in find_entities([PR])[0]] == [("Alice Chen", "person")]
