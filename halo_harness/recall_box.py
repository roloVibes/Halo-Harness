"""halo_harness.recall_box -- the hits Studio's recall box shows (Halo 3.1.2.0 R3; 3.5.0.0: this machine's index
only).

`local_hits(query, k, home)` answers from this harness's OWN index (recall.py), each hit

    {"score": 0.8123, "title": "...", "kind": "memory|session|finding|decision|note|...", "excerpt": "<= 300 chars",
     "harness": "<name>"}

(3.1.8.0 R4: `finding` / `decision` hits add `ref` -- the entry's id, for `halo knowledge` -- `by` and `when`,
knowledge/sources.py). `SEARCH(query, k, home)` is the seam (None: recall.search over that home's index); the tests
swap it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

SEARCH: Optional[Callable] = None
EXCERPT_CHARS = 300
MAX_K = 20
_READ_CAP = 64_000


def clean_query(raw) -> str:
    return " ".join(str(raw or "").split())[:500]


def clamp_k(raw, default: int = 8) -> int:
    try:
        return max(1, min(MAX_K, int(raw)))
    except (TypeError, ValueError):
        return default


def _search(query: str, k: int, home) -> list:
    if SEARCH is not None:
        return list(SEARCH(query, k, home) or [])
    from halo_harness.recall import search
    return search(query, state_dir=home, k=k)


def _flat(text: str) -> str:
    return " ".join(str(text or "").split())[:EXCERPT_CHARS]


def _session_text(path: Path) -> str:
    """A session log's title and first prompt, read from its first few hundred lines."""
    import json
    title, prompt = "", ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh):
                if n > 400 or (title and prompt):
                    break
                try:
                    node = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(node, dict):
                    continue
                if node.get("type") == "meta" and node.get("title") and not title:
                    title = str(node["title"])
                elif node.get("type") == "user" and node.get("kind") is None and not prompt:
                    prompt = next((str(b.get("text")) for b in node.get("content") or []
                                   if isinstance(b, dict) and b.get("type") == "text" and b.get("text")), "")
    except OSError:
        return ""
    return prompt or title


def excerpt_of(hid: str, kind: str) -> "tuple[str, Optional[str]]":
    """`(excerpt, memory type)` read from the hit's own file on this box (the path never leaves it)."""
    path = Path(str(hid or ""))
    if not path.is_file():
        return "", None
    if kind == "session":
        return _flat(_session_text(path)), None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:_READ_CAP]
    except OSError:
        return "", None
    if kind == "coach_library":  # 3.1.6.0 R3: an entry's EXPERIENCE.md answers with its Lessons (the coach pack's files)
        part = (text.split("\n## Lessons", 1)[1:] or [""])[0].split("\n## ", 1)[0].splitlines()[1:]
        return _flat(" ".join(ln.strip()[2:] if ln.strip().startswith("- ") else ln.strip()
                              for ln in part if ln.strip())), None
    from halo_harness.config.frontmatter import parse
    front, body = parse(text)
    meta = front.get("metadata") if isinstance(front.get("metadata"), dict) else {}
    kind_word = front.get("type") or meta.get("type")
    return _flat(body), (str(kind_word).strip().lower() if kind_word else None)


def hits_of(raw: list, name: str, hide: set) -> "tuple[list, int]":
    """The index's hits as the box shows them: no id, no path; the hidden kinds dropped."""
    out, hidden = [], 0
    for h in raw:
        if not isinstance(h, dict):
            continue
        kind = str(h.get("kind") or "memory")
        if "excerpt" in h:
            excerpt, mtype = _flat(h.get("excerpt")), (str(h.get("type")).lower() if h.get("type") else None)
        else:
            excerpt, mtype = excerpt_of(str(h.get("id") or ""), kind)
        if kind in hide or (mtype and mtype in hide) or (kind in ("finding", "decision") and "knowledge" in hide):
            hidden += 1
            continue
        row = {"score": round(float(h.get("score") or 0.0), 4), "title": str(h.get("title") or "")[:200],
               "kind": kind, "excerpt": excerpt, "harness": name}
        if kind in ("finding", "decision"):  # 3.1.8.0 R4: the entry's id, who and when (knowledge/sources.py)
            from halo_harness.knowledge.sources import hit_fields
            row.update(hit_fields(str(h.get("id") or "")))
        out.append(row)
    return out, hidden


def local_hits(query: str, k: int, home=None) -> "tuple[list, str]":
    """This harness's own hits, and a note when there are none to give."""
    from halo_harness.peers import identity
    home = Path(home) if home is not None else identity.home()
    try:
        hits, _hidden = hits_of(_search(query, k, home), identity.harness_name(home), set())
    except Exception as e:  # a broken index never stops the answer
        return [], f"{type(e).__name__}: {e}"[:200]
    if not hits and SEARCH is None:
        from halo_harness.providers.embeddings import embeddings_enabled
        if not embeddings_enabled():
            return [], "embeddings are not configured here (embeddings.model)"
    return hits, ""


def merge(groups: list, k: int) -> list:
    """Every group's hits in one list, best score first (ties: harness, then title), at most k."""
    rows = [h for g in groups for h in g or []]
    rows.sort(key=lambda h: (-float(h.get("score") or 0.0), str(h.get("harness") or ""), str(h.get("title") or "")))
    return rows[:max(1, int(k))]
