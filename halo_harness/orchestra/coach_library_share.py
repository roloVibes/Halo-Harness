"""halo_harness.orchestra.coach_library_share -- the improvement library across
the fleet (Halo 3.1.6.0 R3; orchestra/coach_library.py keeps the entries).

Recall already finds another box's entries (`halo recall --fleet`: the kind
`coach_library`, the Lessons as the excerpt). To take one, a member answers
the read-only fleet command `coach_library {entry}` (fleet/control.py, next
to `recall`) from its own library:

    {"harness": "<name>", "entry": {entry.json}, "experience": "<EXPERIENCE.md>", "overlay": {overlay.json},
     "files": {"<path>": "<text>"}, "bytes": <total>}

under the same switch as recall (`fleet.recall.share: false` answers none;
`fleet.recall.hide: [coach_library]` keeps the library out too), refused for
an unknown entry and for one over MAX_BYTES (256 KB) with its size; each
answer is a `library_asked` line in the member's journal. The hub's admin
route `local/coach-library {harness, entry}` (fleet/hub_recall.py) forwards it
to one live session of that member. `fetch(harness, entry)` (`halo coach
library fetch`) asks the hub this machine runs and writes the entry here
under the SAME id with `from: <harness>` in entry.json -- never over an entry
that is already here. `CALL(home, method, route, body, timeout)` replaces
fleet.hub.running_call (tests).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

CALL: Optional[Callable] = None
MAX_BYTES = 256 * 1024
KIND = "coach_library"


def _size(body: dict) -> int:
    texts = [json.dumps(body["entry"], indent=2, ensure_ascii=False, default=str), body["experience"],
             json.dumps(body["overlay"], indent=2, ensure_ascii=False, default=str)] + list(body["files"].values())
    return sum(len(str(t).encode("utf-8")) for t in texts)


def answer(fields: dict, *, by: str = "", hub: str = "", home=None) -> dict:
    """The member's side of `coach_library {entry}`: its own library, the recall switch, a journal line."""
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import identity, journal
    from halo_harness.orchestra import coach_library as L
    home = Path(home) if home is not None else identity.home()
    me = identity.harness(home)
    cfg = RF.settings(home)
    if not cfg["share"]:
        raise RF.Shut(f"{me['name']} does not share its recall or its coach library (fleet.recall.share: false)")
    if KIND in cfg["hide"]:
        raise RF.Shut(f"{me['name']} keeps its coach library to itself (fleet.recall.hide: {KIND})")
    entry = str((fields or {}).get("entry") or "").strip()
    doc = L.read(entry, home) if L.valid_id(entry) else None
    if doc is None:
        raise RF.Shut(f"no entry {entry!r} in {me['name']}'s coach library (halo coach library lists them)")
    try:
        overlay = json.loads(L.text_of(entry, L.OVERLAY, home) or "{}")
    except ValueError:
        overlay = {}
    body = {"entry": doc, "experience": L.text_of(entry, L.EXPERIENCE, home), "overlay": overlay,
            "files": L.stored_files(entry, home)}
    size = _size(body)
    if size > MAX_BYTES:
        raise RF.Shut(f"entry {entry} is {size / 1024:.0f} KB; a fetch carries at most {MAX_BYTES // 1024} KB")
    journal.append(home, "library_asked", harness=me["id"], harness_name=me["name"], by=by or None, hub=hub or None,
                   entry=entry, bytes=size)
    return dict(body, harness=me["name"], bytes=size)


def _call():
    if CALL is not None:
        return CALL
    from halo_harness.fleet.hub import running_call
    return running_call


def fetch(harness: str, entry: str, *, home=None, state_dir=None) -> "tuple[int, dict]":
    """(0 written | 1 refused, unknown or already here | 2 not an entry id | 3 no hub here, {entry, from, path, files,
    error})."""
    from halo_harness.orchestra import coach_library as L
    harness, entry = str(harness or "").strip(), str(entry or "").strip()
    if not harness or not L.valid_id(entry):
        return 2, {"error": "fetch takes a harness (its name or id, halo fleet who) and an entry id (e-<yyyymmdd>-<4 hex>)"}
    if L.entry_dir(entry, state_dir).exists():
        return 1, {"error": f"{entry} is already in this library; a fetch never overwrites it "
                            f"(halo coach library forget {entry} first)"}
    if home is None:
        from halo_harness.fleet import identity
        home = identity.home()
    got = _call()(home, "POST", "local/coach-library", {"harness": harness, "entry": entry}, 60.0)
    if got is None:
        return 3, {"error": "fetch asks the hub this machine runs, and none runs here (`halo studio --fleet` starts one)"}
    status, body = got
    body = body if isinstance(body, dict) else {}
    if status != 200:
        return 1, {"error": f"{body.get('harness') or harness}: {body.get('error') or status}"}
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    doc = result.get("entry") if isinstance(result.get("entry"), dict) else None
    if not doc or doc.get("id") != entry:
        return 1, {"error": f"{harness} answered no entry {entry}"}
    name = str(result.get("harness") or body.get("harness") or harness)
    doc = dict(doc, **{"from": name, "fetched": round(time.time(), 3)})
    files = {L.safe_rel(k): str(v) for k, v in (result.get("files") or {}).items() if L.safe_rel(k)}
    overlay = result.get("overlay") if isinstance(result.get("overlay"), dict) else {}
    path = L.write(doc, str(result.get("experience") or ""), overlay, files, state_dir)
    return 0, {"entry": entry, "from": name, "path": str(path), "files": sorted(files)}
