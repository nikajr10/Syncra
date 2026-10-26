"""Demo connector (Task 10.1): the fictional company in data/demo/company.yaml, as if synced.

Sources created by `make demo` carry `config.demo = true`; `build_connector` hands them this
connector instead of a real API, so the worker never asks GitHub, Jira or Slack about them.
The cursor is the file's hash: an edited file is synced again (unchanged items are skipped).
"""

from __future__ import annotations

import hashlib
from typing import Any

import yaml

from app.connectors.base import RawItem
from app.core.config import BACKEND_DIR
from app.db.models import Source, access_tag

DEMO_FILE = BACKEND_DIR / "data" / "demo" / "company.yaml"


def company() -> dict[str, Any]:
    return yaml.safe_load(DEMO_FILE.read_text())


class DemoConnector:
    def __init__(self, source: Source) -> None:
        text = DEMO_FILE.read_text()
        self.version = hashlib.sha256(text.encode()).hexdigest()[:16]
        self.spec = next(
            s for s in yaml.safe_load(text)["sources"]
            if (s["kind"], s["external_id"]) == (source.kind, source.external_id)
        )  # fmt: skip

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        if since_cursor == self.version:
            return [], since_cursor
        tag = access_tag(self.spec["kind"], self.spec["external_id"])
        tags = ("public", tag) if self.spec.get("public") else (tag,)
        return [RawItem(**item, access_tags=tags) for item in self.spec["items"]], self.version

    def members(self) -> list[str]:
        return [] if self.spec.get("public") else list(self.spec.get("members", []))
