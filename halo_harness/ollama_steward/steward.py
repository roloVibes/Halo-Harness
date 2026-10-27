"""halo_harness.ollama_steward.steward -- Halo 3.3.4.0 R3: the steward
adjusts. `run()` = the rules' findings -> the fit plan (inside the thrash
finding) -> each proposal applied per `ollama.steward.apply`:

    auto    (default) apply it and say one line (the command prints it; a
            session that next calls the model shows the profile's note in
            its status area, agent/ollama_window_steward.py)
    review  write it down as a proposal; `halo ollama steward apply <id>`
    off     findings only

Every change is one line in `<state>/ollama/steward.jsonl`: {id, at, kind
("apply" | "proposal" | "undo" | "rollback"), key, field, from, to, why,
finding, rule, evidence, plan, mode}. The guards: never above a measured cap
(the learned cap, the host's max_ctx), at most one change per host and model
per ten minutes, and a change followed by worse calls (more trims, cut
replies and errors in the next 10 calls of that model than in the 10
before) is rolled back on its own and says so. Server-side hints are never
applied. `undo_last()` reverts the newest change still in place.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

STEWARD_FILE = "steward.jsonl"
MODES = ("auto", "review", "off")
QUIET_S = 600.0
JUDGE_CALLS = 10


def mode() -> str:
    try:
        from halo_harness.theme import get_config_value
        raw = str(get_config_value("ollama.steward.apply", default="auto")).strip().lower()
    except Exception:
        raw = "auto"
    return raw if raw in MODES else "auto"


def journal_path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / STEWARD_FILE


def read_journal(state_dir) -> list:
    out = []
    try:
        with open(journal_path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _append(state_dir, row: dict) -> dict:
    from halo_harness.filelock import file_lock
    from halo_harness.ollama_steward.ledger import now_iso
    row = {"at": now_iso(row.pop("_now", None)), **row}
    path = journal_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=2.0):
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def _in_place(journal: list) -> list:
    """The applied changes not undone or rolled back, oldest first."""
    reverted = {r.get("reverts") for r in journal if r.get("kind") in ("undo", "rollback")}
    return [r for r in journal if r.get("kind") == "apply" and r.get("id") not in reverted]


def _cap(state_dir, key: str, hosts: list) -> Optional[int]:
    from halo_harness.ollama_steward.profiles import split_key
    host_name, model = split_key(key)
    h = next((x for x in hosts if x.name == host_name), None)
    if h is None:
        return None
    caps = []
    try:
        from halo_harness.providers.ollama_calibrate import lookup_learned_cap
        caps.append(lookup_learned_cap(state_dir, host_url=h.url, model=model))
    except Exception:
        pass
    caps.append(getattr(h, "max_ctx", None))
    caps = [c for c in caps if isinstance(c, int) and c > 0]
    return min(caps) if caps else None


def check(state_dir, f: dict, *, hosts: list, now: float, journal: Optional[list] = None) -> "tuple[Optional[dict], str]":
    """(the change to make, "") or (None, why not)."""
    from halo_harness.ollama_steward.ledger import parse_at
    p = f.get("proposal")
    if not p:
        return None, "no profile change"
    journal = read_journal(state_dir) if journal is None else journal
    last = [r for r in journal if r.get("key") == f["key"] and r.get("kind") in ("apply", "undo", "rollback")]
    if last and now - (parse_at(last[-1].get("at")) or 0) < QUIET_S:
        return None, f"{f['key']} changed less than ten minutes ago"
    to = p["to"]
    if p["field"] == "num_ctx":
        cap = _cap(state_dir, f["key"], hosts)
        if cap and isinstance(to, int) and to > cap:
            to = cap
        if to == p.get("from"):
            return None, f"already at the measured cap ({cap})"
    return {**p, "to": to}, ""


def apply_change(state_dir, f: dict, change: dict, *, mode_name: str, now: Optional[float] = None) -> dict:
    from halo_harness.ollama_steward.profiles import set_field
    note = f"steward: {change['field']} {change['to']} for {f['model']} on {f['host']} ({change['why']})"
    set_field(f["key"], change["field"], change["to"], by="steward", note=note[:300])
    return _append(state_dir, {"_now": now, "id": f"c-{f['id']}-{int(now or time.time())}", "kind": "apply",
                               "key": f["key"], "field": change["field"], "from": change.get("from"),
                               "to": change["to"], "why": change["why"], "finding": f["id"], "rule": f["rule"],
                               "evidence": f.get("evidence"), "plan": f.get("plan"), "mode": mode_name, "say": note})


def _revert(state_dir, row: dict, kind: str, why: str, now: Optional[float] = None) -> dict:
    from halo_harness.ollama_steward.profiles import set_field
    say = f"steward {kind}: {row['field']} back to {row.get('from')} for {row['key']} ({why})"
    set_field(row["key"], row["field"], row.get("from"), by="steward", note=say[:300])
    return _append(state_dir, {"_now": now, "id": f"{kind[0]}-{row['id']}", "kind": kind, "reverts": row["id"],
                               "key": row["key"], "field": row["field"], "from": row.get("to"), "to": row.get("from"),
                               "why": why, "say": say})


def undo_last(state_dir) -> Optional[dict]:
    live = _in_place(read_journal(state_dir))
    return _revert(state_dir, live[-1], "undo", "undone by hand") if live else None


def _bad(line: dict) -> int:
    return int(bool(line.get("trimmed")) or line.get("done_reason") == "length" or line.get("status") != 200)


def rollbacks(state_dir, *, lines: Optional[list] = None, now: Optional[float] = None) -> list:
    """Each change in place whose next 10 calls went worse than the 10 before it, reverted."""
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    from halo_harness.ollama_steward.profiles import key_for
    from halo_harness.ollama_steward.traffic import canonical_host
    from halo_harness.providers.ollama import resolve_ollama_hosts
    lines = read_calls(state_dir) if lines is None else lines
    hosts = resolve_ollama_hosts()
    out = []
    for row in _in_place(read_journal(state_dir)):
        t = parse_at(row.get("at")) or 0
        mine = [x for x in lines if x.get("kind") != "calibrate"
                and key_for(canonical_host(x.get("host") or {}, hosts)[0], x.get("model")) == row["key"]]
        before = [x for x in mine if (parse_at(x.get("at")) or 0) < t][-JUDGE_CALLS:]
        after = [x for x in mine if (parse_at(x.get("at")) or 0) >= t][:JUDGE_CALLS]
        if len(after) < JUDGE_CALLS:
            continue
        b, a = sum(map(_bad, before)), sum(map(_bad, after))
        if a > b:
            out.append(_revert(state_dir, row, "rollback", f"{a} bad calls of the next {len(after)} against {b} of "
                               f"the {len(before)} before", now=now))
    return out


def run(state_dir, *, mode_name: Optional[str] = None, found: Optional[list] = None, say: Callable = print,
        now: Optional[float] = None, **gather_kw) -> dict:
    """One pass: roll back what made calls worse, then judge and act per mode."""
    from halo_harness.ollama_steward.rules import findings as get_findings
    from halo_harness.providers.ollama import resolve_ollama_hosts
    mode_name = mode_name or mode()
    now = now or time.time()
    done = {"mode": mode_name, "rolled_back": [], "applied": [], "proposed": [], "skipped": [], "findings": []}
    if mode_name != "off":
        done["rolled_back"] = rollbacks(state_dir, now=now)
        for r in done["rolled_back"]:
            say(r["say"])
    found = get_findings(state_dir, **gather_kw) if found is None else found
    done["findings"] = found
    if mode_name == "off":
        return done
    hosts = resolve_ollama_hosts()
    journal = read_journal(state_dir)
    proposed = {r.get("finding") for r in journal if r.get("kind") == "proposal"}
    for f in found:
        change, why = check(state_dir, f, hosts=hosts, now=now, journal=journal)
        if change is None:
            if f.get("proposal"):
                done["skipped"].append({"finding": f["id"], "why": why})
            continue
        if mode_name == "auto":
            row = apply_change(state_dir, f, change, mode_name=mode_name, now=now)
            journal.append(row)
            done["applied"].append(row)
            say(row["say"])
        elif f["id"] not in proposed:
            done["proposed"].append(propose(state_dir, f, change, now=now))
    return done


def propose(state_dir, f: dict, change: dict, *, now: Optional[float] = None) -> dict:
    """A review-mode proposal line (its id is the finding's: `halo ollama steward apply <id>`)."""
    return _append(state_dir, {"_now": now, "id": f["id"], "kind": "proposal", "key": f["key"], "field": change["field"],
                               "from": change.get("from"), "to": change["to"], "why": change["why"],
                               "finding": f["id"], "rule": f["rule"], "evidence": f.get("evidence"),
                               "plan": f.get("plan")})


def apply_by_id(state_dir, fid: str, *, now: Optional[float] = None, **gather_kw) -> "tuple[Optional[dict], str]":
    """`halo ollama steward apply <id>`: a finding of the current run (or a proposal in the journal) applied."""
    from halo_harness.ollama_steward.rules import findings as get_findings
    from halo_harness.providers.ollama import resolve_ollama_hosts
    now = now or time.time()
    f = None
    row = next((r for r in reversed(read_journal(state_dir)) if r.get("kind") == "proposal" and r.get("id") == fid),
               None)
    if row is None:
        f = next((x for x in get_findings(state_dir, **gather_kw) if x["id"] == fid), None)
        if f is None:
            return None, f"no finding or proposal with the id {fid}"
    else:
        from halo_harness.ollama_steward.profiles import split_key
        host, model = split_key(row["key"])
        f = {"id": fid, "rule": row.get("rule"), "key": row["key"], "host": host, "model": model,
             "evidence": row.get("evidence"), "plan": row.get("plan"),
             "proposal": {k: row.get(k) for k in ("field", "from", "to", "why")}}
    change, why = check(state_dir, f, hosts=resolve_ollama_hosts(), now=now)
    if change is None:
        return None, why
    return apply_change(state_dir, f, change, mode_name="review", now=now), ""
