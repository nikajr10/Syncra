"""Slack connector (Task 1.4): messages and whole threads from a channel. DMs are skipped.

Incremental: the cursor is the latest message / reply `ts` seen. Each run re-reads the last
`SLACK_THREAD_LOOKBACK_DAYS` so replies added to older threads are picked up (the upsert
updates the stored thread). Permissions: everything is tagged `slack:channel:<ID>`
(channel membership).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config.settings import ConfigError, get_settings
from app.db.schema import access_tag
from app.learning.connectors.base import RawItem

log = logging.getLogger("syncra.learning.slack")

PAGE_SIZE = 200
SKIP_SUBTYPES = {  # channel bookkeeping events, never knowledge
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "pinned_item",
    "unpinned_item",
}


def _when(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


class SlackConnector:
    def __init__(
        self,
        channel_id: str,
        *,
        token: str | None = None,
        workspace_url: str | None = None,
        api_url: str | None = None,
        lookback_days: int | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        token = token or settings.slack_bot_token
        if not token:
            raise ConfigError("SLACK_BOT_TOKEN is not set")
        self.channel_id = channel_id
        self.workspace_url = (workspace_url or settings.slack_workspace_url or "").rstrip("/")
        self.lookback = (
            lookback_days if lookback_days is not None else settings.slack_thread_lookback_days
        )
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=api_url or settings.slack_api_url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "syncra"},
            timeout=30,
            transport=transport,
        )

    # --- HTTP ----------------------------------------------------------------------------

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        for _ in range(3):
            response = self._client.get(f"/{method}", params=params)
            if response.status_code == 429:
                wait = min(max(float(response.headers.get("retry-after", 5)), 1.0), 900)
                log.warning("Slack rate limit hit on %s; waiting %.0fs", method, wait)
                self._sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack {method} failed: {data.get('error')}")
            return data
        raise RuntimeError(f"Slack rate limit: giving up on {method}")

    def _paged(self, method: str, params: dict[str, Any], key: str) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            data = self._call(method, {**params, **({"cursor": cursor} if cursor else {})})
            yield from data.get(key, [])
            cursor = data.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                return

    # --- fetch ---------------------------------------------------------------------------

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        info = self._call("conversations.info", {"channel": self.channel_id})["channel"]
        if info.get("is_im") or info.get("is_mpim"):
            log.info("skipping direct-message conversation %s", self.channel_id)
            return [], since_cursor

        tags = (access_tag("slack", self.channel_id),)
        since = float(since_cursor) if since_cursor else 0.0
        latest = since
        params: dict[str, Any] = {"channel": self.channel_id, "limit": PAGE_SIZE}
        if since_cursor:
            params["oldest"] = f"{since - self.lookback * 86400:.6f}"

        items: list[RawItem] = []
        for message in self._paged("conversations.history", params, "messages"):
            ts = float(message["ts"])
            latest = max(latest, ts)  # the cursor moves past everything seen, even skipped
            if message.get("subtype") in SKIP_SUBTYPES:
                continue
            if message.get("reply_count"):
                last_reply = float(message.get("latest_reply") or message["ts"])
                latest = max(latest, last_reply)
                if ts <= since and last_reply <= since:
                    continue  # old thread, nothing new
                replies = list(
                    self._paged(
                        "conversations.replies",
                        {"channel": self.channel_id, "ts": message["ts"], "limit": PAGE_SIZE},
                        "messages",
                    )
                )
                items.append(self._thread(replies or [message], tags))
            else:
                if ts <= since:
                    continue  # inside the look-back window but already stored
                if message.get("thread_ts") and message["thread_ts"] != message["ts"]:
                    continue  # a reply broadcast to the channel; it lives in its thread
                items.append(self._message(message, tags))

        return items, (f"{latest:.6f}" if latest else since_cursor)

    def members(self) -> list[str]:
        params = {"channel": self.channel_id, "limit": PAGE_SIZE}
        return [f"slack:{m}" for m in self._paged("conversations.members", params, "members")]

    # --- mapping -------------------------------------------------------------------------

    @staticmethod
    def _author(message: dict[str, Any]) -> str | None:
        # Apps post with a bot user (U...) and a bot id (B...): the bot id marks them for triage.
        user = message.get("bot_id") or message.get("user")
        return f"slack:{user}" if user else None

    def _link(self, ts: str) -> str | None:
        if not self.workspace_url:
            return None
        return f"{self.workspace_url}/archives/{self.channel_id}/p{ts.replace('.', '')}"

    def _message(self, message: dict[str, Any], tags: tuple[str, ...]) -> RawItem:
        return RawItem(
            external_id=message["ts"],
            type="message",
            text=message.get("text") or "",
            author=self._author(message),
            created_at=_when(message["ts"]),
            updated_at=_when(message["ts"]),
            link=self._link(message["ts"]),
            access_tags=tags,
        )

    def _thread(self, messages: list[dict[str, Any]], tags: tuple[str, ...]) -> RawItem:
        messages = sorted(messages, key=lambda m: float(m["ts"]))
        parent = messages[0]
        lines = [f"{self._author(m) or 'unknown'}: {m.get('text') or ''}" for m in messages]
        first_line = (parent.get("text") or "").splitlines()[0] if parent.get("text") else ""
        return RawItem(
            external_id=parent["ts"],
            type="thread",
            title=first_line[:120] or None,
            text="\n".join(lines),
            author=self._author(parent),
            created_at=_when(parent["ts"]),
            updated_at=_when(messages[-1]["ts"]),
            link=self._link(parent["ts"]),
            access_tags=tags,
        )
