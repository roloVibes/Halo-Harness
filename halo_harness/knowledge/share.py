"""halo_harness.knowledge.share -- findings and decisions across the fleet (Halo
3.1.8.0 R4, docs/FLEET.md "Knowledge across the fleet"), over the coach
library's transport (orchestra/coach_library_share.py).

Recall already finds another box's entries (`halo recall --fleet`: kinds
`finding` / `decision`, each hit with its `ref`, the entry's id). To take
one, a member answers the read-only fleet command `knowledge {id}` -- or
`knowledge {kind, all: true}` for every current entry of a kind -- from its
own store (fleet/control.py, beside `recall` and `coach_library`):

    {"harness": "<name>", "harness_id": "<id>", "entries": [{id, kind, title, when, by, run, repo, evidence,
     alternatives, confidence, supersedes, tags, body}], "bytes": <total>, "left_out": <n> | null}

under the recall switch (`fleet.recall.share: false` answers none;
`fleet.recall.hide: [knowledge]`, `[finding]` or `[decision]` keeps them in),
scrubbed like the capabilities catalog: every absolute path cut to its last
part, the home to `~`, every secret-shaped text redacted; `by` names the
harness id (`gate@<id>`), never a person. One entry over MAX_BYTES is refused
with its size; `all` sends the newest that fit and counts the rest in
`left_out`. Each answer is a `knowledge_asked` line in the member's journal.
The hub's admin route `local/knowledge {harness, id | kind, all}`
(fleet/hub_recall.py) forwards it to one live session of that member.

`fetch(harness, eid)` / `fetch(harness, kind=..., all_kind=True)` (`halo
knowledge fetch`) asks the hub this machine runs and writes each entry here
under the SAME id, read-only: its `_meta.json` says `source: fleet`, `from`
(the harness id), `harness_name`, `fetched` and `read_only: true`. Never over
an entry that is already here. `CALL(home, method, route, body, timeout)`
replaces fleet.hub.running_call (tests).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

CALL: Optional[Callable] = None
MAX_BYTES = 256 * 1024
KIND = "knowledge"
FIELDS = ("id", "kind", "title", "when", "by", "run", "repo", "evidence", "alternatives", "confidence", "supersedes",
          "tags", "body")


def scrub(entry: dict, harness_id: str, homes: tuple = ()) -> dict:
    """The entry as it leaves this box: its fields only, paths cut, secrets redacted, `by` naming the harness."""
    from halo_harness.fleet.capabilities import scrub as cut_paths
    from halo_harness.redact import sanitize_text

    def clean(value):
        if isinstance(value, list):
            return [clean(v) for v in value]
        return sanitize_text(cut_paths(str(value or ""), homes))
    out = {k: clean(entry.get(k)) for k in FIELDS}
    out["id"], out["kind"] = entry["id"], entry["kind"]
    by = str(entry.get("by") or "user")
    out["by"] = by if "@" in by else f"{by}@{harness_id}"
    return out


def _size(rows: list) -> int:
    return len(json.dumps(rows, ensure_ascii=False).encode("utf-8"))


def answer(fields: dict, *, by: str = "", hub: str = "", home=None) -> dict:
    """The member's side of `knowledge {id | kind, all}`: its own store, the recall switch, a journal line."""
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import identity, journal
    from halo_harness.knowledge import store
    home = Path(home) if home is not None else identity.home()
    me = identity.harness(home)
    cfg = RF.settings(home)
    if not cfg["share"]:
        raise RF.Shut(f"{me['name']} does not share its recall or its knowledge (fleet.recall.share: false)")
    fields = fields if isinstance(fields, dict) else {}
    eid, kind = str(fields.get("id") or "").strip(), str(fields.get("kind") or "").strip()
    if eid:
        entry = store.read(eid, home) if store.valid_id(eid) else None
        if entry is None:
            raise RF.Shut(f"no knowledge entry {eid!r} on {me['name']} (halo knowledge list shows them)")
        rows = [entry]
    elif kind in store.KINDS and fields.get("all"):
        rows = store.current(home, kind=kind)
    else:
        raise RF.Shut("a knowledge fetch names an entry id (f-... or d-...), or a kind (finding | decision) with all")
    hidden = [w for w in (KIND, rows[0]["kind"] if rows else kind) if w in cfg["hide"]]
    if hidden:
        raise RF.Shut(f"{me['name']} keeps its knowledge to itself (fleet.recall.hide: {hidden[0]})")
    from halo_harness.config.paths import home as user_home
    homes = tuple(str(h) for h in (user_home(), home, Path(home).parent))
    entries = [scrub(e, me["id"], homes) for e in rows]
    size, left_out = _size(entries), 0
    if size > MAX_BYTES:
        if eid:
            raise RF.Shut(f"entry {eid} is {size / 1024:.0f} KB; a fetch carries at most {MAX_BYTES // 1024} KB")
        keep = []
        for e in entries:
            if _size(keep + [e]) > MAX_BYTES:
                break
            keep.append(e)
        entries, left_out = keep, len(entries) - len(keep)
        size = _size(entries)
    journal.append(home, "knowledge_asked", harness=me["id"], harness_name=me["name"], by=by or None, hub=hub or None,
                   entry=eid or None, of=kind or None, entries=len(entries), bytes=size)
    return {"harness": me["name"], "harness_id": me["id"], "entries": entries, "bytes": size, "left_out": left_out or None}


