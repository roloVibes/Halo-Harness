"""halo_harness.packs.memory_meta -- a pack's memory entries with their
provenance, sharing and retention (Halo 3.2.0.0 R5; R2's namespace folders,
packs/memory.py).

An entry is a note `<name>.md` in its namespace folder
(`~/.halo/packs/.data/<id>/memory/<ns>/`) and, beside it, `<name>._meta.json`:

    {"source": "workflow run" | "bio" | "user", "run": "<run id>", "stage": "<stage id>",
     "written": "<UTC time>", "retention": "keep" | "days:<n>" | "run", "shared": ["<pack id>", ...]}

`ext.memory.write(namespace, text, provenance)` writes both (a stage's worker
gets its run and stage filled in from $HALO_ORCHESTRA_RUN / $HALO_ORCHESTRA_LANE).
Recall honours them: a pack reads its own namespace plus the entries another
pack shares with it (`visible`); `retention: run` entries go when their run
ends (`end_run`, from the run's report), `days:<n>` ones with `halo recall prune`.
A note without a `_meta.json` (R2's) is `{source: user, retention: keep}`.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N

META = "._meta.json"
SOURCES = ("workflow run", "bio", "user")
_DAYS = re.compile(r"^days:(\d{1,5})$")


def split_namespace(namespace) -> "tuple[str, str]":
    """`("doc-review", "reviews")` for `doc-review/reviews`; a bare id is its default namespace. ValueError otherwise."""
    pack_id, _, ns = str(namespace or "").partition("/")
    ns = ns or pack_id
    if not N.is_valid_pack_id(pack_id) or not N.is_valid_name(ns):
        raise ValueError(f"{namespace!r} is not a namespace: <pack id>/<name> (letters, digits, - and _)")
    return pack_id, ns


def meta_path(note: Path) -> Path:
    return Path(note).with_name(Path(note).stem + META)


def meta_of(note) -> dict:
    try:
        data = json.loads(meta_path(Path(note)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    return data if isinstance(data, dict) else {"source": "user", "retention": "keep", "shared": []}


def _run_and_stage() -> "tuple[str, str]":
    from halo_harness.orchestra import RUN_ENV
    run = os.environ.get(RUN_ENV) or ""
    if not run:
        return "", ""
    stage = ""
    try:
        goal = json.loads((Path(run) / "goal.json").read_text(encoding="utf-8"))
        lane = int(os.environ.get("HALO_ORCHESTRA_LANE") or 0)
        stage = str(((goal.get("workflow") or {}).get("jobs") or {}).get(f"job-{lane}", {}).get("stage") or "")
    except (OSError, ValueError):
        pass
    return Path(run).name, stage


def provenance(raw: Optional[dict] = None) -> "tuple[dict, list]":
    """The `_meta.json` for a new entry and the problems with `raw` (the caller's provenance)."""
    raw = dict(raw or {})
    run, stage = _run_and_stage()
    meta = {"source": raw.get("source") or ("workflow run" if run else "user"), "run": str(raw.get("run") or run),
            "stage": str(raw.get("stage") or stage), "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "retention": str(raw.get("retention") or "keep"), "shared": [str(p) for p in raw.get("shared") or []]}
    problems = [f"provenance: unknown key {k!r}" for k in raw if k not in ("source", "run", "stage", "retention", "shared")]
    if meta["source"] not in SOURCES:
        problems.append(f"provenance.source is one of {', '.join(SOURCES)}, got {meta['source']!r}")
    if meta["retention"] not in ("keep", "run") and not _DAYS.match(meta["retention"]):
        problems.append(f"provenance.retention is keep, days:<n> or run, got {meta['retention']!r}")
    if meta["retention"] == "run" and not meta["run"]:
        problems.append("provenance.retention run needs the run (written from a run's stage, or provenance.run)")
    problems += [f"provenance.shared: {p!r} is not a pack id" for p in meta["shared"] if not N.is_valid_pack_id(p)]
    return meta, problems


def write_entry(namespace, text: str, raw_provenance=None, *, name: Optional[str] = None, state_dir=None) -> Path:
    from halo_harness.packs.memory import namespace_dir
    from halo_harness.privateio import write_private_atomic
    pack_id, ns = split_namespace(namespace)
    meta, problems = provenance(raw_provenance)
    if name is not None and not N.is_valid_name(name):
        problems.append(f"name {name!r} is not a note name (letters, digits, - and _)")
    if problems:
        raise ValueError("; ".join(problems))
    folder = namespace_dir(f"{pack_id}/{ns}", state_dir=state_dir)
    note = folder / f"{name or time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(2)}.md"
    write_private_atomic(note, str(text))
    write_private_atomic(meta_path(note), json.dumps(meta, indent=2) + "\n")
    return note


def entries(namespace, *, state_dir=None) -> "list[dict]":
    """Every note of one namespace: `{path, name, meta}`, by name."""
    from halo_harness.packs.memory import namespace_dir
    pack_id, ns = split_namespace(namespace)
    folder = namespace_dir(f"{pack_id}/{ns}", state_dir=state_dir)
    return [{"path": p, "name": p.stem, "namespace": f"{pack_id}/{ns}", "meta": meta_of(p)}
            for p in sorted(folder.glob("*.md"))] if folder.is_dir() else []


def all_entries(*, state_dir=None) -> "list[dict]":
    from halo_harness.packs.memory import memory_sources, namespace_of_path
    return [{"path": Path(i), "name": Path(i).stem, "namespace": namespace_of_path(i, state_dir=state_dir),
             "meta": meta_of(i)} for i, *_ in memory_sources(state_dir=state_dir)]


def visible(entry_id: str, namespace: Optional[str], *, state_dir=None) -> bool:
    """recall's filter: yours (namespace None), the namespace's own entries, or one another pack shares with its pack."""
    from halo_harness.packs.memory import namespace_of_path
    own = namespace_of_path(entry_id, state_dir=state_dir)
    if own == (namespace or ""):
        return True
    if not namespace or not own:
        return False
    return namespace.partition("/")[0] in (meta_of(entry_id).get("shared") or [])


def readable(namespace, *, state_dir=None) -> "list[dict]":
    """The entries a pack's namespace reads: its own and every one shared with its pack."""
    pack_id, ns = split_namespace(namespace)
    mine = entries(namespace, state_dir=state_dir)
    shared = [e for e in all_entries(state_dir=state_dir) if e["namespace"].partition("/")[0] != pack_id
              and pack_id in (e["meta"].get("shared") or [])]
    return mine + shared


def _drop(note: Path) -> None:
    for p in (note, meta_path(note)):
        try:
            p.unlink()
        except OSError:
            pass


def end_run(run_id: str, *, state_dir=None) -> int:
    """The run ended: its `retention: run` entries go. Returns how many."""
    gone = [e for e in all_entries(state_dir=state_dir) if e["meta"].get("retention") == "run" and e["meta"].get("run") == run_id]
    for e in gone:
        _drop(e["path"])
    return len(gone)


def prune(*, state_dir=None, now: Optional[float] = None) -> "list[dict]":
    """`halo recall prune`: every `days:<n>` entry older than n days goes. Returns them."""
    import calendar
    now = time.time() if now is None else now
    gone = []
    for e in all_entries(state_dir=state_dir):
        m = _DAYS.match(str(e["meta"].get("retention") or ""))
        try:
            written = calendar.timegm(time.strptime(str(e["meta"].get("written")), "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            continue
        if m and now - written > int(m.group(1)) * 86400:
            _drop(e["path"])
            gone.append(e)
    return gone
