"""halo_harness.team.cli_run -- the run verbs of `halo team` (team/cli.py):
run, status, board, answer, stop, log, blocks. The runner's seams are
team/run.py's module-level SPAWN / ORCHESTRA / FLOW / DISPATCH."""

from __future__ import annotations

import sys
import time

from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.team.cli import _err, _out, _run_dir, _team


def _printer():
    def show(entry: dict) -> None:
        print(f"+{float(entry.get('elapsed_s') or 0):7.1f}s  {entry.get('kind', ''):<7} {entry.get('text', '')}",
              flush=True)
    return show


class _Tail:
    def __init__(self, run_dir, show, since: int):
        self.run_dir, self.show, self.seen = run_dir, show, since

    def __call__(self, *_a, **_k) -> None:
        for e in BD.read_events(self.run_dir, since=self.seen):
            self.seen += 1
            self.show(e)


def _drive(team, run_dir, args):
    from halo_harness.team.run import TeamRunner
    runner = TeamRunner(team, run_dir, watch=bool(getattr(args, "watch", False)), cwd=team["root"])
    runner.adopt()
    tail = _Tail(run_dir, _printer() if not args.json else (lambda e: None), len(BD.read_events(run_dir)))
    return runner, tail


def _loop(runner, tail, until: str) -> dict:
    def sleep(s):
        tail()
        time.sleep(s)
    try:
        board = runner.loop(until=until, sleep=sleep)
    except KeyboardInterrupt:
        print("\ninterrupted; the run stays open: halo team status", file=sys.stderr)
        board = runner.board()
    tail()
    return board


def _waiting_line(run_dir, board: dict) -> str:
    from halo_harness.team.budget import held
    from halo_harness.team.stages import read_gate
    gated = [r["id"] for r in board.get("stages") or [] if read_gate(run_dir, r["id"])]
    if gated:
        return f"waiting at {', '.join(gated)}: halo team answer {gated[0]} accept|redo|stop"
    holds = held(run_dir)  # 3.1.2.0 R2 (team/budget.py)
    if holds:
        return (f"held at {holds[0]['stage']}: {holds[0]['text']}; raise budget_usd in the team file and run "
                f"halo team run {holds[0]['stage']} again, or skip it in Studio's Attention queue")
    return f"run {board.get('run')} {board.get('state')}"


def cmd_run(args) -> int:
    from halo_harness.lineup_preflight import blocking, refusal_text
    from halo_harness.team.run import open_run
    from halo_harness.team.validate import preflight_findings
    team, code = _team()
    if team is None:
        return code
    problems = S.validate_team(team, cwd=team["root"], preflight=False)
    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return _err(f"{team['path']} has {len(problems)} problem(s); nothing ran", 2)
    if not args.force:
        findings = preflight_findings(team, cwd=team["root"])
        if blocking(findings):
            print(refusal_text(findings, what=f"team {team['name']}"), file=sys.stderr)
            return 2
    if args.stage and S.stage_by_id(team, args.stage) is None:
        return _err(f"no stage {args.stage!r} (stages: {', '.join(s['id'] for s in team['workflow']['stages'])})", 2)
    try:
        run_dir = open_run(team, run=args.run, new=args.new, cwd=team["root"])
    except ValueError as e:
        return _err(str(e))
    board = BD.read_board(run_dir)
    if BD.runner_live(board):
        return _err(f"run {run_dir.name} has a live runner (pid {board['runner'].get('pid')}): "
                    f"halo team status, or halo team answer / stop")
    if board.get("state") != "open":
        return _err(f"run {run_dir.name} is {board.get('state')} (--new starts another)")
    runner, tail = _drive(team, run_dir, args)
    sid = args.stage or next((r["id"] for r in board.get("stages") or [] if r.get("state") == "pending"
                              and S.parse_trigger(r.get("trigger"))[0] == "manual"), None)
    if sid:
        if not runner.request(sid, "halo team run"):
            return _err(f"stage {sid} is already running or queued")
    elif not args.watch:
        return _err("no pending manual stage to start (name one: halo team run <stage>)")
    if not args.json:
        print(f"team {team['name']}, run {run_dir.name}" + (f": stage {sid}" if sid else ": watching the blocks"))
    board = _loop(runner, tail, "idle" if args.watch else "gate")
    _out(args, board, _waiting_line(run_dir, board))
    row = BD.row(board, sid) if sid else None
    return 1 if row and row.get("state") == "failed" else 0


def status_of(run_dir, team=None) -> dict:
    """The run's state; with `team`, its budget line too (3.1.2.0 R2: spent, forecast, budget, holds)."""
    from halo_harness.team.stages import read_gate
    board = BD.read_board(run_dir)
    rows = board.get("stages") or []
    by: dict = {}
    for r in rows:
        by.setdefault(r.get("state"), []).append(r["id"])
    return {"run": board.get("run"), "team": board.get("team"), "state": board.get("state"),
            "stop_reason": board.get("stop_reason") or "", "runner_live": BD.runner_live(board),
            "stages": by, "waiting": [r["id"] for r in rows if read_gate(run_dir, r["id"])],
            "cost_usd": BD.cost(board), **({"budget": _budget(team, run_dir)} if team else {})}


