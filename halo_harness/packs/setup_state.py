"""halo_harness.packs.setup_state -- where a pack's Setup blocks stand (Halo 3.3.11.0 R3; docs/EXTENSION_API.md
"Setup blocks").

    ~/.halo/packs/.data/<id>/setup.json
    {"blocks": {"prefs": {"state": "done", "at": "<UTC time>", "by": "studio"},
                "about": {"state": "skipped", "at": "...", "by": "studio"}}}

A block not in the file is untouched. A form is `done` once it was saved from Setup, a check once it ran green
through the checks job, a note once it was dismissed; any block may be `skipped`. The file lives in the pack's data
folder beside mode.json and its events log, is written only here (privately, atomically), and each change is the
pack's `setup` event in that log. It holds no value the blocks saved: a form's values are the pack's settings
(`packs.settings.<id>` in config.json), a check's lines are the job's frames.

    read(pack_id, state_dir=None) -> {block_id: {state, at, by}}
    mark(pack_id, block_id, state, *, by, state_dir=None) -> the block's record (state: done | skipped | "")
    unfinished(pack, state_dir=None) -> [the manifest entries not done or skipped]
    enable_lines(pack, state_dir=None) -> ["setup: <id> -- <title> (halo setup <id>)"], one per untouched block
    doctor_rows(pack, state_dir=None) -> [one `info` row while a block waits]
    first_key(pack, state_dir=None) -> "pack:<id>:<block>", the block `halo setup <id>` opens
"""

from __future__ import annotations

import json
from pathlib import Path

FILE = "setup.json"
DONE, SKIPPED = "done", "skipped"
STATES = (DONE, SKIPPED)
EVENT = "setup"


def setup_path(pack_id: str, state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data" / pack_id / FILE


def read(pack_id: str, state_dir=None) -> dict:
    """`{block_id: {state, at, by}}` for each block the file records with a known state; {} when there is none."""
    try:
        raw = json.loads(setup_path(pack_id, state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    blocks = raw.get("blocks") if isinstance(raw, dict) else None
    out = {}
    for bid, rec in (blocks or {}).items() if isinstance(blocks, dict) else []:
        if isinstance(rec, dict) and rec.get("state") in STATES:
            out[str(bid)] = {"state": rec["state"], "at": str(rec.get("at") or ""), "by": str(rec.get("by") or "")}
    return out


def state_of(pack_id: str, block_id: str, state_dir=None, *, data: "dict | None" = None) -> dict:
    rec = (read(pack_id, state_dir) if data is None else data).get(block_id)
    return dict(rec) if rec else {"state": "", "at": "", "by": ""}


def mark(pack_id: str, block_id: str, state: str, *, by: str = "studio", state_dir=None) -> dict:
    """Record `state` for the block (`""` forgets it: untouched again); its record as now saved."""
    from halo_harness.packs.events_log import append
    from halo_harness.packs.state import now
    from halo_harness.privateio import write_private_atomic
    if state not in STATES + ("",):
        raise ValueError(f"{state!r} is not one of {', '.join(STATES)} (or '' to forget)")
    blocks = read(pack_id, state_dir)
    if state:
        blocks[block_id] = {"state": state, "at": now(), "by": by}
    else:
        blocks.pop(block_id, None)
    write_private_atomic(setup_path(pack_id, state_dir), json.dumps({"blocks": blocks}, indent=2, sort_keys=True) + "\n")
    append(pack_id, EVENT, {"block": block_id, "state": state or "untouched", "by": by}, state_dir=state_dir)
    return state_of(pack_id, block_id, data=blocks)


def unfinished(pack, state_dir=None) -> "list[dict]":
    """The pack's blocks neither done nor skipped, in the manifest's order."""
    from halo_harness.packs.manifest_setup import setup_of
    seen = read(pack.id, state_dir)
    return [e for e in setup_of(pack.manifest) if isinstance(e.get("id"), str) and e["id"] not in seen]


def first_key(pack, state_dir=None) -> str:
    """The block `halo setup <id>` opens: the first one waiting, else the pack's first block ('' when it has none)."""
    from halo_harness.packs.manifest_setup import key_of, setup_of
    waiting = unfinished(pack, state_dir) or [e for e in setup_of(pack.manifest) if isinstance(e.get("id"), str)]
    return key_of(pack.id, waiting[0]["id"]) if waiting else ""


def _title(e: dict) -> str:
    t = e.get("title")
    return t.strip() if isinstance(t, str) and t.strip() else str(e.get("id"))


def enable_lines(pack, state_dir=None) -> "list[str]":
    """What `halo pack enable <id>` ends with: one line per untouched block."""
    return [f"setup: {pack.id} -- {_title(e)} (halo setup {pack.id})" for e in unfinished(pack, state_dir)]


def doctor_rows(pack, state_dir=None) -> "list[dict]":
    """One `info` row (a note, exit 0) while any of the enabled pack's blocks waits."""
    waiting = unfinished(pack, state_dir)
    if not waiting:
        return []
    n = len(waiting)
    text = (f"{pack.id}: setup waiting: {n} block{'' if n == 1 else 's'} not done yet "
            f"({', '.join(_title(e) for e in waiting)})")
    return [{"pack": pack.id, "severity": "info", "check": "setup-waiting", "text": text, "fix": f"halo setup {pack.id}",
             "path": str(setup_path(pack.id, state_dir))}]


def waiting_count(pack, state_dir=None) -> int:
    """The Pack Manager's "setup waiting" flag: how many blocks are neither done nor skipped."""
    return len(unfinished(pack, state_dir))


def doctor_lines(cwd=None, state_dir=None) -> "list[tuple[str, str]]":
    """`halo doctor`'s rows: one `[INFO]` line per enabled pack with a Setup block waiting (a note: exit 0)."""
    try:
        from halo_harness.packs.registry import active
        packs = active(cwd=cwd, state_dir=state_dir)
    except Exception:  # a packs folder that does not read is `halo pack doctor`'s to say
        return []
    out = []
    for pack in packs:
        for r in doctor_rows(pack, state_dir):
            out.append((f"pack_setup:{pack.id}", f"[INFO] Pack setup: {r['text']}; {r['fix']} opens them"))
    return out


def door(pack_id: str, cwd=None, state_dir=None) -> "tuple[str, list[str]]":
    """`halo setup <pack>`: `(the block key it opens, a line per block with its state)`, or `("", [why])`; `None`
    for the key when no pack has that id (the word is not a pack: the caller's usage line)."""
    from halo_harness.packs.discover import find
    from halo_harness.packs.manifest_setup import setup_of
    from halo_harness.packs.studio_registry import active_pack
    if find(pack_id, cwd=cwd, state_dir=state_dir) is None:
        return None, []
    pack = active_pack(pack_id, cwd=cwd, state_dir=state_dir)
    if pack is None:
        return "", [f"{pack_id} does not run here: its Setup blocks show once it is enabled (halo pack enable {pack_id})"]
    entries = [e for e in setup_of(pack.manifest) if isinstance(e.get("id"), str)]
    if not entries:
        return "", [f"{pack_id} adds no Setup block (halo pack inspect {pack_id} says what it adds)"]
    seen = read(pack.id, state_dir)
    lines = [f"{pack.id} -- {_title(e)} ({e.get('kind')}): {seen.get(e['id'], {}).get('state') or 'waiting'}"
             for e in entries]
    return first_key(pack, state_dir), lines
