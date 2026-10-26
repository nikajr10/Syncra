"""Task 10.1: the demo company loads through its own connector, never a real API."""

from app.db.schema import Source
from app.learning.connectors import build_connector
from app.learning.connectors.demo import DemoConnector, company


def test_every_demo_source_yields_valid_items_once() -> None:
    data = company()
    accounts = {f"{tool}:{a}" for u in data["users"].values() for tool, a in u["accounts"].items()}
    for spec in data["sources"]:
        source = Source(kind=spec["kind"], external_id=spec["external_id"], config={"demo": True})
        connector = build_connector(source)
        assert isinstance(connector, DemoConnector)
        items, cursor = connector.fetch_new(None)
        assert len(items) == len(spec["items"]) and cursor
        assert all(source.access_tag in i.access_tags for i in items)
        assert ("public" in items[0].access_tags) == bool(spec.get("public"))
        assert set(connector.members()) <= accounts
        assert connector.fetch_new(cursor) == ([], cursor)  # nothing new until the file changes
