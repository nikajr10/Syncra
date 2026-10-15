"""GitHub connector (Task 1.2): issues, PRs, their comments, PR reviews, review comments, commits.

Incremental: the cursor is the latest `updated_at` seen (ISO 8601), passed back as `since`.
Permissions: a private repo is tagged `github:repo:<owner/repo>`; a public one also gets `public`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config.settings import ConfigError, get_settings
from app.learning.connectors.base import RawItem

log = logging.getLogger("syncra.learning.github")

PER_PAGE = 100
MAX_RATE_LIMIT_WAIT = 15 * 60  # seconds; longer than this and we give up until the next run


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


def _fmt(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class GitHubConnector:
    def __init__(
        self,
        repo: str,
        *,
        token: str | None = None,
        api_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        token = token or settings.github_token
        if not token:
            raise ConfigError("GITHUB_TOKEN is not set")
        self.repo = repo
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=api_url or settings.github_api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "syncra",
            },
            timeout=30,
            transport=transport,
        )

    # --- HTTP ----------------------------------------------------------------------------

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for _ in range(3):
            response = self._client.get(url, params=params)
            limited = response.status_code in (403, 429) and (
                response.headers.get("x-ratelimit-remaining") == "0"
                or "retry-after" in response.headers
            )
            if not limited:
                response.raise_for_status()
                return response
            wait = float(response.headers.get("retry-after", 0)) or (
                float(response.headers.get("x-ratelimit-reset", 0)) - time.time()
            )
            wait = min(max(wait, 1.0), MAX_RATE_LIMIT_WAIT)
            log.warning("GitHub rate limit hit for %s; waiting %.0fs", self.repo, wait)
            self._sleep(wait)
        raise RuntimeError(f"GitHub rate limit: giving up on {url}")

    def _paged(self, url: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        params = {"per_page": PER_PAGE, **(params or {})}
        next_url: str | None = url
        while next_url:
            response = self._get(next_url, params=params)
            yield from response.json()
            next_url = response.links.get("next", {}).get("url")
            params = None  # the Link URL already carries page + filters

    # --- fetch ---------------------------------------------------------------------------

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        tags = self._access_tags()
        since = {"since": since_cursor} if since_cursor else {}
        latest = _parse(since_cursor) if since_cursor else None
        items: list[RawItem] = []

        def seen(ts: str) -> None:
            nonlocal latest
            parsed = _parse(ts)
            latest = parsed if latest is None or parsed > latest else latest

        updated = {"sort": "updated", "direction": "asc", **since}
        for issue in self._paged(f"/repos/{self.repo}/issues", {"state": "all", **updated}):
            items.append(self._issue(issue, tags))
            seen(issue["updated_at"])
            if "pull_request" in issue:
                number = issue["number"]
                for review in self._paged(f"/repos/{self.repo}/pulls/{number}/reviews"):
                    if review.get("body") or review.get("state") in (
                        "APPROVED",
                        "CHANGES_REQUESTED",
                    ):
                        items.append(self._review(review, number, tags))

        for comment in self._paged(f"/repos/{self.repo}/issues/comments", updated):
            items.append(self._comment(comment, "comment", "comment", "issue_url", tags))
            seen(comment["updated_at"])

        for comment in self._paged(f"/repos/{self.repo}/pulls/comments", updated):
            items.append(
                self._comment(comment, "review", "review_comment", "pull_request_url", tags)
            )
            seen(comment["updated_at"])

        for commit in self._paged(f"/repos/{self.repo}/commits", since):
            items.append(self._commit(commit, tags))
            seen(commit["commit"]["committer"]["date"])

        return items, (_fmt(latest) if latest else since_cursor)

    # --- mapping -------------------------------------------------------------------------

    def _access_tags(self) -> tuple[str, ...]:
        repo = self._get(f"/repos/{self.repo}").json()
        tag = f"github:repo:{self.repo}"
        return (tag,) if repo.get("private", True) else ("public", tag)

    @staticmethod
    def _login(user: dict[str, Any] | None) -> str | None:
        return f"github:{user['login']}" if user and user.get("login") else None

    def _issue(self, issue: dict[str, Any], tags: tuple[str, ...]) -> RawItem:
        return RawItem(
            external_id=f"#{issue['number']}",
            type="pr" if "pull_request" in issue else "issue",
            title=issue.get("title"),
            text=issue.get("body") or "",
            author=self._login(issue.get("user")),
            created_at=_parse(issue["created_at"]),
            updated_at=_parse(issue["updated_at"]),
            link=issue.get("html_url"),
            access_tags=tags,
        )

    def _review(self, review: dict[str, Any], number: int, tags: tuple[str, ...]) -> RawItem:
        state = (review.get("state") or "commented").lower().replace("_", " ")
        body = review.get("body") or ""
        submitted = review.get("submitted_at")
        return RawItem(
            external_id=f"review:{review['id']}",
            type="review",
            title=f"PR #{number} review: {state}",
            text=f"{state}: {body}".strip(),
            author=self._login(review.get("user")),
            created_at=_parse(submitted) if submitted else None,
            updated_at=_parse(submitted) if submitted else None,
            link=review.get("html_url"),
            parent_external_id=f"#{number}",
            access_tags=tags,
        )

    def _comment(
        self,
        comment: dict[str, Any],
        item_type: str,
        prefix: str,
        parent_url_key: str,
        tags: tuple[str, ...],
    ) -> RawItem:
        number = comment[parent_url_key].rstrip("/").rsplit("/", 1)[-1]
        return RawItem(
            external_id=f"{prefix}:{comment['id']}",
            type=item_type,  # type: ignore[arg-type]
            title=comment.get("path"),  # review comments carry the file path
            text=comment.get("body") or "",
            author=self._login(comment.get("user")),
            created_at=_parse(comment["created_at"]),
            updated_at=_parse(comment["updated_at"]),
            link=comment.get("html_url"),
            parent_external_id=f"#{number}",
            access_tags=tags,
        )

    def _commit(self, commit: dict[str, Any], tags: tuple[str, ...]) -> RawItem:
        message = commit["commit"].get("message") or ""
        when = _parse(commit["commit"]["committer"]["date"])
        author = self._login(commit.get("author")) or (
            f"github:{commit['commit']['author']['name']}"
            if commit["commit"].get("author", {}).get("name")
            else None
        )
        return RawItem(
            external_id=commit["sha"],
            type="commit",
            title=message.splitlines()[0] if message else None,
            text=message,
            author=author,
            created_at=when,
            updated_at=when,
            link=commit.get("html_url"),
            access_tags=tags,
        )
