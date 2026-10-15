"""Task 1.3: mocked Jira responses produce correct items and handle paging."""

from urllib.parse import parse_qs

import httpx

from app.learning.connectors.jira import JiraConnector, adf_to_text

BASE = "https://acme.atlassian.test"


def _adf(*paragraphs: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs
        ],
    }


def _issue(key: str, summary: str, updated: str, comments: list[dict] | None = None) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": _adf("Provider times out under load.", "We need a queue."),
            "issuetype": {"name": "Story"},
            "status": {"name": "Done"},
            "assignee": {"accountId": "a1", "displayName": "Alice"},
            "reporter": {"accountId": "b2", "displayName": "Bob"},
            "created": "2026-10-01T10:00:00.000+0200",
            "updated": updated,
            "comment": {"comments": comments or []},
        },
    }


COMMENT = {
    "id": "31",
    "author": {"accountId": "c3", "displayName": "Carol"},
    "body": _adf("Use RabbitMQ, retry_limit = 3"),
    "created": "2026-10-02T09:00:00.000+0200",
    "updated": "2026-10-02T09:30:00.000+0200",
}
PAGE_1 = [_issue("PAY-1", "Add queue to payments", "2026-10-02T12:00:00.000+0200", [COMMENT])]
PAGE_2 = [_issue("PAY-2", "Checkout 500s", "2026-10-03T08:00:00.000+0200")]


class FakeJira:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.rate_limited = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        self.calls.append((request.url.path, params))
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path == "/rest/api/3/myself":
            return httpx.Response(200, json={"timeZone": "Europe/Berlin"})
        if request.url.path == "/rest/api/3/search/jql":
            if not self.rate_limited:
                self.rate_limited = True
                return httpx.Response(429, headers={"retry-after": "7"})
            if params.get("nextPageToken") == "t2":
                return httpx.Response(200, json={"issues": PAGE_2, "isLast": True})
            return httpx.Response(
                200, json={"issues": PAGE_1, "isLast": False, "nextPageToken": "t2"}
            )
        return httpx.Response(404)


def _connector(fake: FakeJira, sleeps: list[float]) -> JiraConnector:
    return JiraConnector(
        "PAY",
        base_url=BASE,
        email="me@acme.test",
        api_token="tok",
        transport=httpx.MockTransport(fake),
        sleep=sleeps.append,
    )


def test_adf_is_flattened_to_text() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Plan"}]},
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "ask "},
                                    {"type": "mention", "attrs": {"text": "@Bob"}},
                                ],
                            }
                        ],
                    }
                ],
            },
            {"type": "codeBlock", "content": [{"type": "text", "text": "retry_limit = 3"}]},
        ],
    }
    assert adf_to_text(doc) == "Plan\nask @Bob\nretry_limit = 3\n"
    assert adf_to_text(None) == ""


def test_first_sync_pages_through_results_and_maps_issues_and_comments() -> None:
    fake, sleeps = FakeJira(), []
    items, cursor = _connector(fake, sleeps).fetch_new(None)

    by_id = {i.external_id: i for i in items}
    assert set(by_id) == {"PAY-1", "comment:31", "PAY-2"}
    issue = by_id["PAY-1"]
    assert issue.type == "issue" and issue.title == "Add queue to payments"
    assert issue.text.startswith("Type: Story · Status: Done · Assignee: Alice")
    assert "We need a queue." in issue.text
    assert issue.author == "jira:b2" and issue.link == f"{BASE}/browse/PAY-1"
    assert issue.access_tags == ("jira:project:PAY",)
    comment = by_id["comment:31"]
    assert comment.type == "comment" and comment.parent_external_id == "PAY-1"
    assert comment.text == "Use RabbitMQ, retry_limit = 3" and comment.author == "jira:c3"

    assert cursor == "2026-10-03T06:00:00.000000+0000"  # latest `updated`, in UTC
    assert sleeps == [7.0]  # 429 honoured once, then retried
    searches = [p for path, p in fake.calls if path.endswith("/search/jql")]
    assert searches[0]["jql"] == 'project = "PAY" ORDER BY updated ASC'
    assert searches[-1]["nextPageToken"] == "t2"


def test_incremental_sync_renders_cursor_in_the_users_timezone() -> None:
    fake, sleeps = FakeJira(), []
    fake.rate_limited = True
    _, cursor = _connector(fake, sleeps).fetch_new("2026-10-03T06:00:00.000000+0000")

    jql = next(p["jql"] for path, p in fake.calls if path.endswith("/search/jql"))
    assert jql == 'project = "PAY" AND updated >= "2026-10-03 08:00" ORDER BY updated ASC'
    assert cursor == "2026-10-03T06:00:00.000000+0000"  # nothing newer than the cursor

    quiet = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={"timeZone": "UTC"} if "myself" in r.url.path else {"issues": [], "isLast": True},
        )
    )
    empty = JiraConnector("PAY", base_url=BASE, email="e", api_token="t", transport=quiet)
    items, cursor = empty.fetch_new("2026-10-03T06:00:00.000000+0000")
    assert items == [] and cursor == "2026-10-03T06:00:00.000000+0000"
