"""halo_harness.start_cli -- `halo start`, the guided first run (Halo
3.1.1.0 R1; the steps live in halo_harness/start/).

    halo start [--lineup NAME] [--repo DIR] [--file F ...] [--model REF] [--yes] [--json] [--no-studio]
    halo start --explain     only the card: what it does, the models, the cost, the time, what it writes

3.2.2.0 R2: the first screen is the card (start/card.py), before step 1's
Enter; `--yes` prints it and goes on, `--json` leaves it out.

One screen per step, each with one sentence of why and the command it
runs: Enter runs the step, q stops the start. At the plan, Enter approves,
s opens Studio's plan canvas (and waits for the decision made there), q
stops. `--yes` runs straight through (the plan approved); `--json` prints
only the machine summary at the end (and asks nothing). The real model you
configured does the work; with no provider configured the start says so
and offers Setup in Studio (Enter; `n` runs the terminal wizard, 3.3.0.0 R4). `HALO_START_FAKE=1` runs the whole path on fake
model calls (tests, a dry look).

Exit codes: 0 every step done, 1 a step failed or the start was stopped,
2 usage or no provider. 3.2.2.0 R1: any other error is one line
(`<Type>: <message>`) and the log holding its traceback
(`<state>/start/<date>/<run or start>-error.log`), exit 1; no traceback
reaches the terminal.
"""

from __future__ import annotations

import argparse
import json
import sys

from halo_harness.start import steps as S


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo start", description="The guided first run: a lineup, a sample repo, one "
                                "real Orchestra goal on your models with a reviewed plan, the run, the report and the "
                                "coach. It opens on a card saying what it does, costs and writes.")
    p.add_argument("--lineup", default=S.DEFAULT_LINEUP, help=f"the shipped lineup to copy (default {S.DEFAULT_LINEUP})")
    p.add_argument("--repo", default=None, metavar="DIR", help="run in this git repo instead of the sample")
    p.add_argument("--file", dest="files", action="append", default=None, metavar="F",
                   help="with --repo: a file the workers share (repeatable; default basket.py)")
    p.add_argument("--model", default=None, metavar="REF", help="the model every part uses (default: your roles)")
    p.add_argument("--yes", action="store_true", help="run straight through: no Enter between steps, the plan approved")
    p.add_argument("--json", action="store_true", help="print only the summary as JSON at the end (asks nothing)")
    p.add_argument("--no-studio", dest="studio", action="store_false", help="do not offer Studio's plan canvas")
    p.add_argument("--explain", action="store_true", help="print only the card (what it does, the models it will "
                   "call, the estimated cost, the time, what it writes) and exit")
    return p


def _card(args, run=None) -> "list[str]":
    from halo_harness.start.card import card_lines
    from halo_harness.start import fake
    return card_lines(lineup=args.lineup, state_dir=run.state_dir if run is not None else None, model=args.model,
                      fake=run.fake if run is not None else fake.enabled(), repo=args.repo)


def _open_studio(run) -> str:
    from halo_harness.studio.launch import launch_detached
    try:
        return launch_detached("orchestra", cwd=run.repo, state_dir=run.state_dir)
    except Exception:
        return ""


def _offer_init(as_json: bool) -> int:
    from halo_harness.start.provider import NO_PROVIDER
    if as_json:
        print(json.dumps({"ok": False, "reason": "no_provider", "message": NO_PROVIDER}))
        return 2
    print(NO_PROVIDER)
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            answer = input("Open Setup in Studio? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 2
        from halo_harness.init_cli import cmd_init
        if answer in ("n", "no"):  # 3.3.0.0 R4: the terminal wizard
            return cmd_init(["--terminal"])
        if answer in ("", "y", "yes"):  # Enter: Setup in Studio, the same door as halo init
            from halo_harness.studio.setup_door import SetupTarget, cli_door
            if not cli_door(SetupTarget(first=True), terminal_cli="halo init --terminal", fallback="wizard"):
                return cmd_init(["--terminal"])
            print("Set a provider up there, then run halo start again.")
    return 2


def _crashed(exc: Exception, run, as_json: bool) -> int:
    """A failure outside the walk: one line on stderr naming the log with the traceback, exit 1."""
    from halo_harness.start.errors import failed_summary
    try:
        state_dir, run_dir = (run.state_dir, run.run_dir) if run is not None else (None, None)
    except Exception:
        state_dir, run_dir = None, None
    summary = failed_summary(state_dir, run_dir, exc)
    line, path = summary["reason"], summary["error_log"]
    if as_json:
        print(json.dumps(summary))
    text = f"halo start: {line}" + (f" -- the full error is in {path}" if path else "")
    try:
        print(text, file=sys.stderr)
    except UnicodeEncodeError:  # a console that cannot show the message's characters
        print(text.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    return 1


def cmd_start(argv) -> int:
    args = _parser().parse_args(list(argv))
    if args.explain:
        for line in _card(args):
            print(line)
        return 0
    built: list = []  # the StartRun, once there is one (its state dir and run folder name the log)
    try:
        return _start(args, built)
    except Exception as e:
        return _crashed(e, built[0] if built else None, args.json)


def _start(args, built: list) -> int:
    from halo_harness.start.engine import Options, StartRun
    from halo_harness.start.screen import Screen, ask
    yes = bool(args.yes or args.json)
    opts = Options(lineup=args.lineup, repo=args.repo, files=tuple(args.files or S.GOAL_FILES), yes=yes,
                   model=args.model, studio=args.studio)
    screen = None if args.json else Screen()
    run = StartRun(opts, emit=screen, ask=None if yes else ask, open_studio=_open_studio)
    built.append(run)
    if not args.json:
        print("halo start: the guided first run" + (" (fake model calls: HALO_START_FAKE=1)" if run.fake else ""))
        print()
        for line in _card(args, run):
            print(f"  {line}" if line else "")
    try:
        summary = run.run()
    except KeyboardInterrupt:
        run.cancel()
        print("\nhalo start: stopped (Ctrl+C)", file=sys.stderr)
        return 1
    if summary.get("reason") == "no_provider":
        return _offer_init(args.json)
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    elif summary["ok"]:
        print()
        print(f"The start is done: lineup {summary['lineup']}, run {summary['run']} in {summary['repo']}.")
    else:
        print()
        print(f"halo start stopped at {summary.get('stopped_at') or 'the start'}: {summary.get('reason')}")
        if summary.get("error_log"):
            print(f"the full error is in {summary['error_log']}")
    return 0 if summary["ok"] else 1
