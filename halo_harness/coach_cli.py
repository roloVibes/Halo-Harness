"""halo_harness.coach_cli -- `halo coach` and the four per-kind `coach` verbs
(Halo 3.0.9.0 round R3; 3.1.3.0 R1 closed the loop):

    halo coach [RUN] [--model [--refresh]] [--apply ID [--yes]] [--json] [--repo DIR]
    halo coach --undo [APPLY_ID]
    halo orchestra coach [RUN] ...          an Orchestra run (default: the latest of this repo)
    halo flow coach [RUN] ...               a flow run (default: the last)
    halo fleet mission coach <id> ...       a mission of this harness (or the shared missions folder)
    halo team coach [RUN] ...               a team run of this repo (default: the latest)

`halo coach` takes a run of any kind (a folder, an id or a prefix; no RUN:
the latest, as `halo work` finds it). Each prints the same card
(orchestra/coach.py `format_card`): one block per suggestion with its id,
its why lines, what Apply writes, its applied state and the lead's
paragraph once asked. `--model` asks the run's lead for one paragraph per
card (kept in `<run>/coach.ask.json`; a second `--model` reads them back,
`--refresh` asks again). `--apply ID` prints the confirm card (the file,
the diff) and asks y/N (`--yes` skips; with `--json` and no `--yes` it
prints the preview and writes nothing). `--undo` puts back the file of an
apply (the last one not undone when no id), when the file still holds what
the apply wrote. `--json` prints the result, `paragraph` per suggestion.
Exit codes: 0 done, 1 no such run / the change could not be made / the
undo was refused, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def add_flags(p) -> None:
    p.add_argument("--json", action="store_true", help="the coach's result as JSON")
    p.add_argument("--model", action="store_true", help="ask the run's lead for one paragraph per card")
    p.add_argument("--refresh", action="store_true", help="with --model: ask again instead of reading the kept paragraphs")
    p.add_argument("--apply", default=None, metavar="ID", help="write the change the card ID names (after y/N)")
    p.add_argument("--yes", action="store_true", help="with --apply: skip the y/N")
    p.add_argument("--preview", action="store_true", help=argparse.SUPPRESS)  # /coach: the confirm card, no prompt


def _emit(data, as_json: bool, text: str) -> None:
    print(json.dumps(data, indent=2, default=str) if as_json else text)


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, OSError):
        return False


def preview_text(p: dict) -> str:
    head = [f"apply {p['id']}: {p['target']} {p.get('name') or ''}: {p['field']} = {p['value']}".replace("  ", " "),
            f"  file: {p['file']}" + ("" if p["exists"] else " (new: the apply creates it)")]
    return "\n".join(head + [f"  {line}" for line in p["diff"] or ["(no change: the file already holds it)"]])


def _apply(run_dir, result: dict, a, cwd) -> int:
    from halo_harness.orchestra import coach_apply as CA
    try:
        p = CA.preview(result, a.apply, run_dir, cwd=cwd)
        if a.json and not a.yes:
            _emit({"preview": p, "applied": None}, True, "")
            return 0
        if not a.json:
            print(preview_text(p))
        if getattr(a, "preview", False) and not a.yes:
            print(f"nothing written yet: add --yes to write it (/coach --apply {p['id']} --yes)")
            return 0
        if not a.yes and not _confirm("Apply this change? [y/N] "):
            print("nothing written")
            return 0
        row = CA.apply(result, a.apply, run_dir, cwd=cwd)
    except CA.ApplyError as e:
        print(f"halo coach: {e}", file=sys.stderr)
        return 1
    _emit({"preview": p, "applied": row}, a.json,
          f"applied {row['apply_id']}: {row['file']} (undo: halo coach --undo {row['apply_id']})")
    return 0


def run_card(run_dir, a, cwd=None) -> int:
    """The card for one run folder, after --model / --apply when given."""
    from halo_harness.orchestra.coach import cached, format_card, overlay
    try:
        result = cached(run_dir, cwd=cwd)
    except ValueError as e:
        print(f"halo coach: {e}", file=sys.stderr)
        return 1
    if getattr(a, "apply", None):
        return _apply(run_dir, result, a, cwd)
    if getattr(a, "model", False):
        from halo_harness.orchestra.coach_ask import ask_all
        ask_all(run_dir, result, refresh=a.refresh, cwd=cwd)
        result = overlay(result, run_dir)
    _emit(result, a.json, format_card(result))
    return 0


def _parse(prog: str, argv: list, run_help: str, required: bool = False, top: bool = False):
    p = argparse.ArgumentParser(prog=prog, description="The post-run coach: its cards, the lead's paragraphs, "
                                                       "Apply with one confirm, Undo.")
    p.add_argument("run", nargs=None if required else "?", default=None, help=run_help)
    add_flags(p)
    if top:
        p.add_argument("--undo", nargs="?", const="", default=None, metavar="APPLY_ID",
                       help="put back the file of an apply (default: the last one not undone)")
        p.add_argument("--repo", default=None, help="the repo whose Orchestra and team runs to look in (default: here)")
    try:
        return p.parse_args(argv), 0
    except SystemExit as e:
        return None, int(e.code or 0)


def cmd_undo(apply_id, as_json: bool = False) -> int:
    from halo_harness.orchestra.coach_record import undo
    ok, message, rec = undo(apply_id or None)
    if as_json:
        _emit({"ok": ok, "message": message, "apply_id": (rec or {}).get("apply_id"), "file": (rec or {}).get("file")},
              True, "")
    else:
        print(message if ok else f"halo coach: {message}", file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_coach(argv: list) -> int:
    """`halo coach`: a run of any kind, or --undo."""
    a, rc = _parse("halo coach", argv, "run folder, id or id prefix of any kind (default: the latest)", top=True)
    if a is None:
        return rc
    if a.undo is not None:
        return cmd_undo(a.undo, a.json)
    from halo_harness.work_cli import _resolve
    repo = Path(a.repo).resolve() if a.repo else Path.cwd()
    run_dir = _resolve(a.run, repo)
    if run_dir is None:
        print(f"halo coach: no run {a.run!r} (halo work lists the latest)" if a.run else "halo coach: no runs here",
              file=sys.stderr)
        return 1
    return run_card(run_dir, a)


def add_orchestra_parser(sub) -> None:
    c = sub.add_parser("coach", help="the post-run coach: what to change in the bios, models, tools or plan")
    c.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
    add_flags(c)


def cmd_orchestra_coach(args, repo: Path) -> int:
    from halo_harness.orchestra import goal as G
    run_dir = G.resolve_run(repo, args.run)
    if run_dir is None:
        print(f"halo orchestra coach: no run {args.run!r} in this repo" if args.run else
              "halo orchestra coach: no runs in this repo", file=sys.stderr)
        return 1
    return run_card(run_dir, args)


def cmd_flow_coach(argv: list) -> int:
    from halo_harness.flows import state
    a, rc = _parse("halo flow coach", argv, "run id or prefix (default: the last)")
    if a is None:
        return rc
    run_dir = state.find_run(a.run or "last")
    if run_dir is None:
        print(f"halo flow coach: no run {a.run or 'last'!r} (halo flow runs lists them)", file=sys.stderr)
        return 1
    return run_card(run_dir, a)


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
    return run_card(S.folder(identity.home(), a.run), a)


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
    return run_card(run_dir, a)
