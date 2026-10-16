"""Task 5.5: intent router training data, the trained classifier and instant small-talk replies."""

import time
from pathlib import Path

import pytest

from app.chat.intent import ACTION, GOT_IT, HELP, QUESTION, SMALL_TALK, route, small_talk_reply
from app.models import gateway


def test_intent_data_has_three_labels_well_represented() -> None:
    texts, labels = gateway.setfit_examples("intent_router")
    assert set(labels) == {SMALL_TALK, QUESTION, ACTION}
    assert 150 <= len(texts) <= 400
    assert all(isinstance(t, str) and t.strip() for t in texts)  # unquoted "a: b" is a dict
    assert len(set(texts)) == len(texts)  # no duplicates, so no text carries two labels
    assert min(labels.count(label) for label in set(labels)) >= 0.25 * len(texts)


def test_small_talk_gets_a_canned_reply() -> None:
    assert small_talk_reply("hi").startswith("Hi! I'm Syncra.")
    assert small_talk_reply("Good morning!") == small_talk_reply("hi")
    assert small_talk_reply("thanks!").startswith("You're welcome!")
    assert small_talk_reply("ok thanks, bye") == small_talk_reply("thank you")  # thanks first
    assert small_talk_reply("see ya later") == "Bye! Ask me again any time."
    assert small_talk_reply("what can you do?") == small_talk_reply("help") == HELP
    assert small_talk_reply("👍") == small_talk_reply("cool") == GOT_IT


def test_route_asks_the_classifier() -> None:
    seen: list[list[str]] = []

    def fake(messages: list[str]) -> list[str]:
        seen.append(messages)
        return [ACTION]

    assert route("open a ticket for it", fake) == ACTION
    assert seen == [["open a ticket for it"]]


def test_trained_router_is_accurate_and_instant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway.get_settings(), "trained_models_dir", tmp_path)
    try:
        assert gateway.train_setfit_held_out("intent_router") >= 0.9  # held-out 20%
        messages = {
            "hi": SMALL_TALK,
            "thanks": SMALL_TALK,
            "who built the payment service?": QUESTION,
            "and who reviewed it?": QUESTION,
            "open a jira ticket to add monitoring for payments": ACTION,
        }
        assert {m: route(m) for m in messages} == messages
        started = time.perf_counter()
        assert route("thanks a lot!") == SMALL_TALK
        assert time.perf_counter() - started < 1  # the model is loaded: no search, no LLM
    finally:
        gateway.load_setfit.cache_clear()  # it was loaded from tmp_path
