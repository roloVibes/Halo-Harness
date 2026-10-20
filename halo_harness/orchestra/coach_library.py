"""halo_harness.orchestra.coach_library -- the improvement library (Halo
3.1.6.0 R3, after Google's Harness²: an adopted harness plus an EXPERIENCE
file). Every Apply -- a card's single change, or a probe card's group --
becomes one entry in the state dir's `coach/library/`:

    ~/.halo/coach/library/<entry>/        <entry> = e-<YYYYMMDD>-<4 hex>
        entry.json      {id, ts, run, run_dir, kind, project: {name, remote}, lineup,
                         goal: {what, done_when}, source: apply|probe, pick?, title,
                         apply_ids, files: [{path, scope: home|repo|other, target, name, fields, bytes, kept}],
                         changes: [{target, name, field, value}], undone: false, from?: <harness>}
        overlay.json    the composed overlay (a probe), or the same shape built from the one change
        files/<path>    the written file's text after the Apply (each <= 64 KB; a bigger one is listed, not kept),
                        <path> relative to the halo home or the repo's .halo
        EXPERIENCE.md   when it applies, the lessons, the evidence, the files (orchestra/coach_experience.py)

An Undo of the apply (or the group) marks the entry `undone: true`; it stays
on disk and is never cited. The next run still starts from the base lineup:
an entry is reused only through the coach's proposals
(orchestra/coach_citations.py), never inherited. `matches(run_dir)` is the
citation rule (coach_citations.matches).
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from pathlib import Path, PurePosixPath
from typing import Optional

from halo_harness.orchestra import coach_record as R
from halo_harness.orchestra import jsonl

LIBRARY, ENTRY, OVERLAY, EXPERIENCE, FILES = "library", "entry.json", "overlay.json", "EXPERIENCE.md", "files"
FILE_CAP = 64 * 1024
ID_RE = re.compile(r"^e-\d{8}-[0-9a-f]{4}$")


def folder(state_dir=None) -> Path:
    return R.folder(state_dir) / LIBRARY


def valid_id(entry) -> bool:
    return bool(ID_RE.match(str(entry or "")))


def entry_dir(entry: str, state_dir=None) -> Path:
    if not valid_id(entry):
        raise ValueError(f"{entry!r} is not a library entry id (e-<yyyymmdd>-<4 hex>)")
    return folder(state_dir) / entry


def new_id(state_dir=None) -> str:
    while True:
        eid = f"e-{time.strftime('%Y%m%d')}-{secrets.token_hex(2)}"
        if not (folder(state_dir) / eid).exists():
            return eid


def read(entry: str, state_dir=None) -> Optional[dict]:
    try:
        data = jsonl.read_json(entry_dir(entry, state_dir) / ENTRY, None)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def entries(state_dir=None) -> list:
    """Every entry.json of the library, newest first."""
    base = folder(state_dir)
    rows = [jsonl.read_json(p / ENTRY, None) for p in base.iterdir() if valid_id(p.name)] if base.is_dir() else []
    return sorted([r for r in rows if isinstance(r, dict) and valid_id(r.get("id"))],
                  key=lambda r: (-float(r.get("ts") or 0), str(r.get("id"))))


def text_of(entry: str, name: str, state_dir=None) -> str:
    try:
        return (entry_dir(entry, state_dir) / name).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def stored_files(entry: str, state_dir=None) -> dict:
    """{<path>: text} under the entry's files/."""
    base = entry_dir(entry, state_dir) / FILES
    return {p.relative_to(base).as_posix(): p.read_bytes().decode("utf-8", errors="replace")
            for p in sorted(base.rglob("*")) if p.is_file()} if base.is_dir() else {}


def safe_rel(path: str) -> Optional[str]:
    """A stored file's path as written under files/: relative, posix, no `..`; None otherwise."""
    p = PurePosixPath(str(path or "").replace("\\", "/"))
    if not p.parts or p.is_absolute() or ".." in p.parts or ":" in p.parts[0]:
        return None
    return p.as_posix()


