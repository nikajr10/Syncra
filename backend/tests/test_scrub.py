"""Task 1.5: personal data and secrets are masked; normal code names are not."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.schema import Item, Source
from app.learning.scrub import Scrubber, get_scrubber
from app.learning.sync import sync_source
from tests.fakes import FakeConnector, item

LEAKS = (
    "acme.com",
    "555-2671",
    "AKIA",
    "ghp_",
    "xoxb-",
    "s3cretPw",
    "hunter2",
    "wJalr",
    "4111 1111",
    "MIIEow",
    "eyJhbGci",
)


@pytest.fixture(scope="module")
def scrubber() -> Scrubber:
    return get_scrubber()


@pytest.mark.parametrize(
    ("text", "masked_as"),
    [
        ("ping alice.smith@acme.com about it", "<EMAIL_ADDRESS>"),
        ("call me on +1 415-555-2671 tomorrow", "<PHONE_NUMBER>"),
        ("key AKIAIOSFODNN7EXAMPLE leaked", "<AWS_ACCESS_KEY>"),
        ("use ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd for CI", "<GITHUB_TOKEN>"),
        # split so the repo never holds a whole token-shaped string (GitHub push protection)
        ("token xoxb-" + "123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx", "<SLACK_TOKEN>"),
        ("db is postgres://app:s3cretPw@db.internal:5432/prod", "<CONNECTION_STRING>"),
        ('set password = "hunter2!"', "<PASSWORD_ASSIGNMENT>"),
        ("AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "<PASSWORD_ASSIGNMENT>"),
        ("card 4111 1111 1111 1111 was charged", "<CREDIT_CARD>"),
        (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
            "<PRIVATE_KEY>",
        ),
        (
            "jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "<JWT>",
        ),
    ],
)
def test_personal_data_and_secrets_are_masked(
    scrubber: Scrubber, text: str, masked_as: str
) -> None:
    out = scrubber.scrub(text)
    assert masked_as in out, out
    for secret in LEAKS:
        assert secret not in out, out


@pytest.mark.parametrize(
    "text",
    [
        "PaymentService calls payments-svc with retry_limit = 3",
        "see PAY-1234 and PR #42 by alice; reviewed by Bob Smith",
        "commit 3f2a9c1d4e5b6a7f8091a2b3c4d5e6f708192a3b fixes v2.3.1",
        "api_key = settings.api_key; token = get_token()",
        "health at http://localhost:8000/health returned 200",
        "RabbitMQ queue between checkout and the payment service",
    ],
)
def test_normal_code_and_names_are_untouched(scrubber: Scrubber, text: str) -> None:
    assert scrubber.scrub(text) == text


def test_scrub_item_cleans_title_and_text_only(scrubber: Scrubber) -> None:
    raw = item(1, "mail bob@acme.com", title="token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd")
    clean = scrubber.scrub_item(raw)
    assert "bob@acme.com" not in clean.text and "<EMAIL_ADDRESS>" in clean.text
    assert "ghp_" not in clean.title
    assert (clean.external_id, clean.author, clean.link) == (raw.external_id, raw.author, raw.link)


def test_sync_scrubs_before_saving(db_session: Session) -> None:
    source = Source(kind="slack", name="#eng", external_id="C1")
    db_session.add(source)
    db_session.commit()
    sync_source(
        db_session, source, FakeConnector([item(1, "ask carol@acme.com, key AKIAIOSFODNN7EXAMPLE")])
    )
    stored = db_session.scalars(select(Item)).one()
    assert "carol@acme.com" not in stored.text and "AKIA" not in stored.text
    assert "<EMAIL_ADDRESS>" in stored.text and "<AWS_ACCESS_KEY>" in stored.text
