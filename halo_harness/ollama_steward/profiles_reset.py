"""halo_harness.ollama_steward.profiles_reset -- Halo 3.3.13.1 (the steward hotfix, plans/ROADMAP.md F1): a model's
profile back to the measured defaults.

    halo ollama steward profiles [--json]                  every profile, one line each
    halo ollama steward profiles reset [<model>] [--host H] [--json]
                                                          drop the tuned fields of that model's profiles (every
                                                          profile with no model), saying what each dropped

Studio's Local section calls the same `reset` (POST ollama/steward/profiles-reset {model?, host?},
studio/ollama_steward_api.py). The tuned fields (profiles.CHANGEABLE: num_ctx, num_predict, keep_alive, tools_max,
host_for, compact_at) go; the measured dialect record stays; the next call uses the measured window (the learned
cap, the memory estimate). Every change still in force on a reset profile is marked reverted (changes.jsonl and the
steward's journal), so no rollback or session end puts a dropped value back.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def _matches(key: str, model: Optional[str], host: Optional[str]) -> bool:
    from halo_harness.ollama_steward.profiles import short_model, split_role
    h, m, _role = split_role(key)
    if host and h.lower() != host.lower():
        return False
    if not model:
        return True
    want = short_model(model)
    return short_model(m) == want or short_model(m).split(":")[0] == want


def _value(v) -> str:
    from halo_harness.ollama_steward.rules_reply_bound import say_n
    return say_n(v) if isinstance(v, int) and not isinstance(v, bool) else str(v)


def _mark_reverted(state_dir, key: str, why: str, now: Optional[float]) -> int:
    from halo_harness.ollama_steward import changes, steward
    from halo_harness.ollama_steward.ledger import now_iso
    from halo_harness.ollama_steward.profiles import CHANGEABLE
    n = 0
    for r in changes.in_force(state_dir):
        if r.get("key") == key and r.get("field") in CHANGEABLE:
            changes._append(state_dir, {"event": "revert", "id": r["id"], "reverted_at": now_iso(now),
                                        "revert_why": why, "revert_line": f"profile {key} reset ({why})"})
            n += 1
    for r in steward._in_place(steward.read_journal(state_dir)):
        if r.get("key") == key:
            steward._append(state_dir, {"_now": now, "id": f"u-{r['id']}", "kind": "undo", "reverts": r["id"],
                                        "key": key, "field": r.get("field"), "from": r.get("to"), "to": None,
                                        "why": why, "say": f"steward undo: profile {key} reset ({why})"})
    return n


def reset(state_dir, model: Optional[str] = None, host: Optional[str] = None, *,
          now: Optional[float] = None) -> "tuple[list[str], list[dict]]":
    """(the lines said, one row per profile reset: {key, dropped})."""
    from halo_harness.ollama_steward.ledger import now_iso
    from halo_harness.ollama_steward.profiles import CHANGEABLE, _save, all_profiles, clean
    from halo_harness.ollama_steward.steward import profile_lock
    why = "reset to the measured defaults"
    lines, rows = [], []
    with profile_lock(state_dir):
        profiles = all_profiles()
        for key in sorted(k for k in profiles if _matches(k, model, host)):
            entry = profiles[key]
            dropped = {f: entry[f] for f in CHANGEABLE if f in entry}
            if not dropped:
                continue
            keep = {k: v for k, v in entry.items() if k == "dialect"}
            if keep:
                profiles[key] = clean({**keep, "by": "user", "at": now_iso(now), "note": why})
            else:
                profiles.pop(key, None)
            _mark_reverted(state_dir, key, why, now)
            rows.append({"key": key, "dropped": {f: _value(v) for f, v in dropped.items()}})
            lines.append(f"reset {key}: dropped " + ", ".join(f"{f} {_value(v)}" for f, v in dropped.items())
                         + "; its calls use the measured window again")
        if rows:
            _save(profiles)
    if not rows:
        what = " ".join(x for x in (model, f"on {host}" if host else "") if x) or "any model"
        lines.append(f"nothing to reset: no tuned profile for {what}")
    return lines, rows


def cmd_profiles(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward.profiles import all_profiles
    p = argparse.ArgumentParser(prog="halo ollama steward profiles",
                                description="The Halo-side profiles per host and model (ollama.profiles); `reset` "
                                            "puts a model's profile back to the measured defaults.")
    p.add_argument("what", nargs="?", choices=("reset",), help="reset: drop the tuned fields")
    p.add_argument("model", nargs="?", default=None, help="the model (every profile when left out)")
    p.add_argument("--host", default=None, help="only this host (its name here)")
    p.add_argument("--json", action="store_true", help="print JSON instead of lines")
    args = p.parse_args(argv)
    if args.what == "reset":
        lines, rows = reset(bridge_home(), args.model, args.host)
        print(json.dumps({"reset": rows, "lines": lines}, indent=2) if args.json else "\n".join(lines))
        return 0
    every = {k: v for k, v in all_profiles().items() if _matches(k, args.model, args.host)}
    if args.json:
        print(json.dumps({k: {f: _value(x) if isinstance(x, int) else x for f, x in v.items()}
                          for k, v in every.items()}, indent=2, default=str))
        return 0
    if not every:
        print("no profiles: every call uses the measured window", file=sys.stdout)
    for k, v in sorted(every.items()):
        tuned = ", ".join(f"{f} {_value(v[f])}" for f in ("num_ctx", "num_predict", "keep_alive", "tools_max",
                                                          "host_for", "compact_at") if f in v)
        print(f"{k}: {tuned or 'no tuned field'} (by {v.get('by') or 'you'})")
    return 0
