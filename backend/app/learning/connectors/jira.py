"""Jira Cloud connector (Task 1.3): issues, descriptions and comments of configured projects.

Incremental: the cursor is the latest `updated` timestamp seen (ISO 8601). JQL has no timezone
syntax, so the bound is rendered in the API user's Jira timezone (`/myself`).
Permissions: every item of project KEY is tagged `jira:project:KEY`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config.settings import ConfigError, get_settings
from app.db.schema import access_tag
from app.learning.connectors.base import RawItem

log = logging.getLogger("syncra.learning.jira")

PAGE_SIZE = 100
FIELDS = "summary,description,comment,created,updated,reporter,assignee,status,issuetype"


def adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format tree to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    kind = node.get("type")
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    if kind in ("mention", "emoji"):
        return node.get("attrs", {}).get("text") or node.get("attrs", {}).get("shortName", "")
    inner = "".join(adf_to_text(child) for child in node.get("content", []))
    block = kind in {
        "paragraph",
        "heading",
        "listItem",
        "codeBlock",
        "blockquote",
        "bulletList",
        "orderedList",
        "tableRow",
        "panel",
    }
    return inner + ("\n" if block and not inner.endswith("\n") else "")


def _parse(ts: str) -> datetime:
    # Jira: "2026-10-01T10:00:00.000+0200" (no colon in the offset)
    if len(ts) > 5 and ts[-5] in "+-" and ts[-3] != ":":
        ts = ts[:-2] + ":" + ts[-2:]
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


class JiraConnector:
    def __init__(
        self,
        project_key: str,
        *,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        base_url = base_url or settings.jira_base_url
        email = email or settings.jira_email
        api_token = api_token or settings.jira_api_token
        if not (base_url and email and api_token):
            raise ConfigError("JIRA_BASE_URL, JIRA_EMAIL and JIRA_API_TOKEN must be set")
        self.project_key = project_key
        self.base_url = base_url.rstrip("/")
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=httpx.BasicAuth(email, api_token),
            headers={"Accept": "application/json", "User-Agent": "syncra"},
            timeout=30,
            transport=transport,
        )

    # --- HTTP ----------------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        for _ in range(3):
            response = self._client.get(path, params=params)
            if response.status_code == 429:
                wait = min(max(float(response.headers.get("retry-after", 5)), 1.0), 900)
                log.warning("Jira rate limit hit for %s; waiting %.0fs", self.project_key, wait)
                self._sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"Jira rate limit: giving up on {path}")

    def _search(self, jql: str) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"jql": jql, "fields": FIELDS, "maxResults": PAGE_SIZE}
        while True:
            page = self._get("/rest/api/3/search/jql", params)
            yield from page.get("issues", [])
            token = page.get("nextPageToken")
            if page.get("isLast", not token) or not token:
                return
            params["nextPageToken"] = token

    def _timezone(self) -> ZoneInfo:
        name = self._get("/rest/api/3/myself", {}).get("timeZone") or "UTC"
        try:
            return ZoneInfo(name)
        except Exception:  # unknown zone name: fall back rather than fail the sync
            log.warning("unknown Jira timezone %r, using UTC", name)
            return ZoneInfo("UTC")

    # --- fetch ---------------------------------------------------------------------------

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        jql = f'project = "{self.project_key}"'
        if since_cursor:
            local = _parse(since_cursor).astimezone(self._timezone())
            jql += f' AND updated >= "{local.strftime("%Y-%m-%d %H:%M")}"'
        jql += " ORDER BY updated ASC"

        tags = (access_tag("jira", self.project_key),)
        latest = _parse(since_cursor) if since_cursor else None
        items: list[RawItem] = []
        for issue in self._search(jql):
            fields = issue.get("fields", {})
            items.append(self._issue(issue, fields, tags))
            for comment in fields.get("comment", {}).get("comments", []):
                items.append(self._comment(issue["key"], comment, tags))
            updated = _parse(fields["updated"])
            latest = updated if latest is None or updated > latest else latest
        cursor = latest.strftime("%Y-%m-%dT%H:%M:%S.%f%z") if latest else since_cursor
        return items, cursor

    def members(self) -> list[str]:
        """Everyone with the Browse Projects permission on the project."""
        params: dict[str, Any] = {
            "projectKey": self.project_key, "permissions": "BROWSE_PROJECTS",
            "maxResults": PAGE_SIZE, "startAt": 0,
        }  # fmt: skip
        accounts: list[str] = []
        while page := self._get("/rest/api/3/user/permission/search", params):
            accounts += [f"jira:{u['accountId']}" for u in page if u.get("accountId")]
            if len(page) < PAGE_SIZE:
                break
            params["startAt"] += len(page)
        return accounts

    def create_issue(self, title: str, description: str) -> dict[str, str]:
        """Create a Task in the project (Phase 8 actions): {"key", "link"} of the new ticket."""
        paragraphs = [
            {"type": "paragraph", "content": [{"type": "text", "text": part}]}
            for part in description.split("\n\n")
            if part.strip()
        ]
        fields = {
            "project": {"key": self.project_key},
            "summary": title,
            "issuetype": {"name": "Task"},
            "description": {"type": "doc", "version": 1, "content": paragraphs},
        }
        response = self._client.post("/rest/api/3/issue", json={"fields": fields})
        response.raise_for_status()
        key = response.json()["key"]
        return {"key": key, "link": f"{self.base_url}/browse/{key}"}

    # --- mapping -------------------------------------------------------------------------

    @staticmethod
    def _account(user: dict[str, Any] | None) -> str | None:
        return f"jira:{user['accountId']}" if user and user.get("accountId") else None

    def _issue(self, issue: dict[str, Any], fields: dict[str, Any], tags: tuple) -> RawItem:
        key = issue["key"]
        header = " · ".join(
            part
            for part in (
                f"Type: {fields.get('issuetype', {}).get('name')}"
                if fields.get("issuetype")
                else "",
                f"Status: {fields.get('status', {}).get('name')}" if fields.get("status") else "",
                f"Assignee: {fields['assignee'].get('displayName')}"
                if fields.get("assignee")
                else "",
            )
            if part
        )
        description = adf_to_text(fields.get("description")).strip()
        return RawItem(
            external_id=key,
            type="issue",
            title=fields.get("summary"),
            text=f"{header}\n\n{description}".strip(),
            author=self._account(fields.get("reporter")),
            created_at=_parse(fields["created"]) if fields.get("created") else None,
            updated_at=_parse(fields["updated"]) if fields.get("updated") else None,
            link=f"{self.base_url}/browse/{key}",
            access_tags=tags,
        )

    def _comment(self, key: str, comment: dict[str, Any], tags: tuple) -> RawItem:
        return RawItem(
            external_id=f"comment:{comment['id']}",
            type="comment",
            text=adf_to_text(comment.get("body")).strip(),
            author=self._account(comment.get("author")),
            created_at=_parse(comment["created"]) if comment.get("created") else None,
            updated_at=_parse(comment["updated"]) if comment.get("updated") else None,
            link=f"{self.base_url}/browse/{key}?focusedCommentId={comment['id']}",
            parent_external_id=key,
            access_tags=tags,
        )
