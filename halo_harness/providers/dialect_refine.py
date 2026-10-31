"""halo_harness.providers.dialect_refine -- Halo 3.3.6.0 R4: the dialect record
refined from the ledger (providers/dialect.py says what the record is).

    refine(host, model, *, state_dir, now=None, force=False) -> [lines]

The model's newest LAST_N calls on the host: a reply cut (`done_reason` length,
or the server log's `reply-cut`) in over CUT_RATE of them raises the reply
reserve one step; a loop the guard saw (`loop` on a ledger line) turns the
guard on. A field you set is never changed. Per `ollama.steward.apply`: auto
writes it (`from: ledger`), review leaves a proposal in the steward's journal
(`halo ollama steward apply <id>`), off does nothing. At most once a minute
per host and model in a process.
"""

from __future__ import annotations

import re
import time
from typing import Optional

from halo_harness.providers.dialect import STEPS, _key, clean_stored, record, set_fields, stored

CUT_RATE, LAST_N = 0.10, 20
REFINE_EVERY_S = 60.0
_REFINED: dict = {}


def refine(host, model: str, *, state_dir, now: Optional[float] = None, force: bool = False) -> list:
    """The ledger's rules on the newest LAST_N calls; per `ollama.steward.apply`. Returns the lines said."""
    name, now = getattr(host, "name", host), now or time.time()
    k = (str(state_dir), name, model)
    if not force and now - _REFINED.get(k, 0) < REFINE_EVERY_S:
        return []
    _REFINED[k] = now
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.providers.ollama import ollama_names_match
    rows = [x for x in read_calls(state_dir, since=7 * 86400.0, host=name)
            if x.get("model") and ollama_names_match(x["model"], model) and x.get("kind") != "calibrate"][-LAST_N:]
    if not rows:
        return []
    rec, changes, why = record(host, model, state_dir=state_dir), {}, []
    cut = [x for x in rows if x.get("done_reason") == "length" or "reply-cut" in (x.get("log_events") or [])]
    if len(rows) >= 5 and len(cut) / len(rows) > CUT_RATE and rec["from"].get("reply_reserve") != "user":
        nxt = next((s for s in STEPS if s > rec["reply_reserve"]), None)
        if nxt:
            changes["reply_reserve"] = nxt
            why.append(f"{len(cut)} of its last {len(rows)} replies were cut: the reply reserve {rec['reply_reserve']:,} -> {nxt:,}")
    if any(x.get("loop") for x in rows) and not rec["loop_guard"]["on"] and rec["from"].get("loop_guard") != "user":
        changes["loop_guard"] = {"on": True, "window": rec["loop_guard"]["window"]}
        why.append("it started repeating itself: the loop guard is on")
    if not changes:
        return []
    from halo_harness.ollama_steward.steward import mode
    m = mode()
    lines = [f"{model} on {name}: {w}" for w in why]
    if m == "auto":
        before = stored(host, model)
        set_fields(host, model, changes, by="ledger")
        from halo_harness.ollama_steward import changes as CH  # 3.3.6.0 R5: a refinement is a change with a scope
        for f, v in changes.items():
            CH.record(state_dir, by="ledger", key=_key(host, model), field=f"dialect.{f}", before=before.get(f), after=v,
                      scope="until-restart", why="; ".join(why), before_by=(before.get("from") or {}).get(f))
    elif m == "review":
        _propose(state_dir, host, model, changes, why)
        lines = [f"{line} (proposed: ollama.steward.apply is review)" for line in lines]
    else:
        return []
    return lines


def _propose(state_dir, host, model: str, changes: dict, why: list) -> None:
    from halo_harness.ollama_steward.steward import _append
    d = stored(host, model)
    new = {**d, **changes, "from": {**(d.get("from") or {}), **{f: "ledger" for f in changes}}}
    fid = f"dialect-{re.sub(r'[^a-z0-9]+', '-', _key(host, model).lower())}"
    _append(state_dir, {"id": fid, "kind": "proposal", "key": _key(host, model), "field": "dialect",
                        "from": d or None, "to": clean_stored(new), "why": "; ".join(why), "finding": fid,
                        "rule": "dialect-refine", "evidence": None, "plan": None})
