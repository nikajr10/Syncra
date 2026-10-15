"""Connector registry: build the right connector for a `sources` row (Task 1.6)."""

from __future__ import annotations

from app.db.schema import Source
from app.learning.connectors.base import Connector, RawItem

__all__ = ["Connector", "RawItem", "build_connector"]


def build_connector(source: Source) -> Connector:
    """`sources.external_id` is the repo (owner/name), Jira project key or Slack channel id."""
    if source.kind == "github":
        from app.learning.connectors.github import GitHubConnector

        return GitHubConnector(source.external_id)
    if source.kind == "jira":
        from app.learning.connectors.jira import JiraConnector

        return JiraConnector(source.external_id)
    if source.kind == "slack":
        from app.learning.connectors.slack import SlackConnector

        return SlackConnector(source.external_id)
    raise ValueError(f"unknown source kind {source.kind!r}")
