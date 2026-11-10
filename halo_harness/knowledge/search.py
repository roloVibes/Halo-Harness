"""halo_harness.knowledge.search -- findings and decisions for some words (Halo
3.1.8.0 R4, docs/KNOWLEDGE.md "Searching"; 3.3.16.2 "knowledge that answers
the question").

`search(query, k=, kinds=, state_dir=, cwd=, project=)` ranks the current
entries by RELEVANCE first: the share of the query's content words a record
says (knowledge/rank.py: paths, commands and shas are not words a record says;
"the", "of" ... are not content words), or recall's score when embeddings are
configured and it is `RECALL_MIN` or more. A record with neither is not a hit,
however new it is. Then:

* scope -- the project the search is made from (`project`, else `cwd`'s git
  root): its records and the ones written with no project first at equal
  relevance; another project's only when they match, marked with it;
  `project="all"` drops the preference;
* the guided first run's sample (`halo start`'s basket repo) never answers a
  search made from another project;
* a routine "gate passed" record counts `GATE_FACTOR` of its relevance, so it
  ranks under findings and decisions -- unless the query names its file or
  symbol (a gate that failed is a decision and keeps its rank);
* near-duplicates (the same gate on the same unit, re-run) collapse to the
  newest with "x N".

Each hit: {"id", "kind", "title", "score", "by", "when", "confidence", "path",
"via": "recall" | "words", "project", "n", "why"} -- `why` says in a few words
why it is there ("2/6 words: halo, harness; project basket"). `SEARCH(query,
state_dir, k)` replaces recall.search (tests).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from halo_harness.knowledge import rank as R

SEARCH: Optional[Callable] = None
KINDS = ("finding", "decision")
RECALL_MIN = 0.35
GATE_FACTOR = 0.5


def _words(text: str) -> set:  # kept for callers of 3.1.8.0's name
    return R.content_words(text)


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


def _why(matched: list, want: set, recall: float, project: str, here: str, routine: bool, n: int) -> str:
    bits = [f"{len(matched)}/{len(want)} words: {', '.join(sorted(matched)[:5])}" if matched
            else f"recall {recall:.2f}"]
    if project and project != here:
        bits.append(f"project {project}")
    elif project:
        bits.append("this project")
    if routine:
        bits.append("a passed gate, ranked under findings")
    if n > 1:
        bits.append(f"x{n} (re-run)")
    return "; ".join(bits)


def rank(query: str, rows: list, k: int, *, recall: Optional[dict] = None, here: str = "", scope: str = ".",
         state_dir=None) -> list:
    """The hits for `query` among `rows` (see the module docstring); `recall`: {path: score}; `scope`: "." (the
    project `here`), "all", or a project name (only its records and the ones with no project)."""
    want = R.content_words(query)
    if not want:
        return []
    folders = R.sample_folders(state_dir)
    home = here if scope == "." else scope  # the project whose sample records may answer ("all": every one)
    cands = []
    for e in rows:
        project = R.project_of(e)
        if scope not in (".", "all") and project not in ("", scope):
            continue
        if scope != "all" and project != home and R.is_sample(e, state_dir, folders):
            continue
        matched = sorted(want & R.entry_words(e))
        rec = float((recall or {}).get(str(Path(e["path"])), 0.0))
        relevance = max(len(matched) / len(want), rec if rec >= RECALL_MIN else 0.0)
        if relevance <= 0:
            continue
        routine = R.is_routine_gate(e) and not R.names_unit(e, want)
        cands.append({"e": e, "rel": relevance * (GATE_FACTOR if routine else 1.0), "rec": rec, "matched": matched,
                      "routine": routine, "away": scope == "." and project not in ("", here), "project": project})
    cands.sort(key=lambda c: (c["e"]["when"], c["e"]["id"]), reverse=True)  # the newest first, kept by the sorts below
    groups: dict = {}
    for c in cands:  # near-duplicates: the newest stands for the rest
        groups.setdefault(R.dup_key(c["e"]), []).append(c)
    best = [g[0] | {"n": len(g)} for g in groups.values()]
    best.sort(key=lambda c: (c["e"]["when"], c["e"]["id"]), reverse=True)
    best.sort(key=lambda c: (-round(c["rel"], 6), c["away"], -c["rec"]))
    out = []
    for c in best[:k]:
        e = c["e"]
        via = "recall" if c["rec"] >= RECALL_MIN else "words"
        out.append({"id": e["id"], "kind": e["kind"], "title": e["title"],
                    "score": round(c["rec"] if via == "recall" else c["rel"], 4), "by": e["by"], "when": e["when"],
                    "confidence": e.get("confidence") or "", "path": e["path"], "via": via, "project": c["project"],
                    "n": c["n"], "why": _why(c["matched"], want, c["rec"], c["project"], here, c["routine"], c["n"])})
    return out


def by_words(query: str, rows: list, k: int) -> list:
    """3.1.8.0's word match (no recall, every project): `rank` with scope "all"."""
    return rank(query, rows, k, scope="all")


def search(query: str, *, k: int = 8, kinds=KINDS, state_dir=None, cwd=None, project: Optional[str] = None) -> list:
    from halo_harness.knowledge.store import current
    query = " ".join(str(query or "").split())
    if not query:
        return []
    rows = [e for e in current(state_dir) if e["kind"] in kinds]
    if not rows:
        return []
    hits = _recall(query, max(50, k), state_dir)
    recall = None
    if hits is not None:
        recall = {str(Path(str(h.get("id") or ""))): float(h.get("score") or 0.0) for h in hits if h.get("kind") in kinds}
    scope = project if project not in (None, "", ".") else "."
    return rank(query, rows, k, recall=recall, here=R.project_here(cwd), scope=scope, state_dir=state_dir)
