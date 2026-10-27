"""halo_harness.ollama_steward.cli_steward -- `halo ollama steward ...`
(Halo 3.3.4.0 R3):

    findings [--host H] [--since 24h] [--json]   what the rules find (rules.py)
    plan [--host H] [--since 24h] [--json]       the fit plan per host (fit.py)
    apply <id>                                    apply one finding's change
    undo                                          revert the newest change in place
    run [--once] [--mode auto|review|off] [--json]
                                                  findings -> plan -> apply per mode
                                                  (steward.py); without --once it
                                                  runs every ten minutes until Ctrl+C
    --watch                                       the steward's job in the foreground (R4,
                                                  job.py): the server-log tail, the timer,
                                                  the agent's notes; prints each line
    status [--json]                               whether a job runs, where, since when, the
                                                  last run's counts and the last note

Reads the ledger, the events, the hardware card and the catalog; writes
only `ollama.profiles` in config.json and `<state>/ollama/steward.jsonl`.
No server setting changes; only `--watch` sends a model request (the job's
note, one call to `ollama.steward.model` when something is new).
"""

from __future__ import annotations

import argparse
import json
import sys

RUN_EVERY_S = 600.0


def _state_dir():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _readers() -> dict:
    from halo_harness.ollama_steward.hardware import hardware_card
    from halo_harness.providers.ollama import get_catalog
    return {"card_reader": hardware_card, "catalog_reader": get_catalog}


def _findings(args):
    from halo_harness.ollama_steward.rules import findings
    return findings(_state_dir(), since=args.since, host=args.host, **_readers())


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default=None, help="only this host (its name here)")
    p.add_argument("--since", default="24h", help="how much of the ledger to judge: 1h, 24h (the default), 7d, ...")
    p.add_argument("--json", action="store_true", help="print JSON instead of lines")


def _plans(args) -> list:
    from halo_harness.ollama_steward.fit import plan
    from halo_harness.ollama_steward.rules import gather
    from halo_harness.ollama_steward.rules_host import _asked, _serving
    ctx = gather(_state_dir(), since=args.since, host=args.host, **_readers())
    by_host: dict = {}
    for g in ctx["groups"]:
        by_host.setdefault(g["host"], []).append(g)
    return [plan(ctx["cards"].get(h) or {}, [_asked(g) for g in gs], ctx["catalogs"].get(h) or {}, host_name=h,
                 other_hosts=lambda m, h=h: _serving(ctx, m, h)) for h, gs in by_host.items()]


def cmd_ollama_steward(argv: list) -> int:
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.fit import format_plan
    from halo_harness.ollama_steward.rules import format_finding
    parser = argparse.ArgumentParser(
        prog="halo ollama steward", add_help=True,
        description="The Ollama steward: what the calls and the server's lines say is wrong per host and model, "
                    "the fit plan for each card, and the profile changes it makes (ollama.profiles). Server-side "
                    "changes are only shown, with the line to set.")
    sub = parser.add_subparsers(dest="what")
    _common(sub.add_parser("findings", help="what the rules find"))
    _common(sub.add_parser("plan", help="the fit plan for each host's card"))
    ap = sub.add_parser("apply", help="apply one finding's profile change (by its id)")
    ap.add_argument("id")
    sub.add_parser("undo", help="revert the newest change still in place")
    rp = sub.add_parser("run", help="findings, the plan, then apply per ollama.steward.apply")
    _common(rp)
    rp.add_argument("--once", action="store_true", help="one pass (R4's job calls this on a timer)")
    rp.add_argument("--mode", choices=steward.MODES, default=None, help="this run only: auto, review or off")
    sp = sub.add_parser("status", help="whether the steward's job runs, where, since when, its last run and note")
    sp.add_argument("--json", action="store_true", help="print JSON instead of lines")
    parser.add_argument("--watch", action="store_true",
                        help="run the steward's job here in the foreground (Ctrl+C stops it): the server log, the "
                             "timer and the notes, each line printed")
    args = parser.parse_args(argv)
    state = _state_dir()
    if args.watch and not args.what:
        return _watch(state)
    try:
        if args.what == "status":
            return _status(args, state)
        if args.what == "findings":
            found = _findings(args)
            if args.json:
                print(json.dumps(found, indent=2, default=str))
            elif not found:
                print(f"no findings in the last {args.since}: the calls in the ledger and the server's lines look right")
            for f in ([] if args.json else found):
                print("\n".join(format_finding(f)))
            return 0
        if args.what == "plan":
            plans = _plans(args)
            if args.json:
                print(json.dumps(plans, indent=2, default=str))
                return 0
            if not plans:
                print("nothing to plan: no calls in the ledger's window")
            for p in plans:
                print("\n".join(format_plan(p)))
            return 0
        if args.what == "apply":
            row, why = steward.apply_by_id(state, args.id, **_readers())
            print(row["say"] if row else f"halo ollama steward apply: {why}", file=sys.stdout if row else sys.stderr)
            return 0 if row else 1
        if args.what == "undo":
            row = steward.undo_last(state)
            print(row["say"] if row else "nothing to undo: no steward change is in place")
            return 0
        if args.what == "run":
            return _run(args, state)
    except ValueError as e:
        print(f"halo ollama steward: {e}", file=sys.stderr)
        return 2
    parser.print_help()
    return 0


def _run(args, state) -> int:
    import time
    from halo_harness.ollama_steward import steward
    while True:
        done = steward.run(state, mode_name=args.mode, since=args.since, host=args.host,
                           say=(lambda s: None) if args.json else print, **_readers())
        if args.json:
            print(json.dumps({k: v for k, v in done.items()}, indent=2, default=str))
        else:
            print(f"steward ({done['mode']}): {len(done['findings'])} findings, {len(done['applied'])} applied, "
                  f"{len(done['proposed'])} proposed, {len(done['rolled_back'])} rolled back")
        if args.once:
            return 0
        try:
            time.sleep(RUN_EVERY_S)
        except KeyboardInterrupt:
            return 0


def _status(args, state) -> int:
    from halo_harness.ollama_steward import job_state, notes
    from halo_harness.ollama_steward.agent import choose_model
    st = job_state.status(state)
    if not st.get("running"):  # the model a job started now would use
        st["model"], st["model_why"] = choose_model(state_dir=state)
    last = notes.latest(state, stages=("note",)) or notes.latest(state, stages=("change", "finding"))
    if args.json:
        print(json.dumps({**st, "last_note": last}, indent=2, default=str))
        return 0
    for line in job_state.format_status(st, last_note=last):
        print(line)
    return 0


def _watch(state) -> int:
    from halo_harness.ollama_steward.job import StewardJob
    job = StewardJob(state, where="watch", say=print)
    ok, why = job.start()
    print(why, file=sys.stdout if ok else sys.stderr)
    if not ok:
        return 1
    try:
        while not job.stop_event.wait(1.0):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        job.stop()
    print("steward job stopped")
    return 0
