"""halo_harness.local_advise_cli -- `halo local advise [--host H] [--lineup L] [--json]` (Halo 3.3.7.0 R4; plans/local-
model-fit-brief.md Part J; docs/COMMANDS-local.md): the roster adviser's lines (models_library/advise.py), ranked by
value per gigabyte, each with the one command that does its one thing. Nothing downloads, deletes or retires here.
3.3.8.0 R4: then the placement scores -- each lane's score on every candidate across the fleet and the pool, with its
loading tax (the load seconds, the switch, the pool's penalty); a cheaper placement is a `placement` suggestion.
"""

from __future__ import annotations

import argparse
import json


def cmd_advise(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="halo local advise", description=(
        "Review the installed local models against the roles, the host's memory budget, the capability profiles and "
        "the host log: what is missing (gap), what overlaps, what is mismatched, what has a newer line (freshness). "
        "Each line says what it unlocks or frees, what it costs and the command that does it; nothing runs here."))
    ap.add_argument("--host", default=None, help="only this Ollama host")
    ap.add_argument("--lineup", default=None, help="the lineup whose roles it reads (default: the active one)")
    ap.add_argument("--json", action="store_true", help="print the suggestions as JSON")
    a = ap.parse_args(argv)
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_library.advise import advise, remember
    state = bridge_home()
    got = advise(state, a.host, lineup=a.lineup)
    remember(state, got)
    if a.json:
        print(json.dumps(got, indent=2, default=str))
        return 0
    print(got["head"])
    for s in got["suggestions"]:
        print(f"  {s['rank']}. {s['line']}")
    if not got["suggestions"]:
        print("  nothing to add or retire: every role has a model, nothing overlaps and nothing has a newer line")
    lines = (got.get("placement") or {}).get("lines") or []
    if lines:  # 3.3.8.0 R4: every lane's placement score and its loading tax across the fleet and the pool
        print("placement scores (the chosen host first; halo local place --apply moves a lane):")
        for line in lines:
            print(f"  {line}")
    return 0
