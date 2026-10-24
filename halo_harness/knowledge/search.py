"""halo_harness.knowledge.search -- findings and decisions for some words (Halo
3.1.8.0 R4, docs/KNOWLEDGE.md "Searching").

`search(query, k=, kinds=, state_dir=)` ranks the current entries through
recall (recall.search over the index, kept to the kinds finding and
decision) when embeddings are configured; when they are not, a plain word
match over the entries' titles, bodies, evidence and tags ranks them (the
share of the query's words an entry holds), so `knowledge_search` and `halo
knowledge search` answer either way. Each hit:

    {"id": "f-20261024-a1b2c3", "kind": "finding", "title", "score", "by", "when", "confidence", "path", "via": "recall" | "words"}

`SEARCH(query, state_dir, k)` replaces recall.search (tests).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

SEARCH: Optional[Callable] = None
KINDS = ("finding", "decision")
_WORD = re.compile(r"[a-z0-9_]{2,}")


def _words(text: str) -> set:
    return set(_WORD.findall(str(text or "").lower()))


def _hit(entry: dict, score: float, via: str) -> dict:
    return {"id": entry["id"], "kind": entry["kind"], "title": entry["title"], "score": round(float(score), 4),
            "by": entry["by"], "when": entry["when"], "confidence": entry.get("confidence") or "", "path": entry["path"],
            "via": via}


def _recall(query: str, k: int, state_dir) -> Optional[list]:
    """The recall hits of the knowledge kinds; None when embeddings are off (or the index answered nothing)."""
    try:
        if SEARCH is not None:
            return list(SEARCH(query, state_dir, k) or [])
        from halo_harness.providers.embeddings import embeddings_enabled
        if not embeddings_enabled():
            return None
        from halo_harness.recall import search as recall_search
        return recall_search(query, state_dir=state_dir, k=k)
    except Exception:  # a broken index never stops a search: the words answer
        return None


def by_words(query: str, rows: list, k: int) -> list:
    want = _words(query)
    if not want:
        return []
    scored = []
    for e in rows:
        have = _words(" ".join([e["title"], e["body"], " ".join(e["evidence"]), " ".join(e["tags"]), e["id"]]))
        share = len(want & have) / len(want)
        if share > 0:
            scored.append((share, e))
    scored.sort(key=lambda pair: (pair[1]["when"], pair[1]["id"]), reverse=True)  # ties: the newest first
    scored.sort(key=lambda pair: -pair[0])
    return [_hit(e, s, "words") for s, e in scored[:k]]


def search(query: str, *, k: int = 8, kinds=KINDS, state_dir=None) -> list:
    from halo_harness.knowledge.store import current
    query = " ".join(str(query or "").split())
    if not query:
        return []
    rows = [e for e in current(state_dir) if e["kind"] in kinds]
    if not rows:
        return []
    by_path = {str(Path(e["path"])): e for e in rows}
    hits = _recall(query, max(50, k), state_dir)
    if hits is None:
        return by_words(query, rows, k)
    out = []
    for h in hits:
        e = by_path.get(str(Path(str(h.get("id") or ""))))
        if e is not None and h.get("kind") in kinds:
            out.append(_hit(e, float(h.get("score") or 0.0), "recall"))
    return out[:k]
