"""tests.test_studio_flow_api -- Halo 3.0.4.0 round R5: Studio's Flow routes
(`/api/flow/...`) over a temp state dir, FakeComfy and the R3 fakes
(tests/helpers/flow_studio_rig.py): the templates, the run rows and one
run's payload (steps, gate, report, posts, artboards with their
/design-files/ URLs), events since N, POST flow/runs -> 201 with
flow_state / flow_gate / flow_report frames on /api/events and the 409 for
a second run, the answer route (accept resolves the open gate; a closed
gate and a stale round are 422), stop and resume, the assets upload into a
run that has not started (its intake picks the file up), and the report /
posts / metrics routes. The media and sessions routes are in
tests/test_studio_media_sessions.py.

Run: python tests/test_studio_flow_api.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.flow_studio_rig import FlowStudio, Reader, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
INTAKE = {"brief": "a teaser for 3.0.4", "platforms": ["x", "instagram"], "budget_usd": "5"}


@test
def test_templates_runs_and_the_run_payload(ctx: Ctx):
    with FlowStudio() as s:
        status, rows = s.get("flow/templates")
        social = next((r for r in rows if r["name"] == "social-post"), None) if status == 200 else None
        ctx.check(f"templates lists the shipped social-post, got {status} {rows}", social is not None
                  and social["source"] == "template" and social["steps"][0] == {"id": "intake", "kind": "intake"}
                  and social["form"]["brief"] == "text" and "x" in social["form"]["platforms"])
        done = s.finished_run()
        waiting, _t, _box = s.waiting_run()
        status, runs = s.get("flow/runs")
        by = {r["run"]: r for r in runs} if status == 200 else {}
        ctx.check(f"runs lists both, newest first, got {runs}", status == 200 and runs[0]["run"] == waiting.name
                  and by[done.name]["status"] == "finished" and by[done.name]["cost_usd"] > 0)
        ctx.check("the waiting run names its waiting step", by[waiting.name].get("waiting_step") == "approve"
                  and "waiting_step" not in by[done.name])
        status, run = s.get(f"flow/runs/{done.name}")
        ctx.check(f"the run payload has every part, got {status} {sorted(run)}", status == 200 and {
            "flow", "steps", "gate", "report", "posts", "metrics_tail", "artboards", "events", "live"} <= set(run))
        ctx.check("steps are the steps/<n>.json records", [x.get("id") for x in run["steps"]][:3] == ["intake", "plan", "marketing"])
        ctx.check("a finished run has no gate and a report", run["gate"] is None and run["report"]["status"] == "finished")
        ctx.check(f"posts are this run's dry-run posts, got {run['posts']}",
                  [p["platform"] for p in run["posts"]] == ["x", "instagram"] and all(p["run"] == done.name for p in run["posts"]))
        art = run["artboards"][0] if run["artboards"] else {}
        ctx.check(f"the hero artboard with its /design-files/ URL, got {art}", art.get("id") == "hero"
                  and art.get("url") == f"/design-files/{run['project']['slug']}/hero/render.png" and art.get("version") == 1)
        import urllib.request
        with urllib.request.urlopen(s.base + art["url"], timeout=10) as r:
            ctx.check("the artboard URL serves the PNG", r.status == 200 and r.headers["Content-Type"] == "image/png"
                      and r.read()[:4] == b"\x89PNG")
        status, run = s.get(f"flow/runs/{waiting.name}")
        ctx.check(f"the waiting run carries the open gate, got {run.get('gate')}", status == 200 and run["gate"]["step"] == "approve"
                  and run["gate"]["actions"] == ["accept", "redo", "stop"] and run["gate"]["artboards"])
        status, ev = s.get(f"flow/runs/{done.name}/events?since=0")
        n = len(ev["events"])
        status2, ev2 = s.get(f"flow/runs/{done.name}/events?since={n - 2}")
        ctx.check(f"events since N, got {n} then {ev2}", status == 200 and ev["next"] == n and n > 10
                  and len(ev2["events"]) == 2 and ev2["next"] == n and ev2["events"][-1]["kind"] == "report")
        ctx.check("a bad since is a 422", s.get(f"flow/runs/{done.name}/events?since=x")[0] == 422)
        ctx.check("an unknown run is a 404", s.get("flow/runs/nope-0000")[0] == 404)
        status, rep = s.get(f"flow/runs/{done.name}/report")
        ctx.check("report is report.json", status == 200 and rep["run"] == done.name and rep["status"] == "finished")
        ctx.check("a run without a report is a 404 on /report", s.get(f"flow/runs/{waiting.name}/report")[0] == 404)
        status, posts = s.get(f"flow/runs/{done.name}/posts")
        ctx.check("posts route", status == 200 and len(posts["posts"]) == 2)
        status, met = s.get(f"flow/runs/{done.name}/metrics?limit=5")
        ctx.check(f"metrics route (the R3 stub writes none), got {met}", status == 200 and met["metrics"] == [])


@test
def test_answer_route_resolves_the_gate(ctx: Ctx):
    with FlowStudio() as s:
        run_dir, t, box = s.waiting_run()
        status, body = s.post(f"flow/runs/{run_dir.name}/answer", {"step": "approve", "action": "accept", "round": 9})
        ctx.check(f"a stale round is a 422, got {status} {body}", status == 422 and "round" in body["error"])
        status, body = s.post(f"flow/runs/{run_dir.name}/answer", {"step": "publish", "action": "accept"})
        ctx.check(f"a step with no gate is a 422, got {status}", status == 422)
        status, body = s.post(f"flow/runs/{run_dir.name}/answer", {"step": "approve", "action": "maybe"})
        ctx.check(f"an unknown action is a 422, got {status} {body}", status == 422)
        status, body = s.post(f"flow/runs/{run_dir.name}/answer", {"step": "approve", "action": "accept", "round": 1})
        ctx.check(f"accept answers the gate, got {status} {body}", status == 200 and body["ok"] and body["gate"]["step"] == "approve")
        t.join(20)
        ctx.check(f"the runner went on and finished, got {box.get('report', {}).get('status')}",
                  not t.is_alive() and box["report"]["status"] == "finished")
        status, body = s.post(f"flow/runs/{run_dir.name}/answer", {"step": "approve", "action": "accept"})
        ctx.check(f"answering a closed gate is a 422, got {status} {body}", status == 422)


@test
def test_post_run_streams_flow_frames_and_one_run_at_a_time(ctx: Ctx):
    with FlowStudio() as s:
        rd = Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
        try:
            ctx.check("bad bodies are 422 / 404", s.post("flow/runs", {})[0] == 422
                      and s.post("flow/runs", {"template": "no-such-flow"})[0] == 404
                      and s.post("flow/runs", {"template": "../etc"})[0] == 404
                      and s.post("flow/runs", {"template": "social-post", "set": {"render": 3}})[0] == 422)
            status, body = s.post("flow/runs", {"template": "social-post", "intake": INTAKE, "set": {"render.width": 64}})
            ctx.check(f"POST flow/runs is a 201 naming the run, got {status} {body}", status == 201 and body["started"])
            run = body.get("run", "")
            st = rd.wait(lambda k, f: k == "flow_state" and f["session_id"] == f"flow:{run}", 10)
            ctx.check(f"a flow_state frame for flow:<run>, got {st}", st is not None and st["data"]["run"] == run
                      and st["data"]["kind"] == "state")
            gate = rd.wait(lambda k, f: k == "flow_gate" and f["data"].get("data", {}).get("gate"), 20)
            ctx.check(f"a flow_gate frame carries the gate, got {gate and gate['data']['text']}",
                      gate is not None and gate["data"]["data"]["gate"]["step"] == "approve")
            status, body = s.post("flow/runs", {"template": "social-post", "intake": INTAKE})
            ctx.check(f"a second run while one is live is a 409 naming it, got {status} {body}",
                      status == 409 and body.get("run") == run)
            status, rows = s.get("flow/runs")
            ctx.check("the live run is marked live", any(r["run"] == run and r["live"] for r in rows))
            status, body = s.post(f"flow/runs/{run}/answer", {"step": "approve", "action": "accept"})
            ctx.check("Studio answers its own run's gate", status == 200)
            rep = rd.wait(lambda k, f: k == "flow_report" and f["session_id"] == f"flow:{run}", 20)
            ctx.check(f"the flow_report frame arrives, got {rep and rep['data']['text']}", rep is not None
                      and rep["data"]["data"]["status"] == "finished")
            from halo_harness.studio import flow_runs
            ctx.check("the runner thread ends", flow_runs.wait(10) and flow_runs.live_id() is None)
            status, run_body = s.get(f"flow/runs/{run}")
            graph = s.comfy.prompts[-1]["graph"]
            ctx.check("the set override reached the render graph", graph["5"]["inputs"]["width"] == 64)
            ctx.check("the intake budget became the run budget", run_body["flow"]["budget_usd"] == 5.0)
        finally:
            rd.close()


@test
def test_assets_into_a_held_run_then_resume_and_stop(ctx: Ctx):
    with FlowStudio() as s:
        status, body = s.post("flow/runs", {"template": "social-post", "intake": INTAKE, "start": False})
        run = body.get("run", "")
        ctx.check(f"start: false makes the run without starting it, got {status} {body}", status == 201 and not body["started"])
        data = base64.b64encode(b"\x89PNG logo").decode("ascii")
        status, row = s.post(f"flow/runs/{run}/assets", {"name": "../logo.png", "data_base64": data})
        ctx.check(f"the upload lands in the project's assets, got {status} {row}", status == 201
                  and row["name"] == "logo.png" and Path(row["path"]).read_bytes() == b"\x89PNG logo"
                  and Path(row["path"]).parent.name == "assets" and row["intake"] is True)
        big = base64.b64encode(b"\x00" * (5 * 1024 * 1024)).decode("ascii")
        status, row2 = s.post(f"flow/runs/{run}/assets", {"name": "big.bin", "data_base64": big})
        ctx.check(f"a 5 MB asset passes the server's body cap, got {status}", status == 201 and row2["size"] == 5 * 1024 * 1024)
        ctx.check("a bad upload is a 422", s.post(f"flow/runs/{run}/assets", {"name": "x.png", "data_base64": "!!"})[0] == 422)
        status, body = s.post(f"flow/runs/{run}/resume", {"yes": True})
        ctx.check(f"resume starts the held run, got {status} {body}", status == 200 and body["started"])
        from halo_harness.studio import flow_runs
        ctx.check("it finishes with --yes", flow_runs.wait(20))
        status, payload = s.get(f"flow/runs/{run}")
        intake = payload["steps"][0].get("output") or {}
        ctx.check(f"the intake step picked the uploads up, got {intake.get('assets')}",
                  [Path(p).name for p in intake.get("assets") or []] == ["logo.png", "big.bin"])
        ctx.check("the run finished", payload["flow"]["status"] == "finished")
        status, body = s.post(f"flow/runs/{run}/resume", {})
        ctx.check(f"resuming a finished run is a 409, got {status}", status == 409)
        run_dir, t, box = s.waiting_run()
        status, body = s.post(f"flow/runs/{run_dir.name}/stop", {"reason": "enough"})
        ctx.check(f"stop writes stop.json, got {status} {body}", status == 200 and body["ok"])
        t.join(20)
        ctx.check("the gate answered stop and the run stopped", box["report"]["status"] == "stopped"
                  and "enough" in str(box["report"]["stop_reason"]))
        ctx.check("wait_for helper sanity", wait_for(lambda: True, 0.1))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio flow api tests"))
