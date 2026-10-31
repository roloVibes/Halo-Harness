"""halo_harness.local_bench_cli -- Halo 3.3.6.0 R5: `halo local bench | tune | changes | revert` (dispatched by
local_cli.cmd_local; `halo models bench` is the same as `halo local bench`).

    halo local bench [--host H] [--model M | --all] [--quick] [--yes] [--json]
        the cost line first (local: time and a busy card, never dollars), then one line per window as it lands, then
        the speed card; --all = every installed model on the host, largest first
    halo local tune [--host H] [--json] [--apply ID [--scope S] [--session SID]]
        the tuning report: the warm set, each model's windows, the reserve, the findings, every option with what it
        writes and how long it takes; --apply lands a Halo-side option (scope keep unless you name another)
    halo local changes [--host H] [--all] [--json]       the changes in force with their scopes (--all: reverted too)
    halo local revert <id> | --all [--scope S] [--host H]   put one or all back; each line says what it put back
"""

from __future__ import annotations

import argparse
import json
import sys


def _host(name):
    from halo_harness.providers.ollama import resolve_ollama_host
    return resolve_ollama_host(name or None)


def _card(host):
    from halo_harness.studio import ollama_hosts_view as V
    return V.card_of(host)


def _models(host, model, all_models: bool) -> list:
    if model:
        return [model]
    if not all_models:
        return []
    from halo_harness.studio import ollama_hosts_view as V
    rows = [r for r in V.catalog_of(host).get("models") or [] if isinstance(r, dict) and r.get("size")]
    return [str(r.get("model") or r.get("name")) for r in sorted(rows, key=lambda r: -int(r["size"]))]


def _ask(question: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        print("no terminal to ask on: run it again with --yes")
        return False
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def cmd_bench(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers import local_bench as LB
    from halo_harness.providers.local_bench_runs import lines
    p = argparse.ArgumentParser(prog="halo local bench", description="The bench: a measured battery per model on its host "
                                "(cold load, three windows, the GPU window, the reply reserve) -> the speed card.")
    p.add_argument("--host", default="", help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--model", default="", help="the model to bench")
    p.add_argument("--all", action="store_true", help="every installed model on the host, largest first")
    p.add_argument("--quick", action="store_true", help="one window: the planner's ceiling")
    p.add_argument("--yes", action="store_true", help="run without asking")
    p.add_argument("--json", action="store_true", help="the speed cards as JSON")
    args = p.parse_args(argv)
    host = _host(args.host)
    if host is None:
        print(f"no Ollama host named {args.host!r} (ollama.hosts)")
        return 1
    models = _models(host, args.model, args.all)
    if not models:
        print("name a model (--model M) or bench every installed one (--all)")
        return 2
    card, state = _card(host), bridge_home()
    mins = sum(LB.estimate(host, m, card=card, state_dir=state, quick=args.quick)[0] for m in models)
    print(LB.cost_line(host.name, mins) + (f" ({len(models)} models)" if len(models) > 1 else ""))
    if not _ask("Run the bench now?", args.yes):
        return 1
    out, rc = [], 0
    for m in models:
        print(f"{m} on {host.name}:")
        got = LB.bench(host, m, quick=args.quick, card=card, state_dir=state, on_line=(lambda s: None) if args.json
                       else (lambda s: print(f"  {s}")))
        out.append(got)
        if not got.get("ok"):
            print(f"  {got.get('say')}")
            rc = 1
            continue
        if not args.json:
            print("\n".join(f"  {x}" for x in lines(got)))
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    return rc


def _session_for(given: str):
    if given:
        return given, None
    try:
        from halo_harness.remote.registry import list_live
        rows = sorted(list_live(), key=lambda e: -(e.get("started") or 0))
        return (rows[0].get("session_id"), rows[0].get("pid")) if rows else (None, None)
    except Exception:
        return None, None


def cmd_tune(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import tune_lines
    from halo_harness.ollama_steward.tune_report import format_report, report_for
    p = argparse.ArgumentParser(prog="halo local tune", description="The tuning report: the planner's options for the "
                                "whole host; Apply for Halo's side, the exact line for the server's.")
    p.add_argument("--host", default="", help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--json", action="store_true", help="the report as JSON")
    p.add_argument("--apply", default="", metavar="ID", help="land a Halo-side option (its id from the report)")
    p.add_argument("--scope", default="keep", choices=("session", "until-restart", "keep"), help="the change's scope")
    p.add_argument("--session", default="", help="the session a `session` scope ends with (default: the newest live one)")
    args = p.parse_args(argv)
    host = _host(args.host)
    if host is None:
        print(f"no Ollama host named {args.host!r} (ollama.hosts)")
        return 1
    r = report_for(bridge_home(), host.name)
    if args.apply:
        sid, pid = _session_for(args.session) if args.scope == "session" else (None, None)
        got = tune_lines.apply(bridge_home(), host.name, args.apply, scope=args.scope, session_id=sid, session_pid=pid,
                               report=r)
        print("\n".join(got["lines"]))
        return 0 if got["ok"] else 1
    print(json.dumps(r, indent=2, default=str) if args.json else "\n".join(format_report(r)))
    return 0


def cmd_changes(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import changes as C
    p = argparse.ArgumentParser(prog="halo local changes", description="The changes Halo made to local models' profiles, "
                                "each with its scope.")
    p.add_argument("--host", default="", help="one host's only")
    p.add_argument("--all", action="store_true", help="the reverted ones too")
    p.add_argument("--json", action="store_true", help="as JSON")
    args = p.parse_args(argv)
    rows = [r for r in C.read(bridge_home()) if (args.all or not r.get("reverted_at"))
            and (not args.host or str(r.get("host")).lower() == args.host.lower())]
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    print("\n".join(C.line_of(r) for r in rows) if rows else "no change in force" + (f" on {args.host}" if args.host else ""))
    return 0


def cmd_revert(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import changes as C
    p = argparse.ArgumentParser(prog="halo local revert", description="Put one change back, or all of them.")
    p.add_argument("id", nargs="?", default="", help="the change's id (halo local changes)")
    p.add_argument("--all", action="store_true", help="every change in force")
    p.add_argument("--scope", default="", choices=("", "session", "until-restart", "keep"), help="only this scope's")
    p.add_argument("--host", default="", help="only this host's")
    args = p.parse_args(argv)
    if not args.id and not args.all:
        print("name a change (halo local changes lists them) or --all")
        return 2
    said = C.revert(bridge_home(), "all" if args.all else args.id, "reverted by hand", scope=args.scope or None,
                    host=args.host or None)
    print("\n".join(said))
    return 0


COMMANDS = {"bench": cmd_bench, "tune": cmd_tune, "changes": cmd_changes, "revert": cmd_revert}
