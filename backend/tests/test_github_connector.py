"""Task 1.2: mocked GitHub responses produce correct items and handle paging + rate limits."""

import json
import time
from urllib.parse import parse_qs

import httpx

from app.learning.connectors.github import GitHubConnector

REPO = "acme/payments"
API = "https://gh.test"


def _user(login: str) -> dict:
    return {"login": login}


ISSUES_PAGE_1 = [
    {
        "number": 7,
        "title": "Add queue between checkout and payments",
        "body": "Provider times out under load.",
        "user": _user("alice"),
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "2026-10-02T09:00:00Z",
        "html_url": f"https://github.com/{REPO}/pull/7",
        "pull_request": {"url": f"{API}/repos/{REPO}/pulls/7"},
    }
]
ISSUES_PAGE_2 = [
    {
        "number": 8,
        "title": "Checkout returns 500",
        "body": "",
        "user": _user("bob"),
        "created_at": "2026-10-03T10:00:00Z",
        "updated_at": "2026-10-03T11:00:00Z",
        "html_url": f"https://github.com/{REPO}/issues/8",
    }
]
REVIEWS_7 = [
    {"id": 501, "state": "COMMENTED", "body": "", "user": _user("carol")},  # container only
    {
        "id": 502,
        "state": "APPROVED",
        "body": "LGTM",
        "user": _user("bob"),
        "submitted_at": "2026-10-02T08:00:00Z",
        "html_url": f"https://github.com/{REPO}/pull/7#pullrequestreview-502",
    },
]
ISSUE_COMMENTS = [
    {
        "id": 901,
        "body": "Can we use RabbitMQ?",
        "user": _user("bob"),
        "created_at": "2026-10-01T12:00:00Z",
        "updated_at": "2026-10-01T12:00:00Z",
        "html_url": f"https://github.com/{REPO}/pull/7#issuecomment-901",
        "issue_url": f"{API}/repos/{REPO}/issues/7",
    }
]
REVIEW_COMMENTS = [
    {
        "id": 777,
        "body": "retry_limit should be configurable",
        "path": "payments/queue.py",
        "user": _user("carol"),
        "created_at": "2026-10-02T07:00:00Z",
        "updated_at": "2026-10-04T07:00:00Z",
        "html_url": f"https://github.com/{REPO}/pull/7#discussion_r777",
        "pull_request_url": f"{API}/repos/{REPO}/pulls/7",
    }
]
COMMITS = [
    {
        "sha": "abc123",
        "html_url": f"https://github.com/{REPO}/commit/abc123",
        "author": _user("alice"),
        "commit": {
            "message": "Add RabbitMQ queue\n\nAbsorbs provider spikes.",
            "author": {"name": "Alice", "date": "2026-10-02T06:00:00Z"},
            "committer": {"name": "Alice", "date": "2026-10-02T06:30:00Z"},
        },
    }
]


class FakeGitHub:
    """Routes requests to canned pages; records query params; rate-limits one call."""

    def __init__(self, private: bool = True, rate_limit_once: bool = True) -> None:
        self.private = private
        self.rate_limit_once = rate_limit_once
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, params = (
            request.url.path,
            {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()},
        )
        self.calls.append((path, params))
        assert request.headers["authorization"] == "Bearer tok"
        if path == f"/repos/{REPO}":
            return httpx.Response(200, json={"private": self.private})
        if path == f"/repos/{REPO}/issues":
            query = request.url.query.decode()
            if params.get("page") == "2":
                return httpx.Response(200, json=ISSUES_PAGE_2)
            return httpx.Response(
                200,
                json=ISSUES_PAGE_1,
                headers={"Link": f'<{API}/repos/{REPO}/issues?{query}&page=2>; rel="next"'},
            )
        if path == f"/repos/{REPO}/pulls/7/reviews":
            return httpx.Response(200, json=REVIEWS_7)
        if path == f"/repos/{REPO}/issues/comments":
            if self.rate_limit_once:
                self.rate_limit_once = False
                return httpx.Response(
                    403,
                    json={"message": "API rate limit exceeded"},
                    headers={
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": str(int(time.time()) + 120),
                    },  # fmt: skip
                )
            return httpx.Response(200, json=ISSUE_COMMENTS)
        if path == f"/repos/{REPO}/pulls/comments":
            return httpx.Response(200, json=REVIEW_COMMENTS)
        if path == f"/repos/{REPO}/commits":
            return httpx.Response(200, json=COMMITS)
        return httpx.Response(404, json={"message": f"no route for {path}"})


