"""halo_harness.fleet.mission_files -- a mission's shared folder over the
signed fleet protocol (Halo 3.0.6.0 "Fleet Missions" round R7).

Hub port route `POST /fleet/v1/mission_files` (signed like every member
request, fleet/hub_mission.py), body `{v, op: list | get | put, mission,
path?, data_b64?}`:

    list  -> {files: [{path, size, mtime}]}       what this member may read
    get   -> {path, size, data_b64}               one file it may read
    put   -> {ok, path, size}                     one file it may write; 413 past fleet.mission.max_file_mb

A member reaches only a mission it has a part in (403 otherwise). It reads
`MISSION.md`, `claims.json`, `inputs/**`, its own `parts/<n>/**` and
`artifacts/<n>/**`, and the hand-backs and artifacts of the parts its parts
depend on; it writes only its own `parts/<n>/handback.md | result.json |
branch.bundle` and `artifacts/<n>/**`. Every path goes through
mission_store.confine: relative, no `..`, no symlink followed.

`HubFiles(entry)` is the member's side: `pull(mission, part, dest)` before a
part runs, `push(mission, part, src, rels)` after. With `fleet.shared_dir`
set nothing is mirrored (mission_worker.py decides).
"""

from __future__ import annotations

import base64
import fnmatch
import os
import tempfile
from pathlib import Path
from typing import Optional

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet import protocol

PART_FILES = ("handback.md", "result.json", "branch.bundle")
TIMEOUT_S = 120.0


def _parts_of(doc: dict, plan: dict, hid: str) -> "tuple[list, list]":
    mine = [pid for pid, p in (doc.get("parts") or {}).items() if str(p.get("harness")) == str(hid)]
    deps = sorted({d for p in (plan or {}).get("parts") or [] if p.get("id") in mine for d in p.get("depends_on") or []})
    return mine, deps


def readable(rel: str, mine: list, deps: list) -> bool:
    pats = ["MISSION.md", "claims.json", "inputs/**"]
    pats += [f"parts/{n}/**" for n in mine] + [f"artifacts/{n}/**" for n in mine]
    pats += [f"parts/{d}/handback.md" for d in deps] + [f"artifacts/{d}/**" for d in deps]
    return any(fnmatch.fnmatchcase(rel, p) for p in pats)


def writable(rel: str, mine: list) -> bool:
    return any(rel in (f"parts/{n}/{f}" for f in PART_FILES) or fnmatch.fnmatchcase(rel, f"artifacts/{n}/**")
               for n in mine)


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def serve(home, hid: str, body: dict) -> "tuple[int, dict]":
    """One signed request from member `hid`: `(status, reply)`."""
    from halo_harness.fleet.mission_plan import load_plan
    op, mid = str(body.get("op") or ""), str(body.get("mission") or "")
    if op not in ("list", "get", "put"):
        return 400, {"error": f"op is list, get or put, got {op!r}"}
    doc = S.load(home, mid) if M.valid_id(mid) else None
    if doc is None:
        return 404, {"error": f"no mission {mid!r} on this hub"}
    mine, deps = _parts_of(doc, load_plan(home, mid) or {}, hid)
    if not mine:
        return 403, {"error": f"this harness has no part in mission {mid}"}
    base, cap = S.folder(home, mid), M.max_file_bytes(home)
    if op == "list":
        return 200, {"files": [f for f in S.files(base) if readable(f["path"], mine, deps)]}
    try:
        rel = S.clean_rel(body.get("path"))
        path = S.confine(base, rel)
    except S.PathRefused as e:
        return 400, {"error": str(e)}
    if op == "get":
        if not readable(rel, mine, deps):
            return 403, {"error": f"{rel} is not this harness's to read"}
        if not path.is_file():
            return 404, {"error": f"no file {rel} in mission {mid}"}
        if path.stat().st_size > cap:
            return 413, {"error": f"{rel} is larger than fleet.mission.max_file_mb"}
        data = path.read_bytes()
        return 200, {"path": rel, "size": len(data), "data_b64": base64.b64encode(data).decode("ascii")}
    if not writable(rel, mine):
        return 403, {"error": f"{rel} is not this harness's to write (its own parts/<n>/ files and artifacts/<n>/)"}
    try:
        data = base64.b64decode(str(body.get("data_b64") or ""), validate=True)
    except ValueError:
        return 400, {"error": "data_b64 is not base64"}
    if len(data) > cap:
        return 413, {"error": f"{rel} is {len(data)} bytes; fleet.mission.max_file_mb allows {cap}"}
    _atomic(path, data)
    S.log(home, mid, "file_put", path=rel, size=len(data), harness=hid)
    return 200, {"ok": True, "path": rel, "size": len(data)}


class HubFiles:
    """The member's side: signed calls to the hub that sent the part."""

    def __init__(self, entry: dict, timeout: float = TIMEOUT_S) -> None:
        from halo_harness.fleet import identity, store
        from halo_harness.fleet.relay import HubLink
        key = store.key_for(entry)
        if key is None:
            raise RuntimeError("the pair key for this hub is missing; `halo fleet join` it again")
        self.link = HubLink(entry, key, identity.harness()["id"], timeout=timeout)

    def call(self, op: str, mission: str, **fields) -> dict:
        return self.link.request("POST", protocol.PREFIX + "/mission_files", protocol.doc(op=op, mission=mission, **fields))

    def pull(self, mission: str, dest) -> list:
        """Every file this harness may read, written under `dest`; the paths."""
        got = []
        for f in self.call("list", mission).get("files") or []:
            one = self.call("get", mission, path=f["path"])
            _atomic(S.confine(dest, one["path"]), base64.b64decode(one.get("data_b64") or ""))
            got.append(one["path"])
        return got

    def push(self, mission: str, src, rels: list, cap: Optional[int] = None) -> "tuple[list, list]":
        """`(sent, skipped)`: each of `rels` under `src` sent to the hub (a file over the cap is skipped)."""
        sent, skipped = [], []
        for rel in rels:
            path = S.confine(src, rel)
            if not path.is_file():
                continue
            data = path.read_bytes()
            if cap is not None and len(data) > cap:
                skipped.append(rel)
                continue
            self.call("put", mission, path=rel, data_b64=base64.b64encode(data).decode("ascii"))
            sent.append(rel)
        return sent, skipped

    def close(self) -> None:
        self.link.close()
