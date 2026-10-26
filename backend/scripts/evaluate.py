"""Evaluation runner (Task 10.2): `make eval`, after `make demo`.

Asks every question of data/demo/eval.yaml as its user, through the real search, answer writer and
claim checker (guard, intent and rewriter are skipped: the questions stand alone), and prints:

- right source in top 8: an expected item is among the evidence (answerable questions)
- leaks: evidence from an item the asking user must never see (must be 0)
- citations backed: cited claims the claim checker found supported by what they cite
- answers citing a right source: the checked reply cites an expected item
- unsupported-claim rate: claims the checker removed
- "I don't know" when it should, and when it shouldn't have
- time per stage (search, first word, whole answer, check)

`--search-only` skips the LLM (seconds instead of minutes) and reports retrieval only.
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import yaml
from sqlalchemy import select

from app.core.config import BACKEND_DIR
from app.db.models import Item, Source, User
from app.db.session import new_session
from app.services.chat import answer, search
from app.services.chat.check import CITATION, check
from app.services.chat.permissions import user_tags

EVAL_FILE = BACKEND_DIR / "data" / "demo" / "eval.yaml"
IDK = "i don't know"


@dataclass
class Result:
    question: str
    user: str
    answerable: bool
    found: bool  # an expected item is in the evidence
    leaked: list[str]  # hidden items in the evidence
    reply: str = ""
    cited_right: bool = False  # the checked reply cites an expected item
    claims: int = 0  # claims checked (hedges excluded)
    removed: int = 0
    cited_claims: int = 0
    cited_backed: int = 0
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def said_idk(self) -> bool:
        return IDK in self.reply.lower()


def item_keys(evidence: list[search.Evidence]) -> dict[str, str]:
    """{E#: "<source external id>|<item external id>"} of each piece of evidence."""
    with new_session() as session:
        rows = session.execute(
            select(Item.id, Source.external_id, Item.external_id)
            .join(Source, Source.id == Item.source_id)
            .where(Item.id.in_([e.item_id for e in evidence]))
        ).all()
    keys = {item_id: f"{source}|{item}" for item_id, source, item in rows}
    return {e.label: keys[e.item_id] for e in evidence}


def run_one(entry: dict[str, Any], llm: bool) -> Result:
    with new_session() as session:
        user_id = session.scalar(select(User.id).where(User.username == entry["user"]))
        if user_id is None:
            raise SystemExit(f"No user {entry['user']}: run `make demo` first.")
        tags = user_tags(session, user_id)
    timings: dict[str, float] = {}
    started = time.perf_counter()
    evidence = search.find_evidence(entry["question"], tags)
    timings["search"] = time.perf_counter() - started
    keys = item_keys(evidence)
    expected, hidden = set(entry.get("sources", [])), set(entry.get("hidden", []))
    result = Result(
        entry["question"], entry["user"], entry["answerable"],
        found=bool(expected & set(keys.values())),
        leaked=sorted(hidden & set(keys.values())), timings=timings,
    )  # fmt: skip
    if not llm:
        return result
    started, pieces = time.perf_counter(), []
    for piece in answer.write(entry["question"], evidence):
        timings.setdefault("first_word", time.perf_counter() - started)
        pieces.append(piece)
    timings["answer"] = time.perf_counter() - started
    draft, _ = answer.split("".join(pieces))
    started = time.perf_counter()
    checked = check(draft, evidence)
    timings["check"] = time.perf_counter() - started
    claims = [c for c in checked.claims if c.supported is not None]
    cited_in_draft = [c for c in claims if search_labels(c.text)]
    result.reply = checked.text or "I don't know"
    result.claims, result.removed = len(claims), len(checked.removed)
    result.cited_claims = len(cited_in_draft)
    result.cited_backed = sum(1 for c in cited_in_draft if c.supported)
    result.cited_right = bool({keys.get(label) for label in search_labels(result.reply)} & expected)
    return result


def search_labels(text: str) -> set[str]:
    return {label.strip() for m in CITATION.findall(text) for label in m.split(",")}


def _pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "n/a"


def report(results: list[Result], llm: bool, say: Callable[[str], None] = print) -> dict:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    leaks = [r for r in results if r.leaked]
    scores: dict[str, Any] = {
        "questions": len(results),
        "found": sum(r.found for r in answerable),
        "leaks": len(leaks),
    }
    say(f"Questions: {len(results)} ({len(answerable)} answerable, {len(unanswerable)} not)")
    say(f"Right source in top 8: {_pct(scores['found'], len(answerable))}")
    say(f"Leaks of hidden items: {len(leaks)}")
    if llm:
        claims = sum(r.claims for r in results)
        cited = sum(r.cited_claims for r in results)
        scores |= {
            "cited_backed": sum(r.cited_backed for r in results), "cited_claims": cited,
            "cited_right": sum(r.cited_right for r in answerable),
            "removed": sum(r.removed for r in results), "claims": claims,
            "idk_right": sum(r.said_idk for r in unanswerable),
            "idk_wrong": sum(r.said_idk for r in answerable),
        }  # fmt: skip
        say(f"Citations backed by their evidence: {_pct(scores['cited_backed'], cited)}")
        say(f"Answers citing a right source: {_pct(scores['cited_right'], len(answerable))}")
        say(f"Unsupported-claim rate (removed): {_pct(scores['removed'], claims)}")
        say(f'"I don\'t know" when it should: {_pct(scores["idk_right"], len(unanswerable))}')
        say(f'"I don\'t know" when it had the answer: {_pct(scores["idk_wrong"], len(answerable))}')
    for stage in ("search", "first_word", "answer", "check"):
        times = [r.timings[stage] for r in results if stage in r.timings]
        if times:
            say(f"Time, {stage}: median {statistics.median(times):.2f}s, max {max(times):.2f}s")
    misses = [r for r in answerable if not r.found or (llm and not r.cited_right)]
    for r in misses + leaks + [r for r in unanswerable if llm and not r.said_idk]:
        say(f"- check: [{r.user}] {r.question} -> found={r.found} leaked={r.leaked} "
            f"reply={r.reply[:160]!r}")  # fmt: skip
    return scores


def main(argv: list[str]) -> None:
    llm = "--search-only" not in argv
    entries = yaml.safe_load(EVAL_FILE.read_text())
    results = []
    for n, entry in enumerate(entries, 1):
        print(f"[{n}/{len(entries)}] {entry['question']}", file=sys.stderr)
        results.append(run_one(entry, llm))
    report(results, llm)


if __name__ == "__main__":
    main(sys.argv[1:])
