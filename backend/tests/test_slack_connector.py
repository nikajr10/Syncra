"""Task 1.4: mocked Slack responses give one item per thread with replies in order; DMs skipped."""

from urllib.parse import parse_qs

import httpx

from app.learning.connectors.slack import SlackConnector

API = "https://slack.test/api"
WS = "https://acme.slack.com"
DAY = 86400.0
T0 = 1_760_000_000.0  # some Unix time

PARENT_TS = f"{T0 + 100:.6f}"
REPLY_1_TS = f"{T0 + 200:.6f}"
REPLY_2_TS = f"{T0 + 300:.6f}"
LONE_TS = f"{T0 + 400:.6f}"
JOIN_TS = f"{T0 + 500:.6f}"

HISTORY_PAGE_1 = [  # Slack returns newest first
    {"type": "message", "subtype": "channel_join", "user": "U9", "text": "joined", "ts": JOIN_TS},
    {"type": "message", "user": "U2", "text": "Deploy done, retry_limit=3", "ts": LONE_TS},
]
HISTORY_PAGE_2 = [
    {
        "type": "message",
        "user": "U1",
        "text": "Should we add a queue to payments?\nProvider keeps timing out.",
        "ts": PARENT_TS,
        "thread_ts": PARENT_TS,
        "reply_count": 2,
        "latest_reply": REPLY_2_TS,
    },
]
REPLIES = [
    HISTORY_PAGE_2[0],
    {
        "type": "message",
        "user": "U2",
        "text": "Yes, RabbitMQ",
        "ts": REPLY_1_TS,
        "thread_ts": PARENT_TS,
    },
    {
        "type": "message",
        "user": "U1",
        "text": "Agreed, doing it",
        "ts": REPLY_2_TS,
        "thread_ts": PARENT_TS,
    },
]


class FakeSlack:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.rate_limit_once = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        params = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        self.calls.append((method, params))
        assert request.headers["authorization"] == "Bearer xoxb-test"
        if method == "conversations.info":
            is_dm = params["channel"].startswith("D")
            return httpx.Response(
                200, json={"ok": True, "channel": {"id": params["channel"], "is_im": is_dm}}
            )
        if method == "conversations.history":
            if self.rate_limit_once:
                self.rate_limit_once = False
                return httpx.Response(429, headers={"retry-after": "3"})
            if params.get("cursor") == "page2":
                return httpx.Response(200, json={"ok": True, "messages": HISTORY_PAGE_2})
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "messages": HISTORY_PAGE_1,
                    "response_metadata": {"next_cursor": "page2"},
                },
            )
        if method == "conversations.replies":
            assert params["ts"] == PARENT_TS
            return httpx.Response(200, json={"ok": True, "messages": REPLIES})
        return httpx.Response(200, json={"ok": False, "error": f"unknown_method {method}"})


def _connector(fake: FakeSlack, sleeps: list[float], channel: str = "C1") -> SlackConnector:
    return SlackConnector(
        channel,
        token="xoxb-test",
        workspace_url=WS,
        api_url=API,
        lookback_days=7,
        transport=httpx.MockTransport(fake),
        sleep=sleeps.append,
    )


def test_first_sync_gives_one_item_per_thread_with_replies_in_order() -> None:
    fake, sleeps = FakeSlack(), []
    items, cursor = _connector(fake, sleeps).fetch_new(None)

    by_id = {i.external_id: i for i in items}
    assert set(by_id) == {PARENT_TS, LONE_TS}  # channel_join skipped, both pages read
    thread = by_id[PARENT_TS]
    assert thread.type == "thread" and thread.author == "slack:U1"
    assert thread.title == "Should we add a queue to payments?"
    assert thread.text.splitlines() == [
        "slack:U1: Should we add a queue to payments?",
        "Provider keeps timing out.",
        "slack:U2: Yes, RabbitMQ",
        "slack:U1: Agreed, doing it",
    ]
    assert thread.link == f"{WS}/archives/C1/p{PARENT_TS.replace('.', '')}"
    assert thread.access_tags == ("slack:channel:C1",)
    assert thread.updated_at.timestamp() == float(REPLY_2_TS)
    assert by_id[LONE_TS].type == "message" and by_id[LONE_TS].author == "slack:U2"

    assert cursor == JOIN_TS  # latest ts seen in the channel
    assert sleeps == [3.0]


def test_incremental_sync_looks_back_for_new_replies_and_skips_stored_messages() -> None:
    fake, sleeps = FakeSlack(), []
    fake.rate_limit_once = False
    since = f"{T0 + 250:.6f}"  # after reply 1, before reply 2 and the lone message
    items, cursor = _connector(fake, sleeps).fetch_new(since)

    history = next(p for m, p in fake.calls if m == "conversations.history")
    assert float(history["oldest"]) == float(since) - 7 * DAY
    ids = {i.external_id for i in items}
    assert ids == {PARENT_TS, LONE_TS}  # thread re-emitted (new reply), lone message is new
    assert cursor == JOIN_TS

    fake.calls.clear()
    items, cursor = _connector(fake, sleeps).fetch_new(JOIN_TS)
    assert items == [] and cursor == JOIN_TS  # nothing newer: old thread not re-read
    assert not [m for m, _ in fake.calls if m == "conversations.replies"]


def test_direct_messages_are_skipped() -> None:
    fake, sleeps = FakeSlack(), []
    items, cursor = _connector(fake, sleeps, channel="D42").fetch_new("1.000000")
    assert items == [] and cursor == "1.000000"
    assert [m for m, _ in fake.calls] == ["conversations.info"]