def _call():
    if CALL is not None:
        return CALL
    from halo_harness.fleet.hub import running_call
    return running_call


def _keep(entry: dict, name: str, hid: str, state_dir) -> Optional[str]:
    """Write one fetched entry here, read-only, under its own id; its id, or None when it is not one."""
    from halo_harness.knowledge import store
    eid, kind = str(entry.get("id") or ""), store.kind_of_id(entry.get("id"))
    if not kind or entry.get("kind") != kind:
        return None
    by = str(entry.get("by") or "")
    by = by if store.valid_by(by) and "@" in by else f"user@{hid}"
    sup = str(entry.get("supersedes") or "")
    meta = {"source": "fleet", "from": hid, "harness_name": name, "fetched": store.utc(), "read_only": True}
    store.write(kind, str(entry.get("title") or ""), body=str(entry.get("body") or ""), evidence=entry.get("evidence") or [],
                by=by, run=str(entry.get("run") or ""), repo=str(entry.get("repo") or ""),
                alternatives=entry.get("alternatives") or [], tags=entry.get("tags") or [],
                supersedes=sup if store.valid_id(sup) else "", eid=eid, when=str(entry.get("when") or "") or None,
                meta=meta, state_dir=state_dir)
    return eid


def fetch(harness: str, eid: str = "", *, kind: str = "", all_kind: bool = False, home=None,
          state_dir=None) -> "tuple[int, dict]":
    """(0 written | 1 refused, unknown or all here already | 2 usage | 3 no hub here, {written, skipped, from, error})."""
    from halo_harness.knowledge import store
    harness, eid, kind = str(harness or "").strip(), str(eid or "").strip(), str(kind or "").strip()
    if not harness or not (store.valid_id(eid) or (all_kind and kind in store.KINDS)):
        return 2, {"error": "fetch takes a harness (its name or id, halo fleet who) and an entry id (f-... or d-...), "
                            "or --all finding|decision"}
    if eid and store.read(eid, state_dir) is not None:
        return 1, {"error": f"{eid} is already here; a fetch never overwrites it (halo knowledge forget {eid} first)"}
    if home is None:
        from halo_harness.fleet import identity
        home = identity.home()
    ask = {"harness": harness, "id": eid, "kind": kind, "all": bool(all_kind and not eid)}
    got = _call()(home, "POST", "local/knowledge", ask, 60.0)
    if got is None:
        return 3, {"error": "fetch asks the hub this machine runs, and none runs here (`halo studio --fleet` starts one)"}
    status, body = got
    body = body if isinstance(body, dict) else {}
    if status != 200:
        return 1, {"error": f"{body.get('harness') or harness}: {body.get('error') or status}"}
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    rows = [e for e in result.get("entries") or [] if isinstance(e, dict)]
    if eid and not any(e.get("id") == eid for e in rows):
        return 1, {"error": f"{harness} answered no entry {eid}"}
    name = str(result.get("harness") or body.get("harness") or harness)
    hid = str(result.get("harness_id") or name)
    written, skipped = [], []
    for e in rows:
        if store.valid_id(e.get("id")) and store.read(e["id"], state_dir) is not None:
            skipped.append(e["id"])
            continue
        got_id = _keep(e, name, hid, state_dir)
        if got_id:
            written.append(got_id)
    out = {"written": written, "skipped": skipped, "from": name, "left_out": result.get("left_out")}
    if not written:
        out["error"] = "every entry it answered is here already" if skipped else f"{name} answered no entry"
    return (0 if written else 1), out
