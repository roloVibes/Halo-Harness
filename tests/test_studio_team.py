"""tests.test_studio_team -- Halo 3.0.8.0 round R1: Studio's Team routes
(`/api/team/...`, studio/team_api.py + team_live.py) through
tests/test_studio_api.py's `_Studio` rig (an in-process server over a scoped
home; the repo is built in the Studio's own folder): the team payload,
validate (the file and a YAML text), the board before and during a run, the
blocks and their changes, the events; `POST team/run` through the `RUNNER`
seam with the fakes: 202, the `team` frames on `/api/events` (stage, gate,
claim, change), answer accept driving the next stages, stop; 422 on a
problem, on an unknown stage and on the preflight (`force` runs); 404 with
no team file. No model is ever called.

Run: python -m tests.test_studio_team
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.orchestra_studio_rig import Reader  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_api import _Studio  # noqa: E402

test, TESTS = new_registry()


def _until(pred, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


@test
def test_read_routes(ctx: Ctx):
    with _Studio() as s:
        status, data, _ = s.call("GET", "/api/team")
        ctx.check(f"no team file: found false, got {data}", status == 200 and data["found"] is False and data["team"] is None)
        ctx.check("the other routes are a 404 naming init", s.call("GET", "/api/team/board")[0] == 404
                  and "halo team init" in s.call("GET", "/api/team/blocks")[1]["error"])
        root, _state = R.repo(at=s.state.parent / "proj")
        status, data, _ = s.call("GET", "/api/team")
        ctx.check(f"the team payload's keys, got {sorted(data)}", status == 200 and set(data) == {
            "found", "path", "source", "root", "team", "problems", "preflight", "run", "live"})
        ctx.check("found in the repo, valid, no run yet", data["found"] and data["source"] == "repo" and data["problems"] == []
                  and data["run"] is None and data["live"] is False and data["team"]["name"] == "launch")
        status, v, _ = s.call("POST", "/api/team/validate", {})
        ctx.check(f"validate the file, got {v['problems']}", status == 200 and v["ok"] is True and v["team"]["blocks"])
        bad = R.TEAM.replace("writes: [site]", "writes: [nowhere]")
        status, v, _ = s.call("POST", "/api/team/validate", {"yaml": bad})
        ctx.check(f"validate a YAML text, got {v['problems']}", status == 200 and v["ok"] is False
                  and any("writes `nowhere`" in p for p in v["problems"]))
        status, v, _ = s.call("POST", "/api/team/validate", {"yaml": "name: ["})
        ctx.check("broken YAML is a problem line", status == 200 and v["ok"] is False and "not valid YAML" in v["problems"][0])
        status, b, _ = s.call("GET", "/api/team/board")
        ctx.check(f"no run: the stages, all pending, got {b['board']['state']}", status == 200 and b["run"] is None
                  and [r["state"] for r in b["board"]["stages"]] == ["pending"] * 3 and b["board"]["stages"][2]["kind"] == "orchestra")
        ctx.check("an unknown run is a 404", s.call("GET", "/api/team/board?run=19990101")[0] == 404)
        status, bl, _ = s.call("GET", "/api/team/blocks")
        ctx.check("every block's status", status == 200 and [x["id"] for x in bl["blocks"]] == ["copy", "site", "notes"])
        status, ch, _ = s.call("GET", "/api/team/blocks/copy/changes?since=0")
        ctx.check("no changes yet", status == 200 and ch == {"block": "copy", "changes": [], "next": 0})
        ctx.check("an unknown block is a 404", s.call("GET", "/api/team/blocks/nope/changes")[0] == 404)
        ctx.check("a bad since is a 422", s.call("GET", "/api/team/events?since=x")[0] == 422)
        ctx.check("no run: no events", s.call("GET", "/api/team/events")[1] == {"run": None, "events": [], "next": 0})
        ctx.check("a wrong method is a 405", s.call("GET", "/api/team/run")[0] == 405)
        ctx.check("no token, no answer", s.call("GET", "/api/team", token="")[0] == 401)
        ctx.check("the repo is the Studio's folder", Path(data["root"]) == root)


@test
def test_run_frames_answer_and_stop(ctx: Ctx):
    from halo_harness.studio import team_api, team_live
    fakes = R.Fakes()
    saved = team_api.RUNNER
    team_api.RUNNER = fakes.seams
    try:
        with _Studio() as s:
            root, _state = R.repo(at=s.state.parent / "proj")
            fakes.writes["writer"] = [("Edit", root / "content" / "intro.md", {"old_string": "more", "new_string": "M"})]
            ctx.check("an unknown stage is a 422", s.call("POST", "/api/team/run", {"stage": "nope"})[0] == 422)
            rd = Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
            try:
                status, out, _ = s.call("POST", "/api/team/run", {"stage": "draft"})
                ctx.check(f"202 with the run and the stage, got {status} {out}", status == 202 and out["stage"] == "draft"
                          and out["started"] is True and out["run"])
                frames = []

                def seen(action, stage=None):
                    f = rd.wait(lambda k, fr: k == "team" and frames.append(fr) is None and fr["data"]["action"] == action
                                and (stage is None or fr["data"]["stage"] == stage), 8.0)
                    return f
                gate = seen("gate", "draft")
                ctx.check(f"a team gate frame arrives, got {gate and gate['data']['text']}", gate is not None
                          and gate["session_id"] == f"team:{out['run']}" and gate["event"] == "team")
                actions = {f["data"]["action"] for f in frames}
                ctx.check(f"stage, claim and change frames came first, got {sorted(actions)}",
                          {"stage", "claim", "change", "gate"} <= actions)
                row = next(f["data"]["row"] for f in frames if f["data"]["action"] == "stage" and f["data"].get("row"))
                ctx.check("a stage frame carries the board row", row["id"] == "draft" and "state" in row)
                status, b, _ = s.call("GET", "/api/team/board")
                ctx.check(f"the board shows the gate, live, got {b['board']['stages'][0]['state']}", status == 200
                          and b["board"]["stages"][0]["state"] == "gated" and b["live"] is True and b["status"]["waiting"] == ["draft"])
                status, ch, _ = s.call("GET", "/api/team/blocks/copy/changes")
                ctx.check(f"the change line is served, got {ch}", status == 200 and ch["changes"][0]["member"] == "writer")
                status, ev, _ = s.call("GET", "/api/team/events?since=0")
                ctx.check("events since 0", status == 200 and ev["next"] == len(ev["events"]) > 3 and ev["run"] == out["run"])
                ctx.check("a bad answer is a 422", s.call("POST", "/api/team/answer", {"stage": "draft", "action": "maybe"})[0] == 422)
                status, a, _ = s.call("POST", "/api/team/answer", {"stage": "draft", "action": "accept"})
                ctx.check(f"answer accept, got {a}", status == 200 and a["ok"] and a["driven"] is False)
                ctx.check("review runs after the accept", _until(lambda: [r["state"] for r in s.call(
                    "GET", "/api/team/board")[1]["board"]["stages"]] == ["done", "done", "pending"]))
                ctx.check("a second run without a stage while live is a 409", s.call("POST", "/api/team/run", {})[0] == 409)
                status, st, _ = s.call("POST", "/api/team/stop", {"reason": "enough"})
                ctx.check("stop", status == 200 and st["ok"])
                ctx.check("the runner ends", team_live.wait(root, 8.0))
                ctx.check("the board is stopped", s.call("GET", "/api/team/board")[1]["board"]["state"] == "stopped")
                ctx.check("stop again is a 409", s.call("POST", "/api/team/stop", {})[0] == 409)
            finally:
                rd.close()
    finally:
        team_api.RUNNER = saved


@test
def test_run_refuses_on_a_problem_and_on_the_preflight(ctx: Ctx):
    import yaml
    from halo_harness.studio import team_api, team_live
    fakes = R.Fakes()
    saved = team_api.RUNNER
    team_api.RUNNER = fakes.seams
    try:
        with _Studio() as s:
            root, _state = R.repo(R.TEAM.replace("writes: [site]", "writes: [nowhere]"), at=s.state.parent / "proj")
            status, out, _ = s.call("POST", "/api/team/run", {"stage": "draft"})
            ctx.check(f"a problem in the file is a 422 with the lines, got {out}", status == 422
                      and any("writes `nowhere`" in p for p in out["problems"]))
            teams = s.state / "teams"
            teams.mkdir(parents=True, exist_ok=True)
            (teams / "broken.yaml").write_text(yaml.safe_dump({"name": "broken", "agents": [
                {"agent": "ghost-bio", "role": "main"}]}), encoding="utf-8")
            (root / ".halo" / "team.yaml").write_text(R.TEAM.replace("{name: writer, lineup: standard, role: main}",
                                                                     "{name: writer, lineup: broken, role: main}"),
                                                      encoding="utf-8")
            status, out, _ = s.call("POST", "/api/team/run", {"stage": "draft"})
            ctx.check(f"the preflight blocks: 422 with preflight true, got {status} {out.get('error', '')[:80]!r}",
                      status == 422 and out["preflight"] is True and any(p["id"].startswith("writer/missing-bio") for p in out["problems"]))
            status, data, _ = s.call("GET", "/api/team")
            ctx.check("GET team lists the same findings", any(p["id"].startswith("writer/") for p in data["preflight"]))
            status, out, _ = s.call("POST", "/api/team/run", {"stage": "draft", "force": True})
            ctx.check("force runs anyway", status == 202 and out["started"])
            ctx.check("the gate opens", _until(lambda: s.call("GET", "/api/team/board")[1]["board"]["stages"][0]["state"] == "gated"))
            s.call("POST", "/api/team/stop", {})
            ctx.check("stopped", team_live.wait(root, 8.0))
    finally:
        team_api.RUNNER = saved


@test
def test_init_route_and_the_team_gate_attention_row(ctx: Ctx):
    """3.0.8.0 R2: `POST team/init` writes the template and a brief through `halo team init`'s code (409 once
    a file exists); a stage at its gate is a `team_gate` row of the Fleet attention queue: `o` points at the
    Team section on that stage, `r` needs a text, `a` accepts through `POST team/answer`."""
    from halo_harness.studio import team_api, team_live
    from halo_harness.team.spec import template_text
    fakes = R.Fakes()
    saved = team_api.RUNNER
    team_api.RUNNER = fakes.seams
    try:
        with _Studio() as s:
            proj = s.state.parent / "proj"
            proj.mkdir(parents=True, exist_ok=True)
            status, out, _ = s.call("POST", "/api/team/init", {})
            ctx.check(f"init writes the file and the brief, got {status} {out}", status == 200 and out["ok"]
                      and (proj / ".halo" / "team.yaml").read_text(encoding="utf-8") == template_text()
                      and (proj / "docs" / "BRIEF.md").is_file() and len(out["written"]) == 2)
            ctx.check("GET team finds it", s.call("GET", "/api/team")[1]["found"] is True)
            status, out, _ = s.call("POST", "/api/team/init", {})
            ctx.check(f"a second init is a 409 naming the file, got {status} {out}", status == 409 and "team.yaml" in out["path"])
        with _Studio() as s:
            root, _state = R.repo(at=s.state.parent / "proj")
            ctx.check("no gate, no team row", not [r for r in s.call("GET", "/api/fleet/attention")[1]["rows"] if r["kind"] == "team_gate"])
            s.call("POST", "/api/team/run", {"stage": "draft"})
            ctx.check("draft gated", _until(lambda: s.call("GET", "/api/team/board")[1]["board"]["stages"][0]["state"] == "gated"))
            rows = []
            ctx.check("the team_gate row lands", _until(lambda: rows.extend(r for r in s.call("GET", "/api/fleet/attention")[1]["rows"]
                                                                            if r["kind"] == "team_gate") or bool(rows)))
            row = rows[0] if rows else {"id": "", "keys": {}, "what": "", "target": {}}
            ctx.check(f"its what, keys and target, got {row}", "stage draft waits at its gate" in row["what"]
                      and row["keys"] == {"a": "accept", "r": "redo", "s": "stop", "o": "open Team"} and row["text_for"] == "r"
                      and row["target"]["stage"] == "draft")
            status, got, _ = s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "o"})
            ctx.check(f"o opens the Team section on draft, got {got}", status == 200
                      and got["open"] == {"section": "team", "panel": "team-inspector", "run": row["target"]["run"], "stage": "draft"})
            ctx.check("r without a text answers 422 (redo takes the instruction)", s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "r"})[0] == 422)
            status, got, _ = s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "a"})
            ctx.check(f"a accepts the gate, got {status} {got}", status == 200)
            ctx.check("review runs after it", _until(lambda: [r["state"] for r in s.call(
                "GET", "/api/team/board")[1]["board"]["stages"]] == ["done", "done", "pending"]))
            s.call("POST", "/api/team/stop", {})
            ctx.check("the runner ends", team_live.wait(root, 8.0))
    finally:
        team_api.RUNNER = saved



@test
def test_the_coach_route(ctx: Ctx):
    """3.0.9.0 R3: GET team/coach?run= -> the coach's card for a team run (the latest when run is empty);
    404 when the repo has no team run."""
    from tests.helpers.coach_seed import team_run
    with _Studio() as s:
        ctx.check("no team run yet: 404", s.call("GET", "/api/team/coach")[0] == 404)
        run_dir = team_run(s.state.parent / "proj")
        for path in ("/api/team/coach", f"/api/team/coach?run={run_dir.name}"):
            status, data, _ = s.call("GET", path)
            ids = [x["id"] for x in data.get("suggestions") or []]
            ctx.check(f"{path}: the team's cards, got {status} {ids}", status == 200 and data["kind"] == "team"
                      and data["run"] == run_dir.name and "coordination-copy-loops" in ids)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio team tests"))
