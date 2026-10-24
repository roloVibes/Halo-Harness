"""halo_harness.knowledge.cite -- an agent that reuses a finding or a decision
cites it (Halo 3.1.8.0 R4, docs/KNOWLEDGE.md "Citing what was reused").

* `snapshot(hits)` -- the block an agent receives with knowledge hits (the
  `knowledge_search` tool's answer, an Orchestra worker's brief): one line
  per entry with its id, kind, who and when, then CITE_LINE, which tells the
  agent to cite the id of any entry it reuses.
* `brief_text(goal, lane)` -- an Orchestra worker's block: up to BRIEF_K
  entries recall ranks for its job and the goal (score >= MIN_SCORE). Only
  when embeddings are configured, the store holds an entry and
  `knowledge.brief` is not false; '' otherwise (an empty store costs no
  embedding call).
* `cited_ids(text)` -- the knowledge ids `text` names that this harness holds:
  the evidence gatherer's `cited` (outcomes/evidence.py). Nothing asks a
  model whether it reused anything; the id in its answer is the record.
* `reused_by(eid)` -- the outcomes.jsonl rows whose evidence cites `eid`
  (`halo knowledge show`).
"""

from __future__ import annotations

CITE_LINE = ("When you reuse one of these, cite its id in your answer, e.g. (f-20261024-a1b2c3): "
             "the run records what was reused.")
MIN_SCORE, BRIEF_K = 0.35, 3
HEADER = "Findings and decisions this harness knows (its knowledge):"
BRIEF_HEADER = "Findings and decisions this harness knows that rank for your job:"


def line(hit: dict) -> str:
    bits = [hit.get("kind"), hit.get("by"), str(hit.get("when") or "")[:10], hit.get("confidence")]
    return f"- {hit['id']} ({', '.join(str(b) for b in bits if b)}): {hit['title']}"


def snapshot(hits: list, header: str = HEADER) -> str:
    """The block an agent is given for these hits ('' for none)."""
    if not hits:
        return ""
    return "\n".join([header] + [line(h) for h in hits] + [CITE_LINE])


def in_briefs() -> bool:
    try:
        from halo_harness.theme import get_config_value
        value = get_config_value("knowledge.brief", True)
    except Exception:
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "off")


def brief_text(goal, lane, state_dir=None) -> str:
    """An Orchestra worker's block of the entries recall ranks for its job (see the module docstring)."""
    try:
        from halo_harness.knowledge import search as S
        from halo_harness.knowledge.store import current
        if not in_briefs() or not current(state_dir):
            return ""
        if S.SEARCH is None:
            from halo_harness.providers.embeddings import embeddings_enabled
            if not embeddings_enabled():
                return ""
        job = getattr(lane, "job", None)
        query = " ".join(str(x or "") for x in (getattr(job, "title", ""), getattr(goal, "what", ""))).strip()
        hits = [h for h in S.search(query, k=BRIEF_K, state_dir=state_dir)
                if h["via"] == "recall" and h["score"] >= MIN_SCORE]
        return snapshot(hits, BRIEF_HEADER)
    except Exception:  # the brief never fails over its knowledge block
        return ""


def cited_ids(text: str, state_dir=None) -> list:
    """The knowledge ids `text` names (each once, in order) that this harness holds."""
    from halo_harness.knowledge.store import ID_IN_TEXT, path_of
    out = []
    for eid in ID_IN_TEXT.findall(str(text or "")):
        try:
            here = path_of(eid, state_dir).is_file()
        except (OSError, ValueError):
            here = False
        if here and eid not in out:
            out.append(eid)
    return out


def reused_by(eid: str, state_dir=None) -> list:
    """`[{run, task, source, bio, model, outcome, ts}]`: the agent tasks whose evidence cites `eid`, oldest first."""
    from halo_harness.outcomes.evidence import load
    from halo_harness.outcomes.records import read
    rows = []
    for r in read(state_dir):
        if not r.get("cited") or not r.get("evidence"):
            continue
        ev = load(r["evidence"])
        if ev is not None and eid in (getattr(ev, "cited", None) or []):
            rows.append({k: r.get(k) for k in ("run", "task", "source", "bio", "model", "outcome", "ts")})
    return rows
