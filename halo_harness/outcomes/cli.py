"""halo_harness.outcomes.cli -- `halo outcomes` and `halo models --measured`
(Halo 3.1.8.0 R3, docs/COMMANDS-supervise.md, docs/OUTCOMES.md).

    halo outcomes [--bio B] [--model M] [--kind K] [--since 7d|24h|2026-10-20] [--limit N] [--json]
        one row per agent task, newest last: when, where (run / session), the task, bio, model,
        kind, outcome (and what checked it), returns, cost, tests passed/failed, sources
    halo models --measured [--json]
        one row per model and kind: checked tasks, first-time passes, the rate, the mean cost
"""

from __future__ import annotations

import argparse
import json
import time


def _when(ts) -> str:
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError):
        return "?"


def table(rows: list) -> list:
    if not rows:
        return ["No outcomes recorded yet: an Orchestra run's lanes and a session's sub-agents each add a row "
                "when they end."]
    head = (f"{'when':<11} {'run':<14} {'task':<14} {'bio':<18} {'model':<34} {'kind':<8} {'outcome':<20} "
            f"{'ret':>3} {'cost':>8}  {'tests':>7}  src")
    out = [head]
    for r in rows:
        outcome = str(r.get("outcome") or "") + (f" ({r['check']})" if r.get("check") else "")
        tests = f"{int(r.get('tests_passed') or 0)}/{int(r.get('tests_failed') or 0)}"
        out.append(f"{_when(r.get('ts')):<11} {str(r.get('run') or '')[:14]:<14} {str(r.get('task') or '')[:14]:<14} "
                   f"{str(r.get('bio') or '-')[:18]:<18} {str(r.get('model') or '-')[:34]:<34} "
                   f"{str(r.get('kind') or ''):<8} {outcome[:20]:<20} {int(r.get('returns') or 0):>3} "
                   f"${float(r.get('cost_usd') or 0):>7.4f}  {tests:>7}  {int(r.get('sources') or 0)}")
    out.append(f"{len(rows)} task(s); tests = passed/failed; `halo models --measured` rates the checked ones "
               "per model and kind")
    return out


def cmd_outcomes(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo outcomes", description="Every agent task's outcome (outcomes.jsonl)")
    parser.add_argument("--bio", default="", help="Only this bio's tasks")
    parser.add_argument("--model", default="", help="Only this model's tasks")
    parser.add_argument("--kind", default="", help="Only this kind: code, research, check, writing, plan, review, "
                                                   "media, other")
    parser.add_argument("--since", default="", help="Only tasks since: 7d, 24h, 30m, 2026-10-20 or an epoch")
    parser.add_argument("--limit", type=int, default=50, help="The newest N rows (default 50; 0: all)")
    parser.add_argument("--json", action="store_true", help="The rows as JSON")
    args = parser.parse_args(argv)
    from halo_harness.outcomes.records import read, since_ts
    since = None
    if args.since:
        since = since_ts(args.since)
        if since is None:
            print(f"halo outcomes: --since {args.since!r} does not read: give 7d, 24h, 30m, 2026-10-20 or an epoch")
            return 2
    rows = read(None, since=since, bio=args.bio, model=args.model, kind=args.kind)
    if args.limit and args.limit > 0:
        rows = rows[-args.limit:]
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    print("\n".join(table(rows)))
    return 0


def measured_rows(stats: dict) -> list:
    return [{"model": m, "kind": k, **s} for (m, k), s in sorted(stats.items())]


def cmd_models_measured(*, as_json: bool = False) -> int:
    from halo_harness.outcomes.measured import success_by_model_kind, table_lines
    stats = success_by_model_kind(None)
    if as_json:
        print(json.dumps(measured_rows(stats), indent=1, ensure_ascii=False))
        return 0
    print("\n".join(table_lines(stats)))
    return 0
