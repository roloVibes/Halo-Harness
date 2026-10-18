"""tests.test_team_budget -- Halo 3.1.2.0 round R2: a team's budget line
(halo_harness/team/budget.py; spec/validate read `budget_usd` on the team
and on a stage): over the run's or the stage's budget a stage is not
started (the row says why, budget.json, the Attention row with raise /
skip / stop); a raised budget in the file counts at once; the stage
forecast of an agent, an orchestra and a flow stage; `halo team status`
shows spent / forecast / budget; the file's budgets are validated. Through
tests/helpers/team_rig.py's fakes: no model is called.

Run: python -m tests.test_team_budget
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _team_text(team_budget=None, stage_budget=None) -> str:
    text = R.TEAM
    if team_budget is not None:
        text = text.replace("brief: docs/BRIEF.md\n", f"brief: docs/BRIEF.md\nbudget_usd: {team_budget}\n")
    if stage_budget is not None:
        text = text.replace("trigger: manual,\n       gate: required", f"trigger: manual, budget_usd: {stage_budget},\n       gate: required")
    return text


def _runner(text: str):
    from halo_harness.team import budget as TB
    from halo_harness.team import spec as S
    from halo_harness.team.run import TeamRunner, open_run
    TB.ROWS = []  # no catalog: every member turn counts TURN_USD
    root, state = R.repo(text)
    team = S.load_team(root, state)
    fakes = R.Fakes()
    return TeamRunner(team, open_run(team, cwd=root, state_dir=state), cwd=root, state_dir=state, **fakes.seams()), fakes, root, state


@test
def test_over_the_teams_budget_the_stage_is_held_then_a_raise_runs_it(ctx: Ctx):
    from halo_harness.team import board as BD
    from halo_harness.team.budget import TURN_USD, held
    runner, fakes, root, _state = _runner(_team_text(team_budget=0.05))
    runner.request("draft")
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"not started: pending, the row says why, got {row['state']} {row['waiting']!r}",
              row["state"] == "pending" and row["waiting"].startswith("budget: the run spent $0 and stage draft's forecast is $0.10")
              and "over the team's budget_usd $0.05" in row["waiting"] and not any(c[0] == "spawn" for c in fakes.calls))
    hold = BD.read_stage_file(runner.run_dir, "draft", "budget.json", None)
    ctx.check(f"budget.json and the row's budget carry the numbers, got {hold}",
              hold["scope"] == "run" and hold["forecast"] == TURN_USD and hold["budget"] == 0.05 and hold["spent"] == 0.0
              and row["budget"]["text"] == hold["text"] and held(runner.run_dir)[0]["stage"] == "draft")
    ctx.check(f"the runner is idle, not busy, got {runner.status()}", runner.status() == "idle")
    (root / ".halo" / "team.yaml").write_text(_team_text(team_budget=1.0), encoding="utf-8")
    runner.request("draft")
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"raised in the file: the stage runs at once, got {row['state']} {row.get('budget')}",
              row["state"] == "gated" and row.get("budget") is None and row["waiting"] == ""
              and not (runner.run_dir / "stages" / "draft" / "budget.json").exists())


@test
def test_a_stages_own_budget_counts_its_earlier_rounds(ctx: Ctx):
    from halo_harness.team import stages as TS
    runner, fakes, _root, _state = _runner(_team_text(stage_budget=0.105))
    runner.request("draft")
    runner.tick()
    ctx.check("round 1: $0 spent + $0.10 forecast is within $0.105", runner.row("draft")["state"] == "gated")
    TS.write_answer(runner.run_dir, "draft", "redo", "again")
    runner.tick()
    row = runner.row("draft")
    ctx.check(f"the redo: the stage's $0.01 + $0.10 is over its $0.105, got {row['state']} {row['waiting']!r}",
              row["state"] == "pending" and "stage draft spent $0.01 and its forecast is $0.10: over its budget_usd $0.105"
              in row["waiting"] and row["budget"]["scope"] == "stage")


@test
def test_the_attention_row_skip_and_stop(ctx: Ctx):
    from halo_harness.fleet import team_attention as TA
    from halo_harness.fleet.attention import KEYS
    from halo_harness.studio.api import Request
    from halo_harness.studio.team_budget_api import post_budget
    runner, _fakes, root, state = _runner(_team_text(team_budget=0.01))
    runner.request("draft")
    runner.tick()
    entries = TA.gated(root, state)
    rows = TA.rows(entries, {"id": "h", "name": "here", "local": True}, {}, 1000.0)
    row = next(r for r in rows if r["kind"] == "team_budget")
    ctx.check(f"a team_budget row with raise / skip / stop, got {row['keys']} {row['what']!r}",
              row["keys"] == KEYS["team_budget"] == {"a": "raise (edit the file)", "r": "skip", "s": "stop", "o": "open Team"}
              and row["what"] == "Team launch: stage draft is held at its budget line" and "over the team's" in row["detail"])
    req = Request(method="POST", path="team/budget", query={}, body={"stage": "draft", "action": "raise"}, cwd=root,
                  state_dir=state, server=None, params={})
    status, _body, label = TA.answer(req, row, "a", "")
    ctx.check(f"Raise opens the team file, sends nothing, got {status} {_body}", status == 200
              and _body["open"]["section"] == "team" and _body["open"]["panel"] == "team-file" and label == "raise (edit the file)")
    status, body, _ = TA.answer(req, row, "r", "")
    ctx.check(f"Skip: the stage is skipped, the hold gone, got {status} {body}", status == 200 and body["ok"]
              and runner.row("draft")["state"] == "skipped" and not TA.gated(root, state))
    req.body = {"stage": "draft", "action": "skip"}
    ctx.check("a stage that is not held answers 409", post_budget(req)[0] == 409)
    runner2, _f, root2, state2 = _runner(_team_text(team_budget=0.01))
    runner2.request("draft")
    runner2.tick()
    from halo_harness.studio import team_api
    saved, team_api.RUNNER = team_api.RUNNER, (lambda: R.Fakes().seams())
    try:
        req2 = Request(method="POST", path="team/budget", query={}, body={"stage": "draft", "action": "stop"}, cwd=root2,
                       state_dir=state2, server=None, params={})
        status, body = post_budget(req2)
        runner2.tick()  # the test's runner is the live one (its beat is on the board): it takes stop.json
    finally:
        team_api.RUNNER = saved
    ctx.check(f"Stop: the run stops, got {status} {body} {runner2.board().get('state')}", status == 200
              and runner2.board()["state"] == "stopped" and "budget line" in runner2.board()["stop_reason"])


@test
def test_the_stage_forecasts_and_the_status_line(ctx: Ctx):
    from halo_harness.team import budget as TB
    from halo_harness.team import spec as S
    from halo_harness.team.cli import cmd_team
    runner, _fakes, root, state = _runner(_team_text(team_budget=0.05))
    team = runner.team
    rows = [{"ref": "or:vendor/mid", "provider": "openrouter", "price_in_per_m": 1.0, "price_out_per_m": 4.0}]
    TB.ROWS = rows
    agent = TB.stage_forecast(team, S.stage_by_id(team, "review"), ["editor", "writer"], root=root, state_dir=state)
    ctx.check(f"an agent stage: one turn per member (unpriced here: TURN_USD each), got {agent['usd']}",
              agent["usd"] == 2 * TB.TURN_USD and len(agent["lines"]) == 2 and agent["how"] == "2 member turn(s)")
    orch = TB.stage_forecast(team, S.stage_by_id(team, "build"), [], root=root, state_dir=state)
    ctx.check(f"an orchestra stage: the Orchestra forecast of its goal, got {orch['how']} {len(orch['lines'])}",
              orch["how"] == "the Orchestra forecast of its goal" and len(orch["lines"]) == 2)
    flow = TB.stage_forecast(team, S.stage_by_id(team, "post"), [], root=root, state_dir=state)
    ctx.check(f"a flow stage: its steps' budgets, got {flow['usd']}", flow["how"] == "its flow's step budgets" and flow["usd"] > 0)
    TB.ROWS = []
    runner.request("draft")
    runner.tick()
    out, err = io.StringIO(), io.StringIO()
    cwd = os.getcwd()
    os.chdir(root)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cmd_team(["status"])
            code_j = cmd_team(["status", "--json"])
    finally:
        os.chdir(cwd)
    text = out.getvalue()
    st = json.loads(text[text.index("{"):])
    ctx.check(f"`halo team status` shows spent / forecast / budget and the hold, got {text[:400]!r}",
              code == 0 and code_j == 0 and "spent $0.0000 · forecast $" in text and "budget $0.05" in text
              and "held: draft (the run spent $0" in text)
    ctx.check(f"--json carries the budget block, got {st.get('budget')}", st["budget"]["budget_usd"] == 0.05
              and st["budget"]["holds"][0]["stage"] == "draft" and st["budget"]["forecast"] > 0)


@test
def test_the_file_validates_its_budgets(ctx: Ctx):
    from halo_harness.team import spec as S
    root, state = R.repo(_team_text(team_budget="lots", stage_budget=-1))
    problems = S.validate_team(S.load_team(root, state), cwd=root, state_dir=state, preflight=False)
    ctx.check(f"both budget lines are checked, got {problems}",
              "the team's budget_usd is a number of dollars, 0 or more, got 'lots'" in problems
              and "stage `draft`: budget_usd is a number of dollars, 0 or more, got -1" in problems)
    from halo_harness.team import budget as TB
    TB.ROWS = None


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team budget tests"))
