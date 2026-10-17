"""halo_harness.team.blocks -- a block's ledger: who holds which part of it
and every write that landed in it.

    <folder or git block>/.halo-block/       the ledger of a folder or git block
    <dir>/<name>.halo-block/                 the ledger of a file block <dir>/<name>
        claims.jsonl    orchestra/claims.py's ClaimLog, keys by the block's mode:
                        section  `section:<relpath>` (a whole file) or
                                 `section:<relpath>#<heading-slug>` (a markdown
                                 heading, a function or class elsewhere)
                        file     `file:<relpath>`
                        none     no claims; writes are only logged
        changes.jsonl   one line per write: {ts, by, member, stage, op, key, summary}
        state.json      {block, last_change, holders: {holder: [keys]}}

`<relpath>` is relative to the block (a file block: the file's name). A
holder is `<member>@<stage>`. The ledger folder carries a `.gitignore` of
`*`, so it is never committed. `block_status(team, block_id)` is what
`halo team blocks` and `GET /api/team/blocks` show.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.claims import ClaimLog
from halo_harness.team import LEDGER_DIR
from halo_harness.team import spec as S

RECENT = 20


class BlockClaimLog(ClaimLog):
    """The ClaimLog of one block; its claim events go to the team run's log, not the ledger."""

    def _event(self, text: str, **data) -> None:
        return None


def block_root(root, block: dict) -> Path:
    """The folder a block's relative paths start from (a file block: the file's folder)."""
    path = (Path(root) / block["path"]).resolve()
    return path.parent if block["kind"] == "file" else path


def ledger_dir(root, block: dict) -> Path:
    path = (Path(root) / block["path"]).resolve()
    if block["kind"] == "file":
        return path.parent / f"{path.name}{LEDGER_DIR}"
    return path / LEDGER_DIR


def ensure_ledger(root, block: dict) -> Path:
    d = ledger_dir(root, block)
    d.mkdir(parents=True, exist_ok=True)
    ignore = d / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# a Halo team block ledger: never committed\n*\n", encoding="utf-8")
    return d


def claim_log(root, block: dict, clock=time.time) -> BlockClaimLog:
    return BlockClaimLog(ledger_dir(root, block), clock=clock)


def contains(root, block: dict, path) -> bool:
    target = Path(path).resolve()
    base = (Path(root) / block["path"]).resolve()
    if block["kind"] == "file":
        return target == base
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def block_for(team: dict, root, path) -> Optional[dict]:
    """The innermost block holding `path` (nested blocks: the innermost owns the file)."""
    hits = [b for b in team["blocks"] if b["path"] and contains(root, b, path)]
    return max(hits, key=lambda b: len((Path(root) / b["path"]).resolve().parts), default=None)


def rel_in(root, block: dict, path) -> str:
    return Path(path).resolve().relative_to(block_root(root, block)).as_posix()


def key_prefix(block: dict) -> str:
    return {"section": "section:", "file": "file:"}.get(block["claims"], "")


def keys_for(root, block: dict, path, tool_name: str = "Write", tool_input: Optional[dict] = None) -> "list[str]":
    """The claim keys a write to `path` touches (the bare relpath under `claims: none`)."""
    rel = rel_in(root, block, path)
    if block["claims"] != "section" or tool_name not in ("Edit", "MultiEdit"):
        return [key_prefix(block) + rel]
    from halo_harness.orchestra.guard import ClaimGuard
    from halo_harness.orchestra.index import index_file, units_for_lines
    lines = ClaimGuard.touched_lines(tool_name, tool_input or {}, Path(path))
    if lines is None:
        return [key_prefix(block) + rel]
    units = units_for_lines(index_file(path, root=block_root(root, block)), lines)
    return [key_prefix(block) + u.key for u in units] or [key_prefix(block) + rel]


def holder_of(member: str, stage: str) -> str:
    return f"{member}@{stage}"


def holders(log: ClaimLog, now: Optional[float] = None) -> dict:
    out: dict = {}
    for c in log.active(now).values():
        out.setdefault(c.holder, []).append(c.key)
    return {h: sorted(k) for h, k in sorted(out.items())}


def write_state(root, block: dict, log: Optional[ClaimLog] = None, last_change: Optional[dict] = None) -> dict:
    d = ensure_ledger(root, block)
    log = log or claim_log(root, block)
    old = jsonl.read_json(d / "state.json", {}) or {}
    state = {"block": block["id"], "last_change": last_change if last_change is not None else old.get("last_change"),
             "holders": holders(log)}
    jsonl.write_json(d / "state.json", state)
    return state


def record_change(root, block: dict, *, by: str, member: str, stage: str, op: str, key: str,
                  summary: str, clock=time.time) -> dict:
    """One changes.jsonl line, and state.json's `last_change` moves to it."""
    d = ensure_ledger(root, block)
    line = {"ts": round(clock(), 3), "by": by, "member": member, "stage": stage, "op": op, "key": key,
            "summary": summary[:300]}
    with jsonl.locked(d / "changes.jsonl"):
        jsonl.append_line(d / "changes.jsonl", line)
    write_state(root, block, last_change=line)
    return line


def changes(root, block: dict, since: int = 0) -> list:
    return jsonl.read_lines(ledger_dir(root, block) / "changes.jsonl")[max(0, int(since)):]


def release_holder(root, block: dict, holder: str, note: str = "the stage ended") -> "list[str]":
    """Let go of every live claim `holder` has in the block; returns the keys."""
    log = claim_log(root, block)
    keys = [c.key for c in log.active().values() if c.holder == holder]
    for key in keys:
        log.release(holder, key, note)
    if keys:
        write_state(root, block, log)
    return keys


def block_status(team: dict, block_id: str, recent: int = RECENT) -> Optional[dict]:
    """`{id, kind, path, claims, ledger, exists, holders: [{key, holder, state, expires}],
    last_change, changes_count, recent: [last change lines]}`; None for an unknown id."""
    block = S.block_by_id(team, block_id)
    if block is None:
        return None
    root = Path(team["root"])
    log = claim_log(root, block)
    lines = changes(root, block)
    live = sorted(log.active().values(), key=lambda c: c.key)
    return {"id": block["id"], "kind": block["kind"], "path": block["path"], "claims": block["claims"],
            "ledger": str(ledger_dir(root, block)), "exists": (root / block["path"]).exists(),
            "holders": [{"key": c.key, "holder": c.holder, "state": c.state, "expires": round(c.expires, 3)}
                        for c in live],
            "last_change": lines[-1] if lines else None, "changes_count": len(lines),
            "recent": lines[-max(0, int(recent)):] if recent else []}


def all_status(team: dict, recent: int = 5) -> list:
    return [block_status(team, b["id"], recent) for b in team["blocks"]]
