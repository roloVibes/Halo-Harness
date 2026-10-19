"""tests.test_team_run -- Halo 3.0.8.0 round R1: the team runner
(halo_harness/team/run.py, run_stage.py, stages.py, triggers.py) through the
seam fakes in tests/helpers/team_rig.py: a manual stage stops at its
required gate, accept fires the `stage_done` stage (two members, the lead
merging the other's hand-back), a block change fires
the orchestra stage once the settle window passes; redo runs the stage again
with the text; stop ends the run; a delegated member's 202 waits, then runs,
then lands; a 403 fails the stage with the reason; a refused write is logged
and refused; a failed acceptance without a gate fails; a seam that raises
fails only its stage; a new runner adopts a run. No model is called.

Run: python -m tests.test_team_run
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _runner(text=R.TEAM, fakes=None, clock=None):
    from halo_harness.team import spec as S
    from halo_harness.team.run import TeamRunner, open_run
    root, state = R.repo(text)
    team = S.load_team(root, state)
    fakes = fakes or R.Fakes()
    run_dir = open_run(team, cwd=root, state_dir=state)
    kw = {"clock": clock} if clock else {}
    return TeamRunner(team, run_dir, **fakes.seams(), **kw), fakes, root


def _states(runner) -> dict:
    return {r["id"]: r["state"] for r in runner.board()["stages"]}


@test
def test_gate_accept_stage_done_and_a_block_change_after_settle(ctx: Ctx):
    from halo_harness.team import stages as ST
    from halo_harness.team.board import read_events, read_stage_file
    now = [1000.0]
    runner, fakes, root = _runner(clock=lambda: now[0])
    ctx.check("request queues the stage", runner.request("draft") and not runner.request("draft"))
    runner.tick()
    ctx.check(f"draft waits at its required gate, got {_states(runner)}", _states(runner)["draft"] == "gated"
              and _states(runner)["review"] == "pending" and runner.status() == "gated")
    gate = ST.read_gate(runner.run_dir, "draft")
    ctx.check(f"gate.json carries the round, the acceptance and the actions, got {gate}",
              gate["round"] == 1 and gate["acceptance"]["ok"] is True and gate["actions"] == ["accept", "redo", "stop"])
    prompt = next(c[3] for c in fakes.calls if c[0] == "spawn" and c[2] == "draft")
    ctx.check("the prompt carries the brief, the write scope and the task",
              "Launch the thing." in prompt and "YOU WRITE ONLY IN: `copy`" in prompt and "stage `draft`" in prompt)
    ok, _msg = ST.write_answer(runner.run_dir, "draft", "accept")
    ctx.check("the answer is written", ok and not ST.write_answer(runner.run_dir, "nope", "accept")[0])
    runner.tick()
    st = _states(runner)
    ctx.check(f"accept: draft done, review ran, build still waits on its block, got {st}",
              st == {"draft": "done", "review": "done", "build": "pending"})
    order = [(c[1], c[2]) for c in fakes.calls if c[0] == "spawn"]
    ctx.check(f"review ran editor first, then the lead writer, got {order}",
              order == [("writer", "draft"), ("editor", "review"), ("writer", "review")])
    lead_prompt = [c[3] for c in fakes.calls if c[0] == "spawn" and c[1:3] == ("writer", "review")][0]
    ctx.check("the lead merges the editor's hand-back", "YOU LEAD THIS STAGE" in lead_prompt
              and "review draft by editor" in lead_prompt)
    ctx.check("handback.md holds both members", "## editor" in read_stage_file(runner.run_dir, "review", "handback.md"))
    refs = read_stage_file(runner.run_dir, "review", "refs.json")
    ctx.check(f"refs.json holds the session ids, got {refs}", refs == {"sessions": {"editor": "s-editor", "writer": "s-writer"}})
    (root / "NOTES.md").write_text("a note\n", encoding="utf-8")
    now[0] += 1
    runner.tick()
    ctx.check("a change opens the settle window (5 s): not yet", _states(runner)["build"] == "pending")
    now[0] += 3
    runner.tick()
    ctx.check("still settling", _states(runner)["build"] == "pending")
    now[0] += 3
    runner.tick()
    ctx.check(f"quiet past settle_s: build ran, got {_states(runner)}", _states(runner)["build"] == "done")
    goal = next(c[2] for c in fakes.calls if c[0] == "orchestra")
    ctx.check(f"the orchestra got the goal with its defaults, got {goal}",
              goal["what"] == "Build the site" and goal["stop_when"] and goal["files"] == [] and goal["lineup"] == "standard")
    now[0] += 30
    runner.tick()
    ctx.check("one fire per window", sum(1 for c in fakes.calls if c[0] == "orchestra") == 1)
    board = runner.board()
    ctx.check(f"every stage done: the run is done, cost summed, got {board['state']}",
              board["state"] == "done" and abs(sum(r["cost_usd"] for r in board["stages"]) - 0.05) < 1e-9)
    kinds = {e["kind"] for e in read_events(runner.run_dir)}
    ctx.check(f"the run log's kinds, got {sorted(kinds)}", {"state", "trigger", "gate", "report"} <= kinds)
    res = json.loads((runner.run_dir / "stages" / "build" / "result.json").read_text(encoding="utf-8"))
    ctx.check(f"result.json, got {sorted(res)}", res["state"] == "done" and res["refs"] == {"orchestra_run": "20260101-000000-abcd"})


@test
def test_redo_runs_again_with_the_text_and_stop_ends(ctx: Ctx):
    from halo_harness.team import stages as ST
    runner, fakes, _root = _runner()
    runner.request("draft")
    runner.tick()
    ST.write_answer(runner.run_dir, "draft", "redo", "shorter, please")
    runner.tick()
    spawns = [c for c in fakes.calls if c[0] == "spawn"]
    ctx.check(f"redo ran draft again with the text, got {len(spawns)}", len(spawns) == 2
              and "THE LEAD ASKED FOR A REDO: shorter, please" in spawns[1][3])
    ctx.check("round 2, gated again", runner.row("draft")["round"] == 2 and runner.row("draft")["state"] == "gated"
              and ST.read_gate(runner.run_dir, "draft")["round"] == 2)
    ST.write_answer(runner.run_dir, "draft", "stop", "not today")
    ctx.check("stop: tick says nothing is live", runner.tick() is False)
    board = runner.board()
    ctx.check(f"the run is stopped, the rest skipped, got {board['state']} {_states(runner)}",
              board["state"] == "stopped" and board["stop_reason"] == "not today"
              and set(_states(runner).values()) == {"skipped"} and ST.read_gate(runner.run_dir, "draft") is None)
    ctx.check("a stopped run takes no stage", runner.request("review") is False)
    runner2, _f, _r = _runner()
    from halo_harness.team.board import request_stop
    request_stop(runner2.run_dir, "from the CLI")
    runner2.tick()
    ctx.check("stop.json stops the run at the next tick", runner2.board()["state"] == "stopped"
              and runner2.board()["stop_reason"] == "from the CLI")


DELEGATED = R.TEAM.replace("members: [writer], reads: [brief], writes: [copy], trigger: manual,\n       gate: required, acceptance: {expect: \"draft\"}",
                           "members: [remote], reads: [brief], writes: [copy], trigger: manual")


@test
def test_a_delegated_member_202_waits_then_runs(ctx: Ctx):
    fakes = R.Fakes(dispatch_status=202)
    runner, fakes, _root = _runner(DELEGATED, fakes)
    runner.request("draft")
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"202: the stage waits on the owner's card, got {row['state']} {row['waiting']!r}",
              row["state"] == "running" and row["waiting"] == "remote: asked; the owner's card is open on kali"
              and runner.status() == "busy" and ("send", "remote", "draft") in fakes.calls)
    runner.tick()
    ctx.check("nothing new: still waiting", runner.row("draft")["state"] == "running")
    fakes.polls.append({"state": "running"})
    runner.tick()
    ctx.check(f"the owner said yes: running on kali, got {runner.row('draft')['waiting']!r}",
              runner.row("draft")["waiting"] == "remote: running on kali")
    fakes.polls.append({"ok": True, "state": "done", "text": "done remotely", "cost_usd": 0.5})
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"the result lands: done, cost, summary, got {row}", row["state"] == "done" and row["cost_usd"] == 0.5
              and row["summary"] == "done remotely" and row["waiting"] == "")
    ctx.check("no local spawn for a delegated member", not any(c[0] == "spawn" and c[1] == "remote" for c in fakes.calls))
    runner2, _f, _r = _runner(DELEGATED, R.Fakes(dispatch_status=403))
    runner2.request("draft")
    runner2.tick()
    row = runner2.row("draft")
    ctx.check(f"403: the stage fails with the reason, got {row['error']!r}",
              row["state"] == "failed" and row["error"] == "remote: kali refused: the owner said no")


@test
def test_a_refused_write_is_logged_and_refused(ctx: Ctx):
    from halo_harness.team.board import read_events
    runner, fakes, root = _runner()
    fakes.writes["writer"] = [("Write", root / "site" / "x.html", {"content": "x"}),
                              ("Write", root / "content" / "a.md", {"content": "# A\n"})]
    runner.request("draft")
    runner.tick()
    dec = next(c for c in fakes.calls if c[0] == "decisions")
    ctx.check(f"the write outside the stage's blocks is refused, the one inside allowed, got {dec}",
              dec[2] == ["deny", "allow"] and "is in block `site`" in dec[3][0])
    ctx.check("the refused file was not written", not (root / "site" / "x.html").exists() and (root / "content" / "a.md").exists())
    refused = [e for e in read_events(runner.run_dir) if e["kind"] == "claim" and e["data"].get("refused")]
    ctx.check(f"one refused claim line, got {len(refused)}", len(refused) == 1 and refused[0]["data"]["member"] == "writer")
    from halo_harness.team.blocks import block_status
    st = block_status(runner.team, "copy")
    ctx.check(f"the stage's claims are released when it ends, got {st['holders']}", st["holders"] == []
              and st["changes_count"] == 1)


@test
def test_failed_acceptance_raising_seams_and_adopt(ctx: Ctx):
    text = R.TEAM.replace('gate: required, acceptance: {expect: "draft"}', 'gate: none, acceptance: {expect: "zzz"}')
    runner, fakes, _root = _runner(text)
    runner.request("draft")
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"a failed acceptance without a gate fails the stage, got {row}", row["state"] == "failed"
              and "acceptance 'zzz'" in row["error"] and _states(runner)["review"] == "pending")

    def boom(*a, **k):
        raise RuntimeError("the seam broke")
    runner.orchestra = boom
    runner.request("build")
    runner.tick()
    ctx.check(f"a seam that raises fails its stage only, got {runner.row('build')['error']!r}",
              runner.row("build")["state"] == "failed" and runner.row("build")["error"] == "RuntimeError: the seam broke")
    from halo_harness.team.board import set_stage
    from halo_harness.team.run import TeamRunner
    set_stage(runner.run_dir, "review", "running")
    set_stage(runner.run_dir, "build", "ready")
    fresh = TeamRunner(runner.team, runner.run_dir, **fakes.seams())
    fresh.adopt()
    ctx.check("adopt: a row left running fails with the reason, a ready row queues again",
              fresh.row("review")["state"] == "failed" and "runner that ran it ended" in fresh.row("review")["error"]
              and fresh.queue == [("build", "")])
    fresh.loop(sleep=lambda s: None, max_ticks=5)
    ctx.check("the loop runs the queued stage", fresh.row("build")["state"] == "done")


@test
def test_loop_until_the_gate_and_the_statuses(ctx: Ctx):
    runner, _fakes, _root = _runner()
    ctx.check("nothing queued: idle", runner.status() == "idle" and not runner.active())
    runner.request("draft")
    ctx.check("queued: busy", runner.status() == "busy")
    board = runner.loop(until="gate", sleep=lambda s: None, max_ticks=10)
    ctx.check("loop(until=gate) returns at the gate, the beat cleared",
              runner.status() == "gated" and board["runner"] is None)
    runner.watching = True
    from halo_harness.team.stages import write_answer
    write_answer(runner.run_dir, "draft", "accept")
    runner.tick()
    ctx.check(f"with watch, an armed block watcher keeps the runner live, got {runner.status()}",
              runner.status() == "watching")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team run tests"))
