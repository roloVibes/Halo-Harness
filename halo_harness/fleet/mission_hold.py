"""halo_harness.fleet.mission_hold -- what the hub holds for a pack while a
mission runs (Halo 3.2.1.0 R3, docs/FLEET.md "Missions", docs/MISSIONS.md):

* **Capacity.** A pack capability's `capacity.parallel` (its harness's own
  catalog, packs/fleet_registry.py) is held by the hub: before a ready part
  starts, `held` counts the parts live on its harness (asked or running, in
  every mission this hub runs now) that hold the same pack capability (a
  part's `holds`, set when it starts); at the cap the part is `waiting` with
  one line in the mission log, "part 3 waits: bob@member runs 2/2 of pack
  doc-review: docs.review", and it starts when a slot frees. `LOCK` keeps the
  count and the start together across the hub's mission runners.
* **A refused part, re-planned once.** A part its harness refused for a pack
  reason (the worker's `pack_check` line, packs/fleet_share.pack_refusal) is
  assigned again by the rules (mission_assign.assign) with that harness left
  out; a harness with the capability takes it, the plan and MISSION.md say
  so, the part goes back to `pending` and the log and the decisions say
  "part 1 replanned: bob@member refused (<line>); alice@hub has pack
  doc-review: docs.review". With no such harness, or on a second refusal, it
  fails as before with the line ("part 1 not replanned: no other harness has
  docs.review" in the log when nobody else has it).
"""

from __future__ import annotations

import contextlib
import threading
from typing import Optional

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_assign import assign, has, norm_need

LOCK = threading.RLock()


def _cat(entries: list, hid: str) -> dict:
    return next((e.get("catalog") or {} for e in entries or [] if str(e.get("harness")) == hid), {})


def limits(part: dict, entries: list) -> dict:
    """`{"<pack>/<name>": parallel}`: the part's pack needs whose capability carries capacity.parallel there."""
    cat, out = _cat(entries, str(part.get("harness") or "")), {}
    for pn in part.get("pack_needs") or []:
        need = norm_need((pn or {}).get("need"))
        word, pack = need[len("pack:"):] if need.startswith("pack:") else need, str((pn or {}).get("pack") or "")
        for p in cat.get("packs") or []:
            for c in (p.get("capabilities") or []) if isinstance(p, dict) and str(p.get("id")) == pack else []:
                par = (c.get("capacity") or {}).get("parallel") if isinstance(c, dict) else None
                if str(c.get("name") or "").lower() == word and isinstance(par, int) and not isinstance(par, bool) and par > 0:
                    out[f"{pack}/{c.get('name')}"] = par
    return out


def slot(part: dict):
    """LOCK for a part with pack needs (its count and its start go together), else nothing to hold."""
    return LOCK if part.get("pack_needs") else contextlib.nullcontext()


def _live(doc: dict, hid: str, key: str) -> int:
    return sum(1 for ps in (doc.get("parts") or {}).values() if ps.get("state") in M.PART_LIVE
               and str(ps.get("harness")) == hid and key in (ps.get("holds") or []))


def live(home, mid: str, doc: dict, hid: str, key: str) -> int:
    """Parts live on `hid` holding `key`: this mission's (`doc`) and every other one a runner runs here now."""
    from halo_harness.fleet import mission_run as R
    n = _live(doc, hid, key)
    with R._lock:
        others = [m for (h, m), r in R._runners.items() if h == str(home) and m != mid and r.is_alive()]
    for m in others:
        other = S.load(home, m)
        n += _live(other, hid, key) if other and other.get("state") == "running" else 0
    return n


def held(home, mid: str, doc: dict, part: dict, entries: list) -> "tuple[str, list]":
    """`(line, keys)`: the waits line when one of the part's pack capabilities is at its cap on its harness
    ('' when it may start now), and the keys the part holds once it starts."""
    lim = limits(part, entries)
    hid = str(part.get("harness") or "")
    name = (doc.get("parts") or {}).get(part["id"], {}).get("harness_name") or part.get("harness_name") or hid
    for key, par in lim.items():
        k = live(home, mid, doc, hid, key)
        if k >= par:
            pack, cap = key.split("/", 1)
            return f"part {part['id']} waits: {name} runs {k}/{par} of pack {pack}: {cap}", list(lim)
    return "", list(lim)


def replan(home, mid: str, plan: dict, part: dict, ps: dict, line: str, entries: list,
           load: Optional[dict] = None) -> Optional[dict]:
    """The part's new state fields after its harness refused it with the pack line `line` (the part is moved in
    the plan, logged and decided), or None when it stays failed (no other harness has it, or it moved once)."""
    if ps.get("replanned"):
        return None
    pid, old = part["id"], str(ps.get("harness") or part.get("harness") or "")
    was = ps.get("harness_name") or part.get("harness_name") or old
    others = [e for e in entries or [] if str(e.get("harness")) != old]
    trial = assign({**part, "harness": None, "reason": ""}, others, list(plan.get("prefer") or []), dict(load or {}))
    if not trial.get("harness"):
        needs = list(trial.get("needs") or [])
        what = ("all of " if len(needs) > 1 else "") + (", ".join(needs) or "its needs")
        S.log(home, mid, "replan", part=pid, harness=old, text=f"part {pid} not replanned: no other harness has {what}")
        return None
    hid, name = str(trial["harness"]), trial.get("harness_name") or trial["harness"]
    whys = [w for w in (has(_cat(entries, hid), pn.get("need")) for pn in part.get("pack_needs") or []) if w]
    said = f"part {pid} replanned: {was} refused ({line}); {name} has {', '.join(whys) or trial.get('reason')}"
    part.update(harness=hid, harness_name=name, reason=said[:300], pinned=bool(trial.get("pinned")),
                pack_needs=trial.get("pack_needs") or part.get("pack_needs") or [])
    from halo_harness.fleet.mission_plan import write_plan
    doc = S.update(home, mid, lambda d: M.decide(d, said, ""))
    write_plan(home, doc, plan)
    S.log(home, mid, "replanned", part=pid, harness=hid, was=old, text=said)
    return {"state": "pending", "harness": hid, "harness_name": name, "error": None, "command_id": None,
            "via_session": None, "started": None, "ended": None, "replanned": said}
