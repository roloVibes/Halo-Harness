"""halo_harness.fleet.mission_store -- a mission's folder on disk (Halo 3.0.6.0
"Fleet Missions" round R7).

    <missions root>/<id>/
        mission.json        the mission document (fleet/mission.py): state, parts' progress, decisions
        MISSION.md          the goal, constraints, the plan as a table, who does what and why
        plan.json           the plan (fleet/mission_plan.py)
        claims.json         {part: [repo-relative paths or globs]}: what each part may edit
        parts/<n>/brief.md      the part's brief
        parts/<n>/handback.md   what its worker said when it finished
        parts/<n>/result.json   {ok, state, cost_usd, error, session_id, files, branch, bundle?}
        parts/<n>/branch.bundle a repo part's branch (git bundle), pushed by a member
        inputs/             files every part may read
        artifacts/<n>/      what a part made (non-repo outputs)
        log.jsonl           every event: {ts, kind, ...}
        report.md, report.json

The missions root is `<home>/fleet/missions`, or `fleet.shared_dir` when that
is set (a mount every machine sees). What only this machine may know (the
repo's full path, worktree paths) lives outside the folder, in
`<home>/fleet/missions-local/<id>.json`, so it never reaches a member or a
share. `confine(folder, rel)` is the one path check every route uses:
relative, no `..`, no drive or root, no symlink on the way.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import mission as M
from halo_harness.orchestra import jsonl

DOC = "mission.json"
SUBDIRS = ("parts", "inputs", "artifacts")


class PathRefused(ValueError):
    pass


def root(home) -> Path:
    shared = M.shared_dir(home)
    return shared if shared is not None else Path(home) / "fleet" / "missions"


def folder(home, mid: str) -> Path:
    if not M.valid_id(mid):
        raise M.MissionError(f"{mid!r} is not a mission id (m-<yyyymmdd>-<4 hex>)", 404)
    return root(home) / mid


def local_path(home, mid: str) -> Path:
    return Path(home) / "fleet" / "missions-local" / f"{mid}.json"


def local(home, mid: str) -> dict:
    data = jsonl.read_json(local_path(home, mid), {})
    return data if isinstance(data, dict) else {}


def set_local(home, mid: str, **fields) -> dict:
    path = local_path(home, mid)
    with jsonl.locked(path):
        data = local(home, mid)
        data.update(fields)
        jsonl.write_json(path, data)
    return data


def create(home, doc: dict) -> Path:
    base = root(home)
    if M.shared_dir(home) is None:
        from halo_harness.privateio import ensure_private_dir
        base.mkdir(parents=True, exist_ok=True)
        ensure_private_dir(base.parent)
    d = folder(home, doc["id"])
    d.mkdir(parents=True, exist_ok=False)
    for sub in SUBDIRS:
        (d / sub).mkdir(exist_ok=True)
    jsonl.write_json(d / DOC, doc)
    (d / "log.jsonl").write_text("", encoding="utf-8")
    log(home, doc["id"], "drafted", goal=doc.get("goal"), by=doc.get("by"))
    return d


def load(home, mid: str) -> Optional[dict]:
    try:
        return load_at(folder(home, mid), mid)
    except M.MissionError:
        return None


def load_at(base, mid: Optional[str] = None) -> Optional[dict]:
    """mission.json of the mission folder `base` (its id checked against `mid`, else the folder's name)."""
    path, mid = Path(base) / DOC, mid or Path(base).name
    for _ in range(20):  # on Windows a reader can meet the file mid-replace: try again for a moment
        data = jsonl.read_json(path, None)
        if isinstance(data, dict) and data.get("id") == mid:
            return data
        if not path.exists() and not path.parent.is_dir():
            return None
        time.sleep(0.02)
    return None


def need(home, mid: str) -> dict:
    doc = load(home, mid)
    if doc is None:
        raise M.MissionError(f"no mission {mid!r} here", 404)
    return doc


def update(home, mid: str, fn: Callable[[dict], object]) -> dict:
    """Read-modify-write `mission.json` under its lock; `fn(doc)` changes the doc in place."""
    return update_at(folder(home, mid), fn, mid)


def update_at(base, fn: Callable[[dict], object], mid: Optional[str] = None, *, stamp: bool = True) -> dict:
    """`update` on the mission folder `base` (3.1.2.0 R1: work/adapters/part.py writes a part's state
    through it); `stamp=False` keeps `updated` as it is (a part written back unchanged)."""
    path, mid = Path(base) / DOC, mid or Path(base).name
    with jsonl.locked(path):
        doc = load_at(base, mid)
        if doc is None:
            raise M.MissionError(f"no mission {mid!r} here", 404)
        fn(doc)
        if stamp:
            doc["updated"] = time.time()
        jsonl.write_json(path, doc)
    return doc


def all_docs(home) -> list:
    base = root(home)
    try:
        names = sorted(p.name for p in base.iterdir() if p.is_dir() and M.valid_id(p.name))
    except OSError:
        return []
    docs = [load(home, n) for n in names]
    return sorted([d for d in docs if d], key=lambda d: float(d.get("created") or 0))


def log(home, mid: str, kind: str, **fields) -> dict:
    entry = {"ts": round(time.time(), 3), "kind": kind, **{k: v for k, v in fields.items() if v is not None}}
    try:
        path = folder(home, mid) / "log.jsonl"
        with jsonl.locked(path):
            jsonl.append_line(path, entry)
    except (OSError, M.MissionError):
        pass
    return entry


def read_log(home, mid: str, kinds=None) -> list:
    rows = jsonl.read_lines(folder(home, mid) / "log.jsonl")
    want = set(kinds) if kinds else None
    return [r for r in rows if want is None or r.get("kind") in want]


# ---- paths inside a mission folder ------------------------------------------------------

def clean_rel(rel) -> str:
    """`rel` as a forward-slash relative path; PathRefused for anything that could leave the folder."""
    p = str(rel or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if not parts:
        raise PathRefused("a path inside the mission folder is required")
    if p.startswith("/") or ":" in parts[0] or any(x == ".." for x in parts) or "\x00" in p:
        raise PathRefused(f"{rel!r} is not a path inside the mission folder (relative, no `..`)")
    return "/".join(parts)


def confine(base, rel) -> Path:
    """The file `rel` names inside `base`; PathRefused when it climbs out or passes a symlink."""
    base = Path(base)
    clean = clean_rel(rel)
    cur = base
    for part in clean.split("/"):
        cur = cur / part
        if cur.is_symlink():
            raise PathRefused(f"{clean} passes a symbolic link; links are not followed")
    try:
        cur.resolve().relative_to(base.resolve())
    except (ValueError, OSError):
        raise PathRefused(f"{clean} is outside the mission folder") from None
    return cur


def write_text(base, rel: str, text: str) -> Path:
    path = confine(base, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_text(base, rel: str, limit: int = 2_000_000) -> Optional[str]:
    try:
        path = confine(base, rel)
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", errors="replace")
    except (OSError, PathRefused):
        return None


def files(base, prefix: str = "") -> list:
    """`[{path, size, mtime}]` of every regular file under `base` (or under its `prefix`), links skipped."""
    base = Path(base)
    start = confine(base, prefix) if prefix else base
    out = []
    if not start.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(start, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink() or not p.is_file() or name.endswith((".tmp", ".lock")):
                continue
            st = p.stat()
            out.append({"path": p.relative_to(base).as_posix(), "size": st.st_size, "mtime": round(st.st_mtime, 3)})
    return out
