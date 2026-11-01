"""halo_harness.local_place_cli -- `halo local place [<lineup>] [--apply] [--json]` (Halo 3.3.7.0 R3;
plans/local-model-fit-brief.md G12): where each of a lineup's local lanes should run across the reachable hosts.

    place_lineup(name=None) -> {lineup, rows, line, lanes}   local_sched/place.solve over the lineup's `ol:` lanes
    cmd_place(argv) -> exit code

Every configured Ollama host is a candidate: one a paired halo host serves answers with its `route` (the helper's
footprint counted), any other -- this machine's own, with no `halo host` running -- from the local reads. The plan
prints one row per lane (its host, fits / warm / the load seconds, and why); `--apply` writes `host_for` on each
moved lane's `<host>|<model>|<role>` profile, Halo-side only: nothing is pulled and nothing loads until a lane asks.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def place_lineup(name: Optional[str] = None) -> dict:
    from halo_harness.local_sched.place import solve
    from halo_harness.local_sched.preview import lanes_for
    if not name:
        from halo_harness.teams_runtime import active_team_name
        try:
            name = active_team_name(None)
        except Exception:
            name = None
    lanes, _declared, lineup = lanes_for(name)
    got = solve(lanes)
    from halo_harness.local_pool.route import pool_host  # 3.3.8.0 R3: the pool is one more option, said
    pool = None
    if pool_host() is not None:
        from halo_harness.local_pool.degrade import status
        pool = status()["line"]
    return {**got, "lineup": lineup, "pool": pool}


def cmd_place(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo local place", description=(
        "Where each local lane of a lineup should run: every reachable Ollama host asked (a halo host's route "
        "answer, else the local reads), scored on fits / warm / the load time / what it evicts. --apply writes "
        "host_for on each moved lane's profile (Halo-side only)."))
    parser.add_argument("lineup", nargs="?", default=None, help="a lineup (default: the active one)")
    parser.add_argument("--apply", action="store_true", help="write host_for on each moved lane's <host>|<model>|<role>")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    from halo_harness.teams_yaml import resolve_team_template
    if args.lineup and resolve_team_template(args.lineup) is None:
        print(f"halo local place: no lineup named {args.lineup!r} (halo teams lists them)", file=sys.stderr)
        return 1
    plan = place_lineup(args.lineup)
    written = []
    if args.apply:
        from halo_harness.local_sched.place import apply
        written = apply(plan)
    if args.json:
        print(json.dumps({**plan, "written": written}, indent=2, default=str))
        return 0
    if not plan["lanes"]:
        print(f"halo local place: {plan['lineup'] or 'this lineup'} has no local lanes (no `ol:` models)")
        return 0
    print(f"halo local place {plan['lineup']}: {plan['line']}")
    for r in plan["rows"]:
        to = r["host"] or "nowhere"
        moved = f" (from {r['from_host']}: --apply writes host_for)" if r.get("moved") and not args.apply else ""
        print(f"  {r['lane']}: {r['model']} on {to} -- {r['why']}{moved}")
    if plan.get("pool"):
        print(f"  pool (one more option, scored with its decode penalty): {plan['pool']}")
    for line in written:
        print(f"  wrote: {line}")
    return 0
