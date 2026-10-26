"""Privacy scrubber (Task 1.5): hides personal data and secrets before anything is stored.

Built on Microsoft Presidio. Person names are deliberately NOT hidden: "who built X" is the
product. Hidden: emails, phone numbers, credit cards, IBANs, US SSNs, IP addresses, and secrets
(cloud / GitHub / Slack tokens, private keys, connection strings, password assignments, JWTs).
Each hit is replaced by `<ENTITY_TYPE>`.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.config.settings import get_models_config
from app.learning.connectors.base import RawItem

log = logging.getLogger("syncra.learning.scrub")

PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN", "IP_ADDRESS"]

# Secret detectors. Values must look like literal secrets so code names survive
# (no `(`, `[`, `.` in unquoted values; unquoted values need a digit).
_VALUE = (
    r"""(?:"[^"\n]{6,}"|'[^'\n]{6,}'"""
    r"""|(?=[A-Za-z0-9_\-+/=!@#$%^&*]{8,}(?:\s|$))(?=\S*\d)[A-Za-z0-9_\-+/=!@#$%^&*]{8,})"""
)
# After "password=", a plain word is a password too (`password=hunter2`); code still survives
# because calls, attributes and short type names don't match (`password=get_pw()`, `pwd: str`).
_PASSWORD = (
    r"""(?:"[^"\n]{6,}"|'[^'\n]{6,}'"""
    r"""|(?=[A-Za-z0-9_\-+/=!@#$%^&*]{6,}(?:\s|$))[A-Za-z0-9_\-+/=!@#$%^&*]{6,})"""
)
SECRET_PATTERNS: dict[str, str] = {
    "AWS_ACCESS_KEY": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "GITHUB_TOKEN": (
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"
    ),
    "SLACK_TOKEN": r"\bxox[abeprs]-[0-9A-Za-z-]{10,}\b",
    "PRIVATE_KEY": r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    "CONNECTION_STRING": r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s@]+@[^\s]+",
    "PASSWORD_ASSIGNMENT": (
        r"(?i)(?<![A-Za-z])(?:(?:secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)"
        r"\s*[:=]\s*" + _VALUE + r"|(?:password|passwd|pwd)\s*[:=]\s*" + _PASSWORD + ")"
    ),
    "JWT": r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
}
ENTITIES = PII_ENTITIES + list(SECRET_PATTERNS)


class Scrubber:
    def __init__(self) -> None:
        spacy_model = get_models_config()["presidio_nlp"].name
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": spacy_model}],
            }
        ).create_engine()
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        for entity, regex in SECRET_PATTERNS.items():
            self._analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=entity,
                    patterns=[Pattern(name=entity.lower(), regex=regex, score=0.9)],
                )
            )
        self._anonymizer = AnonymizerEngine()
        self._operators = {
            entity: OperatorConfig("replace", {"new_value": f"<{entity}>"}) for entity in ENTITIES
        }

    def scrub(self, text: str) -> str:
        if not text:
            return text
        results = self._analyzer.analyze(text=text, language="en", entities=ENTITIES)
        if not results:
            return text
        return self._anonymizer.anonymize(
            text=text, analyzer_results=results, operators=self._operators
        ).text

    def scrub_item(self, item: RawItem) -> RawItem:
        return item.model_copy(
            update={
                "text": self.scrub(item.text),
                "title": self.scrub(item.title) if item.title else item.title,
            }
        )


@lru_cache
def get_scrubber() -> Scrubber:
    return Scrubber()
