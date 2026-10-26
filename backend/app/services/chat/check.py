"""Claim checker (Task 7.3): every claim of an answer is checked against the evidence it cites.

The answer is split into claims (sentences, and list items), each with the `[E#]` it cites.
The DeBERTa NLI model (`claim_checker`) reads each cited piece of evidence (`Evidence.premise`)
as the premise and the claim as the hypothesis, and all the cited pieces together when a claim
cites several (a claim may join two facts); the claim is supported when one of them entails it
with at least the role's `threshold`. Each piece is read whole and in windows of two sentences.
A claim citing nothing is checked against all evidence and gets the citation of the piece that
supports it. An unsupported sentence ending in an added explanation (", which …", ", making …")
is checked again without it, and kept that way if it holds. Unsupported claims are removed.
Sentences that only say what isn't known ("I don't know …") make no claim and stay.

`confidence` (Task 7.4) labels the checked answer high, medium or low.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import get_models_config, get_settings
from app.ml import gateway
from app.services.chat.search import Evidence

CITATION = re.compile(r"\[(E\d+(?:\s*,\s*E\d+)*)\]")
CITED = re.compile(r"\s*" + CITATION.pattern)  # with the space before it: "queue ." reads badly
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=\S)")
# ", which means …", ", making it …": an explanation the writer added, often unsupported
TAIL = re.compile(r",\s+(?:which|making|meaning|so that|thereby|ensuring|allowing)\b", re.I)
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


def premises(e: Evidence) -> list[str]:
    """The whole piece, and windows of two sentences of it: the NLI model misses a fact in the
    middle of a long Slack thread that it finds in the line saying it."""
    sentences = [s for line in e.text.splitlines() for s in SENTENCE.split(line.strip()) if s]
    header = e.premise.split("\n", 1)[0]
    windows = [" ".join(sentences[i : i + 2]) for i in range(len(sentences) - 1)]
    return [e.premise, *(f"{header}\n{w}" for w in windows if len(sentences) > 2)]


def _entailment(
    claims: Sequence[tuple[str, Sequence[str]]], by_label: dict[str, list[str]]
) -> list[dict[str, float]]:
    """For each (claim, labels to check it against): the best entailment per label."""
    pairs, owners = [], []
    for n, (claim, labels) in enumerate(claims):
        for label in labels:
            pairs += [(premise, claim) for premise in by_label[label]]
            owners += [(n, label)] * len(by_label[label])
        if len(labels) > 1:  # the facts may be spread over the pieces it cites
            pairs.append(("\n\n".join(by_label[label][0] for label in labels), claim))
            owners.append((n, labels[0]))
    scores: list[dict[str, float]] = [{} for _ in claims]
    for (n, label), p in zip(owners, gateway.nli("claim_checker", pairs), strict=True):
        scores[n][label] = max(scores[n].get(label, 0.0), p.get("entailment", 0.0))
    return scores


def check(answer: str, evidence: Sequence[Evidence]) -> Checked:
    """`answer` with every claim its evidence doesn't support removed."""
    by_label = {e.label: premises(e) for e in evidence}
    threshold = get_models_config()["claim_checker"].threshold
    lines = [[s for s in SENTENCE.split(line.strip()) if s] for line in answer.splitlines()]
    sentences = [s for line in lines for s in line]

    todo: dict[int, tuple[str, list[str]]] = {}  # sentence -> (claim, labels to check it with)
    for n, sentence in enumerate(sentences):
        cited = _labels(sentence)
        if HEDGE.search(sentence) and not cited:
            continue
        labels = [label for label in cited if label in by_label]  # a made-up label: none
        todo[n] = (CITED.sub("", sentence).strip().lstrip("-*• "), labels if cited else [*by_label])
    scores = dict(zip(todo, _entailment(list(todo.values()), by_label), strict=True))

    heads = {}  # a failing sentence whose tail adds an explanation: try it without the tail
    for n, (claim, labels) in todo.items():
        tail = TAIL.search(claim)
        if max(scores[n].values(), default=0.0) < threshold and tail:
            heads[n] = (claim[: tail.start()] + ".", labels)
    for (n, (head, _)), head_scores in zip(
        heads.items(), _entailment(list(heads.values()), by_label), strict=True
    ):
        if max(head_scores.values(), default=0.0) >= threshold:
            scores[n] = head_scores
            cited = _labels(sentences[n])
            sentences[n] = _cite(head, ", ".join(cited)) if cited else head

    claims, kept = [], set()
    for n, sentence in enumerate(sentences):
        if n not in todo:  # a hedge: makes no claim
            claims.append(Claim(sentence, (), None, 0.0))
            kept.add(n)
            continue
        cited, best = _labels(sentence), max(scores[n], key=scores[n].get, default=None)
        supported = best is not None and scores[n][best] >= threshold
        if supported and not cited:  # true but uncited: cite what supports it
            cited, sentence = (best,), _cite(sentence, best)
        claims.append(Claim(sentence, cited, supported, scores[n][best] if best else 0.0))
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
