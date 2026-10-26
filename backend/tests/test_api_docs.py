"""The API documentation (Swagger UI at /docs, ReDoc at /redoc, when API_DOCS is on)."""

import json

from app.api.main import app

PUBLIC = {"/health", "/auth/login"}


def test_every_endpoint_is_documented() -> None:
    spec = app.openapi()
    assert "Authorize" in spec["info"]["description"]  # how to log in on the docs page
    tags = {tag["name"] for tag in spec["tags"]}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            where = (method, path)
            assert operation["tags"] and set(operation["tags"]) <= tags, where
            [(code, ok)] = [(c, r) for c, r in operation["responses"].items() if c[0] == "2"]
            if "text/event-stream" in ok.get("content", {}):  # a stream: described in words
                assert ok["description"], where
            elif code != "204":  # a body: described by a named model, not a bare dict
                assert "$ref" in json.dumps(ok["content"]["application/json"]["schema"]), where
            if path not in PUBLIC:  # the lock icon and the 401 are on the page
                assert operation["security"] == [{"HTTPBearer": []}], where
                assert "401" in operation["responses"], where
