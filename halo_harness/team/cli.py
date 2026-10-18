"""halo_harness.team.cli -- `halo team ...` (docs/TEAM.md, docs/COMMANDS.md).

    halo team init [--force] [--json]                    write .halo/team.yaml (and a starter brief)
    halo team validate [--json]                          every problem, one line each (exit 2 when any)
    halo team run [stage] [--force] [--new] [--run ID] [--watch] [--json]
                                                         start a stage (default: the first pending manual one)
    halo team status [--run ID] [--json]                 the run's state, what waits, the cost
    halo team board [--run ID] [--json]                  every stage: state, members, trigger, gate, cost
    halo team answer <stage> accept|redo|stop [--text T] [--run ID] [--json]
    halo team stop [--reason R] [--run ID] [--json]
    halo team log [--since N] [--run ID] [--json]        the run's events
    halo team blocks [block] [--json]                    each block's claims and its last changes
    halo team coach [run] [--json]                       the post-run coach's card (read only)

`run` checks the file (exit 2 on a problem) and runs the lineup preflight
for every member that works here (exit 2 on a blocking finding; `--force`
runs anyway), then drives the run in this process until it is idle or
waits at a gate (`--watch`: until the run ends, the block watchers armed).
`answer` and `stop` act through a runner that is live on the run, else run
it here. Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage,
problems or preflight.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from halo_harness.team import board as BD
from halo_harness.team import spec as S

VERBS = ("init", "validate", "run", "status", "board", "answer", "stop", "log", "blocks", "coach")
USAGE = __doc__.split("\n\n")[1]


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo team {verb}")
    if verb == "init":
        p.add_argument("--force", action="store_true", help="overwrite an existing .halo/team.yaml")
    if verb == "run":
        p.add_argument("stage", nargs="?", default=None)
        p.add_argument("--force", action="store_true", help="run even when the lineup preflight finds problems")
        p.add_argument("--new", action="store_true", help="start a new run instead of continuing the open one")
        p.add_argument("--watch", action="store_true", help="keep running: block_change stages fire as blocks change")
    if verb == "answer":
        p.add_argument("stage")
        p.add_argument("action", help="accept, redo or stop")
        p.add_argument("--text", default="", help="the instruction a redo runs with (or a note)")
    if verb == "stop":
        p.add_argument("--reason", default="stopped by the user")
    if verb == "log":
        p.add_argument("--since", type=int, default=0, help="skip the first N events")
    if verb == "blocks":
        p.add_argument("block", nargs="?", default=None)
    if verb not in ("init", "validate", "blocks"):
        p.add_argument("--run", default=None, help="a run id (default: the latest run)")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def _err(text: str, code: int = 1) -> int:
    print(f"halo team: {text}", file=sys.stderr)
    return code


def _out(args, data, text: str = "") -> None:
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    elif text:
        print(text)


def _team():
    """`(team, None)` or `(None, exit code)`."""
    try:
        team = S.load_team()
    except ValueError as e:
        return None, _err(str(e), 2)
    if team is None:
        return None, _err(f"no team file in {S.team_root()} (halo team init writes .halo/team.yaml)")
    return team, None


def _run_dir(team, ref):
    run_dir = BD.find_run(Path(team["root"]), ref)
    if run_dir is None:
        return None, _err(f"no team run {ref!r}" if ref else "no team run yet (halo team run starts one)")
    return run_dir, None


def init_files(root) -> list:
    """Write `<root>/.halo/team.yaml` from the template and a starter `docs/BRIEF.md` (kept when it is
    there); the paths written. `halo team init` and Studio's `POST team/init` (3.0.8.0 R2) both call it."""
    path = S.repo_team_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(S.template_text(), encoding="utf-8")
    made = [str(path)]
    brief = Path(root) / "docs" / "BRIEF.md"
    if not brief.exists():
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("# Brief\n\nWhat this team makes, for whom, and what done looks like.\n", encoding="utf-8")
        made.append(str(brief))
    return made


def cmd_init(args) -> int:
    root = S.team_root()
    path = S.repo_team_path(root)
    if path.exists() and not args.force:
        return _err(f"{path} exists (--force overwrites it)")
    made = init_files(root)
    _out(args, {"ok": True, "written": made}, "wrote " + ", ".join(made) + "\nnext: halo team validate")
    return 0


def cmd_validate(args) -> int:
    from halo_harness.team.spec_check import preflight_findings
    team, code = _team()
    if team is None:
        return code
    problems = S.validate_team(team, cwd=team["root"])
    warns = [f for f in preflight_findings(team, cwd=team["root"]) if f["severity"] != "blocks"]
    lines = [f"  {p}" for p in problems] + [f"  warning: {w['text']}" for w in warns]
    text = f"{team['path']}: " + (f"{len(problems)} problem(s)" if problems else "valid") + ("\n" + "\n".join(lines) if lines else "")
    _out(args, {"ok": not problems, "path": team["path"], "problems": problems, "warnings": warns}, text)
    return 2 if problems else 0


def handler(verb: str):
    from halo_harness.team import cli_run
    return {"init": cmd_init, "validate": cmd_validate, "run": cli_run.cmd_run, "status": cli_run.cmd_status,
            "board": cli_run.cmd_board, "answer": cli_run.cmd_answer, "stop": cli_run.cmd_stop,
            "log": cli_run.cmd_log, "blocks": cli_run.cmd_blocks}[verb]


def cmd_team(argv) -> int:
    argv = list(argv or [])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage:\n" + USAGE)
        return 0 if argv else 2
    verb = argv[0]
    if verb not in VERBS:
        print(f"halo team: unknown verb {verb!r}\nusage:\n{USAGE}", file=sys.stderr)
        return 2
    if verb == "coach":  # 3.0.9.0 R3 (coach_cli.py)
        from halo_harness.coach_cli import cmd_team_coach
        return cmd_team_coach(argv[1:])
    try:
        args = _parser(verb).parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code or 0)
    return handler(verb)(args)
