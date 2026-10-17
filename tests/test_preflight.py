"""tests.test_preflight -- Halo 3.0.7.0 round R1: the run-start preflight
(lineup_preflight.lineup_problems / flow_problems): each finding over a
scratch lineup and a seeded catalog (dead model id, dead fallback, missing
bio, empty tools.allow, a tier problem), no false dead id from an unread
catalog, and the four entry points refusing with every blocking problem and
its fix -- `halo orchestra run`, `POST /api/orchestra/run`, `halo flow run`,
`POST /api/flow/runs`, a mission `run` -- while `--force` / `{"force": true}`
goes past it (through the seams: orchestra_api.RUNNER, flow_api, the flow
CLI's drive, mission_api). `halo doctor --roles` lists the same findings.
No model is called.

Run: python -m tests.test_preflight
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.preflight_seed import Home  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GOAL = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
        "workers": 5, "files": ["basket.py"]}


def _req(method, path, body, cwd, state_dir):
    from halo_harness.studio.api import Request
    return Request(method=method, path=path, query={}, body=body, cwd=Path(cwd), state_dir=Path(state_dir))


@test
def test_each_finding_with_its_severity_and_fix(ctx: Ctx):
    from halo_harness.lineup_preflight import blocking, lineup_problems
    from halo_harness.preflight import lineup_problems as also
    with Home() as h:
        found = {p["id"]: p for p in lineup_problems("pf-bad", cwd=h.cwd, state_dir=h.state_dir)}
        ctx.check(f"every finding is there, got {sorted(found)}", set(found) == {
            "missing-bio:ghost", "dead-model:worker", "dead-fallback:helper", "empty-tools:notools-bio", "tiers:0",
            "tiers:unplaced"})
        ctx.check("each has the four keys", all(set(p) == {"id", "severity", "text", "fix"} for p in found.values()))
        ctx.check("the dead fallback and the unplaced aliases warn, the rest block",
                  found["dead-fallback:helper"]["severity"] == found["tiers:unplaced"]["severity"] == "warns"
                  and {p["id"] for p in blocking(list(found.values()))}
                  == set(found) - {"dead-fallback:helper", "tiers:unplaced"})
        ctx.check(f"the unplaced line names them, got {found['tiers:unplaced']['text']!r}",
                  found["tiers:unplaced"]["text"].startswith("tiers: 'main', 'tester', 'ghost', 'helper' in no tier"))
        dead = found["dead-model:worker"]
        ctx.check(f"the dead id names alias, bio, ref and catalog, got {dead['text']!r}",
                  dead["text"].startswith("`worker` (bio `dead-bio`) names model `or:vendor/gone`, which is not in the or "
                                          "catalog") and "halo agents edit dead-bio" in dead["fix"])
        ctx.check("the missing bio names it", found["missing-bio:ghost"]["text"] == "`ghost` names bio `ghost-bio`, which does not exist")
        ctx.check("the empty allow-list names its users", "used by `tester`" in found["empty-tools:notools-bio"]["text"]
                  and "tools.allow: []" in found["empty-tools:notools-bio"]["text"])
        ctx.check("the tier problem is the validator's own line", "must hold the main agent 'main' alone" in found["tiers:0"]["text"])
        ctx.check("the clean lineup has only the fallback warning",
                  [p["id"] for p in lineup_problems("pf-good", cwd=h.cwd, state_dir=h.state_dir)] == ["dead-fallback:helper"])
        ctx.check("halo_harness.preflight re-exports it", also is lineup_problems)
        ctx.check("an unknown lineup blocks", [p["id"] for p in lineup_problems("nope", cwd=h.cwd, state_dir=h.state_dir)]
                  == ["lineup-missing"])
        ctx.check("no lineup and no active team is no finding", lineup_problems(None, cwd=h.cwd, state_dir=h.state_dir) == [])
        h.use_team("pf-good")
        ctx.check("an empty name reads the active team", [p["id"] for p in lineup_problems("", cwd=h.cwd, state_dir=h.state_dir)]
                  == ["dead-fallback:helper"])
    with Home(catalog=False) as h:
        ids = [p["id"] for p in lineup_problems("pf-bad", cwd=h.cwd, state_dir=h.state_dir)]
        ctx.check(f"an unreadable catalog gives no dead-id finding, got {ids}", not any(i.startswith("dead-") for i in ids))


@test
def test_orchestra_cli_refuses_and_force_runs(ctx: Ctx):
    from halo_harness import orchestra_cli_run as CR
    from halo_harness.orchestra import adapters, report, run as run_mod
    from halo_harness.orchestra.goal import Goal, new_run
    from tests.helpers import orchestra_fixtures as F
    with Home() as h:
        repo = F.make_repo("pf-orch-")
        new_run(repo, Goal(**{**GOAL, "lineup": "pf-bad"}))
        args = argparse.Namespace(run=None, model=None, dry_run=False, force=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = CR.cmd_run(args, repo)
        text = err.getvalue()
        ctx.check(f"exit 2 with every blocking problem and its fix, got {rc} {text[:300]!r}",
                  rc == 2 and text.startswith("preflight: 4 problem(s) stop run ") and text.count("    fix: ") == 4
                  and "`ghost` names bio `ghost-bio`" in text and "run anyway with --force" in text)
        saved = (run_mod.run, adapters.real_adapters, report.format_report)
        seen = []
        run_mod.run = lambda run_dir, **kw: seen.append(run_dir) or {"status": "finished"}
        adapters.real_adapters = lambda run_dir, goal, model: {}
        report.format_report = lambda rep: "REPORT"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = CR.cmd_run(argparse.Namespace(run=None, model=None, dry_run=False, force=True), repo)
        finally:
            run_mod.run, adapters.real_adapters, report.format_report = saved
        ctx.check(f"--force runs anyway, got {rc}", rc == 0 and len(seen) == 1)
        F_cleanup(repo)


def F_cleanup(repo):
    from tests.helpers import orchestra_studio_rig as R
    R.cleanup(repo)


@test
def test_orchestra_api_refuses_422_and_force_starts(ctx: Ctx):
    from halo_harness.studio import orchestra_api, orchestra_live
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers import orchestra_studio_rig as R
    with Home() as h:
        repo = F.make_repo("pf-orch-api-")
        saved = orchestra_api.RUNNER
        orchestra_api.RUNNER = R.fake_runner()
        try:
            st, body = orchestra_api.post_run(_req("POST", "orchestra/run", {**GOAL, "lineup": "pf-bad"}, repo, h.state_dir))
            ctx.check(f"422 with the preflight body, got {st} {str(body)[:200]}", st == 422 and body.get("preflight") is True
                      and {p["id"] for p in body["problems"]} >= {"dead-model:worker", "missing-bio:ghost"}
                      and body["error"].startswith("preflight: 4 problem(s)") and '{"force": true}' in body["error"])
            ctx.check("no run folder was made", not (repo / ".halo").exists() or not any((repo / ".halo").rglob("goal.json")))
            st, body = orchestra_api.post_run(_req("POST", "orchestra/run", {**GOAL, "lineup": "pf-bad", "force": True},
                                                   repo, h.state_dir))
            ctx.check(f"force: true starts the run, got {st} {body}", st == 201 and body.get("run_id"))
            ctx.check("the run ends", orchestra_live.wait(60))
            st, _b = orchestra_api.post_run(_req("POST", "orchestra/run", {**GOAL, "lineup": "pf-good"}, repo, h.state_dir))
            ctx.check(f"a clean lineup (a warning only) starts without force, got {st}", st == 201)
            orchestra_live.wait(60)
        finally:
            orchestra_live.wait(30)
            orchestra_api.RUNNER = saved
            R.cleanup(repo)


@test
def test_flow_cli_and_api_refuse_and_force_passes(ctx: Ctx):
    from halo_harness.flows import cli_run
    from halo_harness.studio import flow_api
    with Home() as h:
        h.flow("pf-bad")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = cli_run.cmd_run(["pf-flow", "--brief", "x"])
        ctx.check(f"halo flow run exits 2 with the refusal, got {rc} {err.getvalue()[-300:]!r}",
                  rc == 2 and "preflight: 4 problem(s) stop flow pf-flow" in err.getvalue()
                  and "lineup `pf-bad`: `ghost` names bio" in err.getvalue())
        saved, driven = cli_run.drive, []
        cli_run.drive = lambda run_dir, a: driven.append(run_dir) or 0
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                rc = cli_run.cmd_run(["pf-flow", "--brief", "x", "--force"])
        finally:
            cli_run.drive = saved
        ctx.check(f"--force makes the run and drives it, got {rc}", rc == 0 and len(driven) == 1)
        st, body = flow_api.post_run(_req("POST", "flow/runs", {"template": "pf-flow", "intake": {"brief": "x"},
                                                                 "start": False}, h.cwd, h.state_dir))
        ctx.check(f"POST flow/runs is a 422 with the preflight body, got {st} {str(body)[:200]}",
                  st == 422 and body.get("preflight") is True and any(p["id"] == "pf-bad/dead-model:worker" for p in body["problems"]))
        st, body = flow_api.post_run(_req("POST", "flow/runs", {"template": "pf-flow", "intake": {"brief": "x"},
                                                                 "start": False, "force": True}, h.cwd, h.state_dir))
        ctx.check(f"force: true makes the run, got {st} {body}", st == 201 and body.get("run") and body.get("started") is False)


@test
def test_mission_run_refuses_and_force_passes(ctx: Ctx):
    from halo_harness.fleet import mission as M, mission_api as A, mission_store as S
    with Home() as h:
        h.use_team("pf-bad")
        doc = M.new_doc(mid=M.new_id(), goal="a goal", hub={"id": "x", "name": "x"})
        S.create(h.state_dir, doc)
        ctx_ = A.Ctx(h.state_dir, None, publish=lambda f: None, by="t", cwd=h.cwd)
        st, body = A.run(ctx_, doc["id"])
        ctx.check(f"a mission run is a 422 with the preflight body, got {st} {str(body)[:200]}",
                  st == 422 and body.get("preflight") is True and body["error"].startswith("preflight: 4 problem(s) stop mission"))
        st, body = A.run(ctx_, doc["id"], force=True)
        ctx.check(f"force goes past it to the mission's own state check, got {st} {body.get('error')}",
                  st == 409 and "only an approved mission runs" in body["error"])
        st, body = A.admin(h.state_dir, None, {"op": "run", "id": doc["id"], "force": True, "by": "t", "cwd": str(h.cwd)})
        ctx.check(f"the local/mission route carries force, got {st}", st == 409)
        st, _b = A.admin(h.state_dir, None, {"op": "run", "id": doc["id"], "by": "t", "cwd": str(h.cwd)})
        ctx.check(f"and refuses without it, got {st}", st == 422)


@test
def test_doctor_roles_lists_the_same_findings(ctx: Ctx):
    from halo_harness.doctor import cmd_doctor
    with Home() as h:
        h.use_team("pf-bad")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_doctor(["--roles", "--json"])
        data = json.loads(out.getvalue()[out.getvalue().index("{"):])
        ctx.check(f"doctor --roles carries the preflight list, got {rc} {sorted(p['id'] for p in data.get('preflight', []))}",
                  rc == 1 and data["lineup"] == "pf-bad" and {p["id"] for p in data["preflight"]} >= {"dead-model:worker", "tiers:0"}
                  and any("lineup pf-bad: `worker` (bio `dead-bio`)" in p for p in data["problems"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="run-start preflight tests"))