def _budget(team, run_dir) -> dict:
    from halo_harness.team.budget import summary
    try:
        return summary(team, run_dir, cwd=team["root"])
    except Exception as e:  # the status still prints without its budget line
        return {"error": f"{type(e).__name__}: {e}"}


def cmd_status(args) -> int:
    team, code = _team()
    if team is None:
        return code
    run_dir, code = _run_dir(team, args.run)
    if run_dir is None:
        return code
    from halo_harness.work.forecast import money
    st = status_of(run_dir, team)
    b = st.get("budget") or {}
    lines = [f"team {st['team']}, run {st['run']}: {st['state']}" + (f" ({st['stop_reason']})" if st["stop_reason"] else "")
             + (", runner live" if st["runner_live"] else ""),
             f"  spent ${st['cost_usd']:.4f} · forecast {money(b.get('forecast'))} for the stages still to run · "
             + (f"budget {money(b['budget_usd'])}" if b.get("budget_usd") is not None else "no budget set")]
    lines += [f"  held: {h['stage']} ({h['text']})" for h in b.get("holds") or []]
    lines += [f"  {state}: {', '.join(ids)}" for state, ids in st["stages"].items()]
    if st["waiting"]:
        lines.append(f"  waiting: halo team answer {st['waiting'][0]} accept|redo|stop")
    _out(args, st, "\n".join(lines))
    return 0


def cmd_board(args) -> int:
    team, code = _team()
    if team is None:
        return code
    run_dir, code = _run_dir(team, args.run)
    if run_dir is None:
        return code
    board = BD.read_board(run_dir)
    lines = [f"run {board.get('run')} ({board.get('state')}), ${BD.cost(board):.4f}",
             f"  {'stage':<12} {'kind':<9} {'state':<8} {'members':<18} {'trigger':<22} {'gate':<8} cost     summary"]
    for r in board.get("stages") or []:
        lines.append(f"  {r['id']:<12} {r['kind']:<9} {r['state']:<8} {','.join(r.get('members') or [])[:18]:<18} "
                     f"{str(r.get('trigger'))[:22]:<22} {r.get('gate'):<8} ${float(r.get('cost_usd') or 0):<7.4f} "
                     f"{(r.get('waiting') or r.get('error') or r.get('summary') or '')[:60]}")
    _out(args, board, "\n".join(lines))
    return 0


def cmd_answer(args) -> int:
    from halo_harness.team.stages import write_answer
    team, code = _team()
    if team is None:
        return code
    run_dir, code = _run_dir(team, args.run)
    if run_dir is None:
        return code
    ok, message = write_answer(run_dir, args.stage, args.action, args.text)
    if not ok:
        return _err(message)
    board = BD.read_board(run_dir)
    if BD.runner_live(board) or board.get("state") != "open":
        _out(args, {"ok": True, "message": message, "driven": False}, message)
        return 0
    if not args.json:
        print(message)
    runner, tail = _drive(team, run_dir, args)
    board = _loop(runner, tail, "gate")
    _out(args, {"ok": True, "message": message, "driven": True, "board": board}, _waiting_line(run_dir, board))
    return 0


def cmd_stop(args) -> int:
    team, code = _team()
    if team is None:
        return code
    run_dir, code = _run_dir(team, args.run)
    if run_dir is None:
        return code
    board = BD.read_board(run_dir)
    if board.get("state") != "open":
        return _err(f"run {run_dir.name} is already {board.get('state')}")
    BD.request_stop(run_dir, args.reason)
    if not BD.runner_live(board):
        from halo_harness.team.run import TeamRunner
        TeamRunner(team, run_dir, cwd=team["root"]).tick()
    _out(args, {"ok": True, "run": run_dir.name, "reason": args.reason}, f"run {run_dir.name}: stop -- {args.reason}")
    return 0


def cmd_log(args) -> int:
    team, code = _team()
    if team is None:
        return code
    run_dir, code = _run_dir(team, args.run)
    if run_dir is None:
        return code
    events = BD.read_events(run_dir, since=args.since)
    if args.json:
        _out(args, {"events": events, "next": args.since + len(events)})
    else:
        for e in events:
            _printer()(e)
    return 0


def cmd_blocks(args) -> int:
    from halo_harness.team import blocks as B
    team, code = _team()
    if team is None:
        return code
    if args.block and S.block_by_id(team, args.block) is None:
        return _err(f"no block {args.block!r} (blocks: {', '.join(b['id'] for b in team['blocks'])})")
    rows = [B.block_status(team, args.block, recent=10)] if args.block else B.all_status(team)
    lines = []
    for b in rows:
        lines.append(f"{b['id']} ({b['kind']} {b['path']}, claims {b['claims']}): {b['changes_count']} change(s)")
        lines += [f"  held: {h['key']} by {h['holder']} ({h['state']})" for h in b["holders"]]
        lines += [f"  {c.get('member')}@{c.get('stage')} {c.get('op')} {c.get('key')}" for c in b["recent"]]
    _out(args, rows if not args.block else rows[0], "\n".join(lines) or "no blocks")
    return 0


__all__ = ["cmd_run", "cmd_status", "cmd_board", "cmd_answer", "cmd_stop", "cmd_log", "cmd_blocks", "status_of"]
