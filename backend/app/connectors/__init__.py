"""Connector registry: build the right connector for a `sources` row (Task 1.6)."""

from __future__ import annotations

import re

from app.connectors.base import Connector, RawItem
from app.db.models import Source

__all__ = ["Connector", "RawItem", "build_connector"]

# external_id goes into API paths (GitHub) and JQL (Jira): anything else is rejected, so a crafted
# id can't reach other repos / projects (path traversal, JQL injection) under this source's tag.
EXTERNAL_ID = {
    "github": re.compile(r"[A-Za-z0-9-]+/(?!\.{1,2}$)[A-Za-z0-9._-]+"),  # owner/repo
    "jira": re.compile(r"[A-Z][A-Z0-9_]+"),  # project key
    "slack": re.compile(r"[CG][A-Z0-9]+"),  # public / private channel id
}


def build_connector(source: Source) -> Connector:
    """`sources.external_id` is the repo (owner/name), Jira project key or Slack channel id."""
    pattern = EXTERNAL_ID.get(source.kind)
    if pattern and not pattern.fullmatch(source.external_id):
        raise ValueError(f"invalid {source.kind} external_id {source.external_id!r}")
    if (source.config or {}).get("demo"):  # make demo: the fictional company, no real API
        from app.connectors.demo import DemoConnector

        return DemoConnector(source)
    if source.kind == "github":
        from app.connectors.github import GitHubConnector

        return GitHubConnector(source.external_id)
    if source.kind == "jira":
        from app.connectors.jira import JiraConnector

        return JiraConnector(source.external_id)
    if source.kind == "slack":
        from app.connectors.slack import SlackConnector

        return SlackConnector(source.external_id)
    raise ValueError(f"unknown source kind {source.kind!r}")
