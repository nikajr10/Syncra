"""Claim checker (Task 7.3): every claim of an answer is checked against the evidence it cites.

The answer is split into claims (sentences, and list items), each with the `[E#]` it cites.
The DeBERTa NLI model (`claim_checker`) reads each cited piece of evidence (header + text) as
the premise and the claim as the hypothesis; the claim is supported when one of them entails it
with at least the role's `threshold`. A claim citing nothing is checked against all evidence and
gets the citation of the piece that supports it. Unsupported claims are removed. Sentences
that only say what isn't known ("I don't know …") make no claim and stay.

`confidence` (Task 7.4) labels the checked answer high, medium or low.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.chat.search import Evidence
from app.config.settings import get_models_config, get_settings
from app.models import gateway

CITATION = re.compile(r"\[(E\d+(?:\s*,\s*E\d+)*)\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=\S)")
HEDGE = re.compile(
    r"\b(?:don'?t|do not|doesn'?t|does not|can'?t|cannot) (?:know|say|mention|tell|find)\b"
    r"|\bno (?:evidence|information)\b",
    re.I,
)


@dataclass(frozen=True)
class Claim:
    text: str  # the sentence as written, with its citations
    cited: tuple[str, ...]  # E# labels after checking (added for an uncited supported claim)
    supported: bool | None  # None: a hedge, nothing to check
    score: float  # best entailment probability among the evidence checked (0 for a hedge)


@dataclass(frozen=True)
class Checked:
    text: str  # the answer without its unsupported claims
    claims: list[Claim]

    @property
    def removed(self) -> list[Claim]:
        return [c for c in self.claims if c.supported is False]


def _labels(sentence: str) -> tuple[str, ...]:
    found = (label.strip() for m in CITATION.findall(sentence) for label in m.split(","))
    return tuple(dict.fromkeys(found))


def check(answer: str, evidence: Sequence[Evidence]) -> Checked:
    """`answer` with every claim its evidence doesn't support removed."""
    by_label = {e.label: f"{e.header}\n{e.text}" for e in evidence}
    lines = [[s for s in SENTENCE.split(line.strip()) if s] for line in answer.splitlines()]
    sentences = [s for line in lines for s in line]

    pairs, owners = [], []  # (premise, claim) to check, and the sentence each belongs to
    for n, sentence in enumerate(sentences):
        if HEDGE.search(sentence) and not CITATION.search(sentence):
            continue
        claim = CITATION.sub("", sentence).strip().lstrip("-*• ")
        for label in _labels(sentence) or tuple(by_label):  # uncited: any evidence may support it
            if label in by_label:
                pairs.append((by_label[label], claim))
                owners.append((n, label))
    entailed: dict[int, dict[str, float]] = {}
    for (n, label), p in zip(owners, gateway.nli("claim_checker", pairs), strict=True):
        entailed.setdefault(n, {})[label] = p.get("entailment", 0.0)

    threshold = get_models_config()["claim_checker"].threshold
    claims, kept = [], set()
    for n, sentence in enumerate(sentences):
        cited = _labels(sentence)
        if HEDGE.search(sentence) and not cited:
            claims.append(Claim(sentence, (), None, 0.0))
            kept.add(n)
            continue
        scores = entailed.get(n, {})
        best = max(scores, key=scores.get, default=None)
        supported = best is not None and scores[best] >= threshold
        if supported and not cited:  # true but uncited: cite what supports it
            cited, sentence = (best,), _cite(sentence, best)
        claims.append(Claim(sentence, cited, supported, scores.get(best, 0.0) if best else 0.0))
        if supported:
            kept.add(n)
            sentences[n] = sentence

    out, n = [], 0
    for line in lines:
        kept_line = [sentences[n + i] for i in range(len(line)) if n + i in kept]
        n += len(line)
        if kept_line:
            out.append(" ".join(kept_line))
    return Checked("\n".join(out), claims)


def _cite(sentence: str, label: str) -> str:
    end = len(sentence.rstrip(".!?"))
    return f"{sentence[:end]} [{label}]{sentence[end:]}"


def confidence(checked: Checked, evidence: Sequence[Evidence]) -> str:
    """high | medium | low: how much of the answer the evidence backs, times how relevant the
    evidence it cites is.

    support = supported claims / checked claims (hedges don't count); relevance = the
    reranker's best score among the cited evidence, squashed to 0–1 (sigmoid). No supported
    claim (an "I don't know", or everything removed) is always low.
    """
    checked_claims = [c for c in checked.claims if c.supported is not None]
    supported = [c for c in checked_claims if c.supported]
    if not supported:
        return "low"
    cited = {label for c in supported for label in c.cited}
    best = max((e.score for e in evidence if e.label in cited), default=-math.inf)
    relevance = 1 / (1 + math.exp(-best)) if best > -math.inf else 0.0
    score = len(supported) / len(checked_claims) * relevance
    settings = get_settings()
    if score >= settings.confidence_high:
        return "high"
    return "medium" if score >= settings.confidence_medium else "low"
