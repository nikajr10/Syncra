"""Security pass: source-id validation, token never leaves the GitHub host, API headers + errors."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config.settings import Settings
from app.db.schema import Source
from app.learning.connectors import build_connector
from app.learning.connectors.github import GitHubConnector


@pytest.mark.parametrize(
    ("kind", "external_id"),
    [
        ("github", "../user"),  # path traversal to /user/issues (every repo the token sees)
        ("github", "acme/.."),
        ("github", "acme/payments/../../orgs/x"),
        ("jira", 'PAY" OR project = "HR'),  # JQL injection into another project
        ("jira", "pay"),
        ("slack", "D0123"),  # direct messages are never synced
        ("slack", "C1&channel=C2"),
    ],
)
def test_crafted_source_ids_are_rejected(kind: str, external_id: str) -> None:
    with pytest.raises(ValueError, match="invalid"):
        build_connector(Source(kind=kind, external_id=external_id))


def test_github_token_is_not_sent_to_another_host() -> None:
    sent_to: list[str] = []

    def fake(request: httpx.Request) -> httpx.Response:
        sent_to.append(request.url.host)
        if request.url.path == "/repos/acme/x":
            return httpx.Response(200, json={"private": True})
        return httpx.Response(200, json=[], headers={"Link": '<https://evil.test/p2>; rel="next"'})

    connector = GitHubConnector(
        "acme/x", token="tok", api_url="https://gh.test", transport=httpx.MockTransport(fake)
    )
    with pytest.raises(RuntimeError, match="not sending the token"):
        connector.fetch_new(None)
    assert set(sent_to) == {"gh.test"}


def test_every_response_has_security_headers_and_a_request_id() -> None:
    response = TestClient(app).get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "max-age=31536000" in response.headers["strict-transport-security"]
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert len(response.headers["x-request-id"]) == 32
    assert "server" not in response.headers or "uvicorn" not in response.headers["server"]


def test_unhandled_error_returns_generic_message_with_correlation_id() -> None:
    def boom() -> None:
        raise RuntimeError("password=hunter2 at /srv/app/secret.py")

    app.add_api_route("/__boom", boom)
    try:
        response = TestClient(app).get("/__boom")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "Internal server error", "request_id": body["request_id"]}
    assert "hunter2" not in response.text and "secret.py" not in response.text
    assert response.headers["x-request-id"] == body["request_id"]


def test_api_docs_are_off_unless_turned_on() -> None:
    assert Settings.model_fields["api_docs"].default is False
