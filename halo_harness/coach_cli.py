"""halo_harness.coach_cli -- the four `coach` verbs (Halo 3.0.9.0 round R3):

    halo orchestra coach [RUN] [--json]     an Orchestra run (default: the latest of this repo)
    halo flow coach [RUN] [--json]          a flow run (default: the last)
    halo fleet mission coach <id> [--json]  a mission of this harness (or the shared missions folder)
    halo team coach [RUN] [--json]          a team run of this repo (default: the latest)

Each prints the same card (orchestra/coach.py `format_card`): one block per
suggestion with its why lines and what Apply would fill in. `--json` prints
the coach's result. Read only: nothing is written, no model is called.
Exit codes: 0 the card, 1 no such run, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print(result: dict, as_json: bool) -> int:
    from halo_harness.orchestra.coach import format_card
    print(json.dumps(result, indent=2, default=str) if as_json else format_card(result))
    return 0


def _card(run_dir, as_json: bool, cwd=None) -> int:
    from halo_harness.orchestra.coach import coach
    try:
        return _print(coach(run_dir, cwd=cwd), as_json)
    except ValueError as e:
        print(f"halo coach: {e}", file=sys.stderr)
        return 1


def add_orchestra_parser(sub) -> None:
    c = sub.add_parser("coach", help="the post-run coach: what to change in the bios, models, tools or plan")
    c.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
    c.add_argument("--json", action="store_true", help="the coach's result as JSON")


def cmd_orchestra_coach(args, repo: Path) -> int:
    from halo_harness.orchestra import goal as G
    run_dir = G.resolve_run(repo, args.run)
    if run_dir is None:
        print(f"halo orchestra coach: no run {args.run!r} in this repo" if args.run else
              "halo orchestra coach: no runs in this repo", file=sys.stderr)
        return 1
    return _card(run_dir, args.json)


def _parse(prog: str, argv: list, run_help: str, required: bool = False):
    p = argparse.ArgumentParser(prog=prog, description="The post-run coach (read only).")
    p.add_argument("run", nargs=None if required else "?", default=None, help=run_help)
    p.add_argument("--json", action="store_true", help="the coach's result as JSON")
    try:
        return p.parse_args(argv), 0
    except SystemExit as e:
        return None, int(e.code or 0)


def cmd_flow_coach(argv: list) -> int:
    from halo_harness.flows import state
    a, rc = _parse("halo flow coach", argv, "run id or prefix (default: the last)")
    if a is None:
        return rc
    run_dir = state.find_run(a.run or "last")
    if run_dir is None:
        print(f"halo flow coach: no run {a.run or 'last'!r} (halo flow runs lists them)", file=sys.stderr)
        return 1
    return _card(run_dir, a.json)


def cmd_mission_coach(argv: list) -> int:
    from halo_harness.fleet import identity
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_store as S
    a, rc = _parse("halo fleet mission coach", argv, "the mission id (m-<yyyymmdd>-<4 hex>)", required=True)
    if a is None:
        return rc
    if not M.valid_id(a.run) or not (S.folder(identity.home(), a.run) / "mission.json").is_file():
        print(f"halo fleet mission coach: no mission {a.run!r} here", file=sys.stderr)
        return 1
    return _card(S.folder(identity.home(), a.run), a.json)


def cmd_team_coach(argv: list) -> int:
    from halo_harness.team import board as BD
    from halo_harness.team.spec import team_root
    a, rc = _parse("halo team coach", argv, "run id (default: the latest)")
    if a is None:
        return rc
    run_dir = BD.find_run(team_root(), a.run)
    if run_dir is None:
        print(f"halo team coach: no team run {a.run!r}" if a.run else "halo team coach: no team runs here",
              file=sys.stderr)
        return 1
    return _card(run_dir, a.json)