def write(doc: dict, experience: str, overlay: dict, files: dict, state_dir=None) -> Path:
    """One entry folder from its parts (Apply here, or a fetch from another harness); never over an existing one."""
    out = entry_dir(doc["id"], state_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    for rel, text in (files or {}).items():
        rel = safe_rel(rel)
        if rel is not None:
            (out / FILES / rel).parent.mkdir(parents=True, exist_ok=True)
            R.write_exact(out / FILES / rel, str(text))
    R.write_exact(out / OVERLAY, json.dumps(overlay or {}, indent=2, ensure_ascii=False, default=str) + "\n")
    R.write_exact(out / EXPERIENCE, experience)
    R.write_exact(out / ENTRY, json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n")
    return out


def _rel(file: str, repo: Optional[Path], state_dir) -> "tuple[str, str]":
    from halo_harness.config.paths import bridge_home
    p = Path(file).resolve()
    for scope, base in (("home", Path(state_dir) if state_dir is not None else bridge_home()),
                        ("repo", (repo / ".halo") if repo else None)):
        if base is None:
            continue
        try:
            return scope, p.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return "other", p.name


def _rows(applied: dict, state_dir) -> list:
    ids = {applied.get("apply_id")} | set(applied.get("rows") or [])
    group = applied.get("group")
    return [r for r in R.applies(state_dir) if r.get("apply_id") in ids or (group and r.get("group") == group)]


def born(result: dict, s: dict, run_dir, applied: dict, *, cwd=None, state_dir=None) -> Optional[str]:
    """The entry an Apply makes (its id), from the card, the apply's record rows and, for a probe card, probe.json."""
    from halo_harness.orchestra import coach_experience as X
    rows = _rows(applied, state_dir)
    if not rows:
        return None
    kind = result.get("kind") or rows[0].get("kind") or ""
    probe = None
    if (s.get("apply") or {}).get("target") == "overlay":
        from halo_harness.orchestra.coach_probe import read as read_probe
        probe = read_probe(run_dir) or {}
    repo = X.repo_of(run_dir, kind, cwd)
    files, kept = [], {}
    for r in rows:
        scope, rel = _rel(r["file"], repo, state_dir)
        text = r.get("after") or ""
        fields = r["value"] if r.get("value") and isinstance(r["value"], list) and r.get("group") else [[r["field"], r["value"]]]
        size = len(text.encode("utf-8"))
        files.append({"path": rel, "scope": scope, "target": r.get("target"), "name": r.get("name"), "fields": fields,
                      "bytes": size, "kept": size <= FILE_CAP})
        if size <= FILE_CAP:
            kept[rel] = text
    changes = list(((probe or {}).get("apply") or {}).get("changes") or []) if probe is not None else \
        [{"target": r.get("target"), "name": r.get("name"), "field": r.get("field"), "value": r.get("value")} for r in rows]
    ctx = X.context_of(run_dir, kind)
    doc = {"id": new_id(state_dir), "ts": round(time.time(), 3), "run": result.get("run"),
           "run_dir": str(Path(run_dir).resolve()), "kind": kind, "project": X.project_of(run_dir, kind, cwd),
           "lineup": ctx["lineup"], "goal": ctx["goal"], "source": "probe" if probe is not None else "apply",
           "card": s.get("id"), "title": X.title_of(s, probe),
           "apply_ids": [x for x in dict.fromkeys([applied.get("apply_id")] + [r["apply_id"] for r in rows]) if x],
           "files": files, "changes": changes, "undone": False}
    if probe is not None:
        doc["pick"] = probe.get("pick")
    write(doc, X.markdown(doc, s, probe), X.overlay_of(s, changes, probe), kept, state_dir)
    return doc["id"]


def mark_undone(apply_id: Optional[str], state_dir=None) -> list:
    """Every entry an undone apply (or group) made: `undone: true` (kept on disk, never cited). Their ids."""
    done = []
    for e in entries(state_dir) if apply_id else []:
        if apply_id in (e.get("apply_ids") or []) and not e.get("undone"):
            e.update(undone=True, undone_ts=round(time.time(), 3))
            R.write_exact(entry_dir(e["id"], state_dir) / ENTRY, json.dumps(e, indent=2, ensure_ascii=False, default=str) + "\n")
            done.append(e["id"])
    return done


def forget(entry: str, state_dir=None) -> bool:
    """Delete the entry's folder; False when there is none."""
    path = entry_dir(entry, state_dir)
    if not (path / ENTRY).is_file():
        return False
    shutil.rmtree(path)
    return True


def matches(run_dir, state_dir=None, limit: int = 3, *, cwd=None) -> list:
    """The entries the coach cites for this run (orchestra/coach_citations.py has the rule)."""
    from halo_harness.orchestra.coach_citations import matches as cite_matches
    return cite_matches(run_dir, state_dir, limit, cwd=cwd)
