"""halo_harness.recall -- Halo 2.0.7: semantic search over auto-memory and
past sessions (`/recall <query>` in the TUI, `halo recall <query>` on the
CLI), on the LOCAL embedding model (providers/embeddings.py).

The index lives at `<state_dir>/index/embeddings.jsonl` -- one JSON object
per line: {"id": <abs path>, "kind": "memory"|"session", "title",
"mtime": float, "vec": [...]}. Incremental: an entry whose source file's
mtime matches is skipped (re-embedding costs a real local call); entries
whose source vanished are pruned. Sessions are indexed from their log
files (`<state_dir>/sessions/**/*.jsonl`) by title/first-prompt/last-
answer; memory topics by their rendered index text.

Everything here is best-effort and DISABLED until embeddings are
configured: `search()` returns [] and the index is never built.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

from halo_harness.config.paths import bridge_home

_MAX_SESSION_BYTES = 8 * 1024 * 1024
_SESSION_SNAPSHOT_CHARS = 1200


def _index_path(state_dir) -> Path:
    base = Path(state_dir) if state_dir is not None else bridge_home()
    d = base / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d / "embeddings.jsonl"


def _load_index(path: Path) -> dict:
    entries: dict = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("id") and obj.get("vec"):
                entries[obj["id"]] = obj
    return entries


def _save_index(path: Path, entries: dict) -> None:
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                           for e in entries.values()), encoding="utf-8")
    tmp.replace(path)


def _memory_sources(cwd) -> list:
    """(id, title, text, mtime) for every auto-memory topic file."""
    try:
        from halo_harness.config.memory import MemoryStore
        from halo_harness.config.settings import resolve_settings
        store = MemoryStore(cwd, resolve_settings(cwd))
        out = []
        for entry in store.entries():
            p = Path(entry.path)
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            out.append((str(p), entry.name or p.stem, text, p.stat().st_mtime))
        return out
    except Exception:
        return []


def _session_sources(state_dir) -> list:
    """(id, title, text, mtime) for every session log -- the title, the
    first real user prompt, and the last assistant answer, bounded."""
    base = Path(state_dir) if state_dir is not None else bridge_home()
    sessions_dir = base / "sessions"
    out = []
    if not sessions_dir.exists():
        return out
    for path in sorted(sessions_dir.rglob("*.jsonl")):
        try:
            if path.stat().st_size > _MAX_SESSION_BYTES:
                continue
            title, first_prompt, last_answer = None, None, None
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    node = json.loads(line)
                except ValueError:
                    continue
                ntype = node.get("type")
                if ntype == "meta" and title is None and node.get("title"):
                    title = node["title"]
                elif ntype == "user" and node.get("kind") is None and first_prompt is None:
                    for b in node.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                            first_prompt = b["text"]
                            break
                elif ntype == "assistant":
                    for b in node.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                            last_answer = b["text"]
                if first_prompt and title and last_answer:
                    break
            text = "\n".join(x for x in (title, first_prompt, last_answer) if x)
            if text.strip():
                out.append((str(path), title or path.stem, text[:_SESSION_SNAPSHOT_CHARS],
                            path.stat().st_mtime))
        except OSError:
            continue
    return out


def build_index(state_dir=None, *, cwd=None, force: bool = False) -> dict:
    """Refresh the index incrementally. Returns a small report
    {"embedded": n, "total": n, "pruned": n, "enabled": bool}."""
    from halo_harness.providers.embeddings import embeddings_enabled
    if not embeddings_enabled():
        return {"enabled": False, "embedded": 0, "total": 0, "pruned": 0}

    path = _index_path(state_dir)
    existing = _load_index(path)
    sources = _memory_sources(cwd or Path.cwd())
    sources += _session_sources(state_dir)

    live_ids = {sid for sid, *_ in sources}
    pruned = [sid for sid in existing if sid not in live_ids]
    for sid in pruned:
        existing.pop(sid, None)

    to_embed = []
    for sid, title, text, mtime in sources:
        old = existing.get(sid)
        if old is not None and not force and old.get("mtime") == mtime:
            old["title"] = title
            continue
        to_embed.append((sid, title, text, mtime))

    embedded = 0
    BATCH = 16
    for i in range(0, len(to_embed), BATCH):
        chunk = to_embed[i:i + BATCH]
        from halo_harness.providers.embeddings import embed_texts
        vecs = embed_texts([f"{t}\n{x}" for _, t, x, _ in chunk])
        if vecs is None:
            break  # transport down -- keep whatever is already indexed
        for (sid, title, _text, mtime), vec in zip(chunk, vecs):
            if not vec:
                continue
            existing[sid] = {"id": sid, "kind": ("memory" if sid.endswith(".md") else "session"),
                             "title": title, "mtime": mtime, "vec": vec}
            embedded += 1

    _save_index(path, existing)
    return {"enabled": True, "embedded": embedded, "total": len(existing), "pruned": len(pruned)}


def search(query: str, *, state_dir=None, k: int = 8, refresh: bool = True) -> list:
    """Ranked `[{id, kind, title, score}]` for `query` (newest-index
    first on ties). Empty list when embeddings are disabled/unavailable."""
    if not query.strip():
        return []
    from halo_harness.providers.embeddings import cosine, embed_texts, embeddings_enabled
    if not embeddings_enabled():
        return []
    if refresh:
        build_index(state_dir)
    entries = _load_index(_index_path(state_dir))
    if not entries:
        return []
    qvec = embed_texts([query])
    if not qvec or not qvec[0]:
        return []
    qvec = qvec[0]
    scored = [(cosine(qvec, e.get("vec")), e) for e in entries.values()]
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))
    return [{"id": e["id"], "kind": e.get("kind"), "title": e.get("title", ""), "score": round(s, 4)}
            for s, e in scored[:k] if s > 0.0]


def rank_memory_topics(query: str, *, state_dir=None) -> Optional[list]:
    """`/recall`'s memory half as a standalone ranking: the session's
    topic-file ids ordered by similarity to `query` (None when embeddings
    are off). Used by callers that want "which memory topics matter for
    THIS question" without rendering search output."""
    hits = search(query, state_dir=state_dir, k=50)
    if not hits:
        return None
    return [h["id"] for h in hits if h.get("kind") == "memory"]