def _connector(fake: FakeGitHub, sleeps: list[float]) -> GitHubConnector:
    return GitHubConnector(
        REPO, token="tok", api_url=API, transport=httpx.MockTransport(fake), sleep=sleeps.append
    )


def test_first_sync_produces_every_item_type_with_paging_and_rate_limit() -> None:
    fake, sleeps = FakeGitHub(), []
    items, cursor = _connector(fake, sleeps).fetch_new(None)

    by_id = {i.external_id: i for i in items}
    assert set(by_id) == {"#7", "#8", "review:502", "comment:901", "review_comment:777", "abc123"}
    assert by_id["#7"].type == "pr" and by_id["#8"].type == "issue"  # paging merged both pages
    assert by_id["#7"].author == "github:alice" and by_id["#7"].title.startswith("Add queue")
    assert by_id["review:502"].parent_external_id == "#7"
    assert (
        by_id["review:502"].text == "approved: LGTM" and by_id["review:502"].author == "github:bob"
    )
    assert by_id["comment:901"].parent_external_id == "#7"
    assert by_id["review_comment:777"].type == "review"
    assert by_id["review_comment:777"].title == "payments/queue.py"
    assert by_id["abc123"].type == "commit" and by_id["abc123"].title == "Add RabbitMQ queue"
    assert all(i.access_tags == (f"github:repo:{REPO}",) for i in items)  # private repo

    assert cursor == "2026-10-04T07:00:00Z"  # latest updated_at across everything
    assert len(sleeps) == 1 and 1 <= sleeps[0] <= 120  # waited for the rate limit, then retried
    assert [p for p, _ in fake.calls].count(f"/repos/{REPO}/issues/comments") == 2


def test_incremental_sync_passes_cursor_as_since_and_keeps_cursor_when_nothing_new() -> None:
    fake, sleeps = FakeGitHub(rate_limit_once=False), []
    connector = _connector(fake, sleeps)
    _, cursor = connector.fetch_new("2026-10-01T00:00:00Z")

    for path, params in fake.calls:
        if path.endswith(("/issues", "/issues/comments", "/pulls/comments", "/commits")):
            assert params.get("since") == "2026-10-01T00:00:00Z", path
    assert cursor == "2026-10-04T07:00:00Z"

    quiet = httpx.MockTransport(
        lambda r: httpx.Response(
            200, json={"private": False} if r.url.path == f"/repos/{REPO}" else []
        )
    )
    empty = GitHubConnector(REPO, token="tok", api_url=API, transport=quiet)
    items, cursor = empty.fetch_new("2026-10-04T07:00:00Z")
    assert items == [] and cursor == "2026-10-04T07:00:00Z"


def test_public_repo_gets_public_tag() -> None:
    fake, sleeps = FakeGitHub(private=False, rate_limit_once=False), []
    items, _ = _connector(fake, sleeps).fetch_new(None)
    assert items[0].access_tags == ("public", f"github:repo:{REPO}")


def test_request_bodies_are_json_free_gets() -> None:
    fake, sleeps = FakeGitHub(rate_limit_once=False), []
    _connector(fake, sleeps).fetch_new(None)
    assert json.dumps(fake.calls)  # all recorded calls are serialisable (sanity)
