"""halo_harness.local_warm_cli -- `halo local warm [<lineup>] [--host H] [--keep-alive D] [--dry] [--json]` (Halo
3.3.7.0 R3; plans/local-model-fit-brief.md D1 2): pre-warm a lineup's warm set at session start.

    warm_lineup(name, *, host=None, keep_alive=None, dry=False, say=None) -> {lineup, hosts [{host, line, rows}],
        loaded, warm, later, seconds, line}
        rows: [{model, lanes, state ("loaded" | "already warm" | "pivots later" | "not judged" | "failed"), seconds,
                window, say}]
    cmd_warm(argv) -> exit code

The warm set is local_sched/warm_set.pack's for the named lineup (else the active one): per card, the models that
co-reside (the lineup's own `warm:` list first). What is not resident is loaded at its lane's window -- through
the paired halo host's `warm` operation when a host serves it (its invariants first; `beside` for the second model
on the card), else the Ollama API (providers/ollama_load.load) -- and each row says what happened and how long
it took; the models that cannot co-reside are listed as "pivots later" with their load time. A name that is not a
lineup (or no lineup in force) is the 2.0.7 form: the models themselves (local_cli._cmd_warm).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional


def _keep(raw):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return raw


def _load(host, model: str, window: int, keep, beside: bool) -> dict:
    from halo_harness.local_sched.pivot import _client
    c = _client(host)
    if c is not None:
        from halo_harness.ollama_steward.host_client import HostError, _addr_port
        params = {"model": model, "num_ctx": int(window), "beside": beside}
        if keep is not None:
            params["keep_alive"] = keep
        served = c.served_name(_addr_port(str(host.url))[1])
        if served:
            params["host"] = served
        try:
            got = c.act("control", "warm", params, why="halo local warm")
        except HostError as e:
            return {"ok": False, "say": str(e)}
        if got.get("queued"):
            return {"ok": False, "say": got.get("line") or "queued for the host's owner"}
        return {"ok": bool(got.get("ok", True)), "say": got.get("say") or "loaded (through the halo host)"}
    from halo_harness.providers.ollama_load import load
    return load(host, model, num_ctx=int(window), keep_alive=keep)


def warm_lineup(name: Optional[str], *, host: Optional[str] = None, keep_alive=None, dry: bool = False,
                say=None) -> dict:
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.loads import record
    from halo_harness.local_sched.pivot import mark_loaded
    from halo_harness.local_sched.preview import _vram_aware, lanes_for
    from halo_harness.local_sched.swap_cost import secs
    from halo_harness.local_sched.warm_set import by_host, pack
    from halo_harness.providers.ollama import ollama_names_match
    lanes, declared, lineup = lanes_for(name)
    out = {"lineup": lineup, "hosts": [], "loaded": 0, "warm": 0, "later": 0, "seconds": 0.0, "dry": dry}
    say = say or (lambda s: None)
    keep = _keep(keep_alive)
    for host_name, group in by_host(lanes).items():
        if host and host_name != host:
            continue
        h = F.host_named(host_name)
        if h is None:
            continue
        mine = [d for d in declared if any(ollama_names_match(d, ln["model"]) for ln in group)]
        ws = pack(h, group, declared=mine)
        group, moved = _vram_aware(ws, group)
        if moved:  # the VRAM-aware four run on main's model: nothing of theirs to load
            ws = pack(h, group, declared=mine)
        say(ws["line"])
        rows, beside = [], False
        for m in ws["warm"]:
            row = {"model": m["model"], "lanes": m["lanes"], "window": m["window"], "seconds": 0.0}
            if m["warm_now"]:
                row.update(state="already warm", say=f"{m['model']} ({', '.join(m['lanes'])}): already warm")
                out["warm"] += 1
                beside = True
            elif dry:
                row.update(state="would load", say=f"{m['model']} ({', '.join(m['lanes'])}): would load at "
                                                   f"{m['window']:,} (~{secs(m['load_s'])}, {m['load_from']})")
            else:
                t0 = time.monotonic()
                got = _load(h, m["model"], m["window"], keep, beside)
                took = round(time.monotonic() - t0, 1)
                row.update(seconds=took, state="loaded" if got["ok"] else "failed",
                           say=(f"{m['model']} ({', '.join(m['lanes'])}): loaded in {secs(took)} at {m['window']:,}"
                                if got["ok"] else f"{m['model']} ({', '.join(m['lanes'])}): failed -- {got['say']}"))
                if got["ok"]:
                    out["loaded"] += 1
                    out["seconds"] += took
                    beside = True
                    mark_loaded(h, m["model"])
                    record(None, session=None, host=host_name, model=m["model"], seconds=took, why="warm")
            rows.append(row)
            say(f"  {row['say']}")
        for m in ws["pivots"] + ws["unknown"]:
            state = "pivots later" if m in ws["pivots"] else "not judged"
            cost = f"~{secs(m['load_s'])}, {m['load_from']}; " if m.get("load_s") is not None else ""
            rows.append({"model": m["model"], "lanes": m["lanes"], "state": state, "seconds": 0.0, "window": m["window"],
                         "say": f"{m['model']} ({', '.join(m['lanes'])}): {state} ({cost}{m.get('why')})"})
            out["later"] += 1 if state == "pivots later" else 0
            say(f"  {rows[-1]['say']}")
        out["hosts"].append({"host": host_name, "line": ws["line"], "rows": rows, "set": ws})
    if not lanes:
        out["line"] = f"halo local warm: {lineup or 'this lineup'} has no local lanes (no `ol:` models): nothing to warm"
    else:
        verb = "would load" if dry else "loaded"
        out["line"] = (f"halo local warm {lineup}: {out['loaded']} {verb}" + (f" in {secs(out['seconds'])}" if out["loaded"]
                       and not dry else "") + f", {out['warm']} already warm, {out['later']} pivot{'s' * (out['later'] != 1)} later")
    out["seconds"] = round(out["seconds"], 1)
    return out


def _lineup_named(names: list) -> "Optional[str]":
    from halo_harness.teams_yaml import resolve_team_template
    if len(names) == 1 and resolve_team_template(names[0]) is not None:
        return names[0]
    if not names:
        from halo_harness.teams_runtime import active_team_name
        try:
            active = active_team_name(None)
        except Exception:
            active = None
        return active if active and resolve_team_template(active) is not None else None
    return None


def cmd_warm(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo local warm", description=(
        "Pre-warm a lineup's warm set (the models that co-reside on each card): what is not resident is loaded, "
        "each row says how long it took; the models that cannot co-reside pivot later. Names that are not a lineup "
        "are models (the 2.0.7 form)."))
    parser.add_argument("names", nargs="*", help="a lineup (default: the active one), or model names")
    parser.add_argument("--host", default=None, help="only this Ollama host (its name here)")
    parser.add_argument("--keep-alive", default=None, help="how long the weights stay (30m, 24h, -1); default: the "
                                                           "profile's, else the host's")
    parser.add_argument("--dry", action="store_true", help="say what it would load, load nothing")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    lineup = _lineup_named(args.names)
    if lineup is None:
        from halo_harness.local_cli import _cmd_warm
        rest = list(args.names) + (["--host", args.host] if args.host else [])
        return _cmd_warm(rest + ["--keep-alive", args.keep_alive or "30m"])
    got = warm_lineup(lineup, host=args.host, keep_alive=args.keep_alive, dry=args.dry,
                      say=None if args.json else print)
    if args.json:
        print(json.dumps({k: v for k, v in got.items()}, indent=2, default=str))
    else:
        print(got["line"])
    failed = any(r["state"] == "failed" for h in got["hosts"] for r in h["rows"])
    return 1 if failed else 0