def _format(hits: list) -> str:
    if not hits:
        return "no matches (is the embedding model pulled? index built?)"
    lines = []
    for h in hits:
        icon = "memo" if h["kind"] == "memory" else "sess"
        lines.append(f"  {h['score']:+.3f} [{icon}] {h['title']}  ({h['id']})")
    return "\n".join(lines)


def cmd_recall(argv: list) -> int:
    """`halo recall <query> [--k N] [--no-refresh] [--build-only]`."""
    args = list(argv)
    k, refresh, build_only = 8, True, False
    rest = []
    while args:
        a = args.pop(0)
        if a == "--k" and args:
            try:
                k = max(1, int(args.pop(0)))
            except ValueError:
                pass
        elif a == "--no-refresh":
            refresh = False
        elif a == "--build-only":
            build_only = True
        else:
            rest.append(a)
    query = " ".join(rest).strip()

    from halo_harness.providers.embeddings import embeddings_enabled
    if not embeddings_enabled():
        print("recall: embeddings are not configured -- set embeddings.model in "
              "~/.halo/config.json (e.g. \"nomic-embed-text\", pulled on the default "
              "Ollama host) and retry")
        return 2
    if build_only:
        report = build_index(force=True)
        print(f"recall: index rebuilt -- {report['total']} entries "
              f"({report['embedded']} re-embedded, {report['pruned']} pruned)")
        return 0
    if not query:
        print("usage: halo recall <query> [--k N] [--no-refresh] [--build-only]", file=sys.stderr)
        return 2
    hits = search(query, k=k, refresh=refresh)
    print(_format(hits))
    return 0 if hits else 1
