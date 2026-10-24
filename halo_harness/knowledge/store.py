"""halo_harness.knowledge.store -- findings and decisions on disk (Halo 3.1.8.0
R4, docs/KNOWLEDGE.md "The files").

One Markdown file per entry, with a small front matter, under the state dir:

    <state>/knowledge/<kind>/<yyyy-mm>/<id>.md           kind: finding | decision
    <state>/knowledge/<kind>/<yyyy-mm>/<id>._meta.json   provenance, a pack memory entry's shape
        {source, run, stage, written, retention, shared} (packs/memory_meta.py), plus
        {from, harness_name, fetched, read_only: true} for an entry fetched over the fleet

    ---
    id: f-20261024-a1b2c3      f- a finding, d- a decision: <yyyymmdd>-<6 hex>
    kind: finding
    title: basket.py#total passes `python -m pytest -q` at 3f2a1b9c0d4e
    when: '2026-10-24T09:12:00Z'
    by: gate                    judge | gate | coach | supervisor | user | agent:<id>; <by>@<harness id> when fetched
    run: 20261024-090000-b0b1
    repo: basket
    evidence: ['tests: `python -m pytest -q` exit 0, 12 passed']
    confidence: checked         a finding: checked when an evidence line names a test run or a reproduction, else said
    alternatives: [...]         a decision: what else could have been chosen
    supersedes: f-20261023-...  the older entry this one replaces
    tags: [orchestra, gate]
    ---
    What / where / why, in plain prose.

An entry is never edited in place: `supersede` writes a new one naming the
old (the old stays on disk, listed as superseded and left out of recall);
`forget` removes the file and its `_meta.json` (the recall index prunes it);
`write` never overwrites an id that is here.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Optional

from halo_harness.knowledge.frontmatter import confidence, lines as _lines, one_line, parse, render, utc  # noqa: F401

KINDS = ("finding", "decision")
PREFIX = {"finding": "f", "decision": "d"}
ROLES = ("judge", "gate", "coach", "supervisor", "user")
ID_RE = re.compile(r"^([fd])-(\d{8})-([0-9a-f]{6})$")
ID_IN_TEXT = re.compile(r"(?<![\w-])([fd]-\d{8}-[0-9a-f]{6})(?![\w-])")
META = "._meta.json"
TITLE_CAP, BODY_CAP = 300, 20_000


class KnowledgeError(ValueError):
    """A knowledge entry that cannot be written, read or forgotten, with the reason."""


def root(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "knowledge"


def valid_id(eid) -> bool:
    return bool(ID_RE.match(str(eid or "")))


def kind_of_id(eid) -> Optional[str]:
    m = ID_RE.match(str(eid or ""))
    return {"f": "finding", "d": "decision"}[m.group(1)] if m else None


def valid_by(by) -> bool:
    role = str(by or "").split("@", 1)[0]
    return role in ROLES or (role.startswith("agent:") and len(role) > len("agent:"))


def path_of(eid: str, state_dir=None) -> Path:
    m = ID_RE.match(str(eid or ""))
    if not m:
        raise KnowledgeError(f"{eid!r} is not a knowledge id (f-<yyyymmdd>-<6 hex> or d-<yyyymmdd>-<6 hex>)")
    day = m.group(2)
    return root(state_dir) / kind_of_id(eid) / f"{day[:4]}-{day[4:6]}" / f"{eid}.md"


def meta_path(md) -> Path:
    return Path(md).with_name(Path(md).stem + META)


def new_id(kind: str, state_dir=None) -> str:
    while True:
        eid = f"{PREFIX[kind]}-{time.strftime('%Y%m%d')}-{secrets.token_hex(3)}"
        if not path_of(eid, state_dir).exists():
            return eid


def write(kind: str, title: str, *, body: str = "", evidence=(), by: str = "user", run: str = "", repo: str = "",
          alternatives=(), tags=(), supersedes: str = "", eid: Optional[str] = None, when: Optional[str] = None,
          meta: Optional[dict] = None, state_dir=None) -> dict:
    """Write one new entry and its `_meta.json`; the entry as `read` returns it. KnowledgeError with the reason."""
    from halo_harness.privateio import write_private_atomic
    if kind not in KINDS:
        raise KnowledgeError(f"a knowledge entry is a finding or a decision, got {kind!r}")
    title = one_line(title, TITLE_CAP)
    if not title:
        raise KnowledgeError("a knowledge entry needs a title: one line saying what was found or decided")
    if not valid_by(by):
        raise KnowledgeError(f"by is one of {', '.join(ROLES)} or agent:<id>, got {by!r}")
    eid = eid or new_id(kind, state_dir)
    if kind_of_id(eid) != kind:
        raise KnowledgeError(f"{eid!r} is not a {kind} id")
    if supersedes and not valid_id(supersedes):
        raise KnowledgeError(f"supersedes names no knowledge id: {supersedes!r}")
    path = path_of(eid, state_dir)
    if path.exists():
        raise KnowledgeError(f"{eid} is already here; an entry is never overwritten (supersede it instead)")
    ev = _lines(evidence)
    front = {"id": eid, "kind": kind, "title": title, "when": when or utc(), "by": str(by), "run": one_line(run, 120),
             "repo": one_line(repo, 200), "evidence": ev}
    if kind == "finding":
        front["confidence"] = confidence(ev)
    else:
        front["alternatives"] = _lines(alternatives)
    if supersedes:
        front["supersedes"] = supersedes
    front["tags"] = [one_line(t, 40).lower() for t in _lines(tags, 12)]
    text = str(body or "").strip()
    write_private_atomic(path, render(front, text[:BODY_CAP]))
    provenance = {"source": str(by).split("@", 1)[0].split(":", 1)[0], "run": front["run"], "stage": "",
                  "written": utc(), "retention": "keep", "shared": []}
    provenance.update(meta or {})
    write_private_atomic(meta_path(path), json.dumps(provenance, indent=2) + "\n")
    return read(eid, state_dir) or dict(front, body=text, path=str(path))


def _entry(path: Path) -> Optional[dict]:
    try:
        front, body = parse(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    if not valid_id(front.get("id")) or front.get("kind") not in KINDS:
        return None
    try:
        meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    meta = meta if isinstance(meta, dict) else {}
    out = {k: front.get(k) for k in ("id", "kind", "title", "when", "by", "run", "repo", "confidence", "supersedes")}
    out = {k: ("" if v is None else str(v)) for k, v in out.items()}
    out.update(evidence=_lines(front.get("evidence")), alternatives=_lines(front.get("alternatives")),
               tags=_lines(front.get("tags"), 12), body=body, path=str(path), meta=meta,
               read_only=bool(meta.get("read_only")))
    return out


def read(eid: str, state_dir=None) -> Optional[dict]:
    """The entry: its front matter, `body`, `path`, `meta` (its `_meta.json`) and `read_only`; None when not here."""
    if not valid_id(eid):
        return None
    path = path_of(eid, state_dir)
    entry = _entry(path) if path.is_file() else None
    return entry if entry and entry["id"] == eid else None


def entries(state_dir=None, *, kind: Optional[str] = None) -> list:
    """Every entry (or every one of `kind`), newest first, each with `superseded_by` ('' when it is current)."""
    base = root(state_dir)
    rows = []
    for k in ([kind] if kind else KINDS):
        folder = base / k
        for path in sorted(folder.glob("*/*.md")) if folder.is_dir() else []:
            entry = _entry(path)
            if entry is not None and entry["id"] == path.stem:
                rows.append(entry)
    newer = {r["supersedes"]: r["id"] for r in rows if r["supersedes"]}
    for r in rows:
        r["superseded_by"] = newer.get(r["id"], "")
    return sorted(rows, key=lambda r: (r["when"], r["id"]), reverse=True)


def current(state_dir=None, *, kind: Optional[str] = None) -> list:
    """The entries no other entry supersedes."""
    return [r for r in entries(state_dir, kind=kind) if not r["superseded_by"]]


def supersede(old: str, title: str, *, state_dir=None, **fields) -> dict:
    """A new entry of the old one's kind that names it in `supersedes` (the old one is never edited)."""
    entry = read(old, state_dir)
    if entry is None:
        raise KnowledgeError(f"no knowledge entry {old!r} here (halo knowledge list shows them)")
    later = next((r["id"] for r in entries(state_dir, kind=entry["kind"]) if r["supersedes"] == old), "")
    if later:
        raise KnowledgeError(f"{old} is already superseded by {later}: supersede {later} instead")
    fields.setdefault("run", entry["run"])
    fields.setdefault("repo", entry["repo"])
    return write(entry["kind"], title, supersedes=old, state_dir=state_dir, **fields)


def forget(eid: str, state_dir=None) -> bool:
    """Remove the entry's file and its `_meta.json`; False when it is not here."""
    if read(eid, state_dir) is None:
        return False
    path = path_of(eid, state_dir)
    for p in (path, meta_path(path)):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    return True
