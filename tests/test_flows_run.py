"""tests.test_flows_run -- the flow runner (Halo 3.0.4.0 round R3) end to end
over tests/helpers/fake_comfy.py and the fake adapters in
tests/helpers/fake_flow.py: the whole social-post template with --yes
(intake copies assets, roles per role, the org's prompt into the render,
an image artboard with source.json in a scoped design project, the confirm,
dry-run posts.json, the metrics stub, events and report.json), the lineup's
models, a confirm answered by file (redo then accept, stop, the redo cap).
The org gate, budgets, resume and stop.json are in test_flows_run2.py.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_flow import Answers, FakeOneShot, FakeOrg, make_adapters, new_run, template_spec  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _project(slug: str):
    from halo_harness.design.store import Project
    return Project.open(slug)


@test
def test_full_social_post_run_with_yes(ctx: Ctx):
    from halo_harness import events as feed
    from halo_harness.flows.run import run
    from halo_harness.flows.state import read_events, read_flow, read_step
    asset = Path(tempfile.mkdtemp(prefix="flow-asset-")) / "logo.png"
    asset.write_bytes(b"\x89PNG fake")
    fed = []
    with FakeComfy() as fake:
        shot, org = FakeOneShot(), FakeOrg()
        ad = make_adapters(fake.url, one_shot=shot, run_org=org, auto_accept=True, feed=fed.append)
        run_dir = new_run(template_spec(), project="flow-full", assets=[str(asset)])
        seen = []
        report = run(run_dir, adapters=ad, on_event=seen.append)
        ctx.check(f"the run finished, got {report.get('status')} {report.get('stop_reason')}", report["status"] == "finished")
        proj = _project(read_flow(run_dir)["project"])
        ctx.check("the design project exists with posts.json and metrics.jsonl",
                  proj is not None and (proj.path / "posts.json").is_file() and (proj.path / "metrics.jsonl").is_file())
        ctx.check("intake copied the dropped file into the project's assets", (proj.path / "assets" / "logo.png").is_file())
        intake = read_step(run_dir, 1)["output"]
        ctx.check(f"intake output is the form, platforms from the choices, got {intake}",
                  intake["platforms"] == ["x", "instagram"] and intake["brief"].startswith("a one-line teaser")
                  and intake["assets"] == [str(proj.path / "assets" / "logo.png")] and intake["project"].startswith("flow-full-"))
        ctx.check(f"one call per role in order, got {[c['role'] for c in shot.calls]}",
                  [c["role"] for c in shot.calls] == ["planner", "researcher"])
        ctx.check("the standard lineup's roles use the session default (no model)", all(c["model"] is None for c in shot.calls))
        ctx.check("the researcher sees the planner's answer", "The planner answered" in shot.calls[1]["prompt"])
        plan = read_step(run_dir, 2)["output"]
        ctx.check("roles output has text, per_role and cost", set(plan["per_role"]) == {"planner", "researcher"}
                  and abs(plan["cost_usd"] - 0.02) < 1e-9 and "## planner" in plan["text"])
        ctx.check(f"the org got the plan as its goal with the platforms, budget min(3.00, remaining), got {org.calls}",
                  org.calls[0]["org"] == "marketing" and "## planner" in org.calls[0]["goal"]
                  and "platforms: x, instagram" in org.calls[0]["goal"] and abs(org.calls[0]["budget_usd"] - 3.0) < 1e-9)
        mk = read_step(run_dir, 3)["output"]
        ctx.check(f"the Art Director's final text becomes its prompt, got {mk['positions']['Art Director']}",
                  mk["positions"]["Art Director"]["prompt"] == "a lighthouse at dusk, cinematic")
        graph = fake.prompts[-1]["graph"]
        ctx.check("the prompt reached the starter's prompt input", graph["4"]["inputs"]["prompt"] == "a lighthouse at dusk, cinematic")
        ctx.check("width/height set, the seed randomised", graph["5"]["inputs"]["width"] == 1080
                  and graph["5"]["inputs"]["height"] == 1350 and isinstance(graph["6"]["inputs"]["seed"], int))
        rend = read_step(run_dir, 4)["output"]
        art = rend["artboards"][0]
        src = json.loads((proj.artboard_dir(art["id"]) / "source.json").read_text(encoding="utf-8"))
        ctx.check(f"an image artboard 'hero' with render.png, got {art}", art["id"] == "hero" and art["kind"] == "image"
                  and Path(art["path"]).name == "render.png" and Path(art["path"]).read_bytes()[:4] == b"\x89PNG")
        ctx.check(f"source.json says comfyui, the workflow, the prompt id and the set, got {src}",
                  src["app"] == "comfyui" and src["workflow"] == "text-to-image-qwen" and src["prompt_id"] == art["prompt_id"]
                  and src["set"]["width"] == 1080 and src["set"]["seed"] == graph["6"]["inputs"]["seed"])
        meta = proj.meta()
        ctx.check("design.json lists the artboard as an image from comfyui",
                  any(a["id"] == "hero" and a["kind"] == "image" and a["app"] == "comfyui" for a in meta["artboards"]))
        ctx.check("the render was snapshotted as v1", (proj.artboard_dir("hero") / "v1" / "render.png").is_file())
        ctx.check("confirm auto-accepted the paths", read_step(run_dir, 5)["output"]["accepted"] == [art["path"]])
        posts = json.loads((proj.path / "posts.json").read_text(encoding="utf-8"))
        ctx.check(f"posts.json has one dry-run entry per platform, got {[p['platform'] for p in posts]}",
                  [p["platform"] for p in posts] == ["x", "instagram"] and all(p["dry_run"] for p in posts))
        ctx.check(f"each post has its platform's copy and the postiz argv, got {posts[0]}",
                  posts[0]["text"] == "Short post for X #halo" and posts[0]["argv"][:3] == ["postiz", "posts:create", "-c"]
                  and posts[0]["media"] == [art["path"]] and "-m" in posts[0]["argv"])
        ev = read_events(run_dir)
        kinds = [e["kind"] for e in ev]
        ctx.check("post, metric, gate and report lines were logged", {"post", "metric", "gate", "report"} <= set(kinds))
        ctx.check("the report line is last", kinds[-1] == "report")
        el = [e["elapsed_s"] for e in ev]
        ctx.check("elapsed_s never goes backwards", el == sorted(el))
        ctx.check("on_event saw every line, in order", [e["ts"] for e in seen] == [e["ts"] for e in ev])
        order = [e["step"] for e in ev if e["kind"] == "state" and e["data"].get("state") == "done"]
        ctx.check(f"steps finished in flow order, got {order}",
                  order == ["intake", "plan", "marketing", "render", "approve", "publish", "measure", "done"])
        ctx.check("the feed got flow_* events (registered kinds), no note", fed and all(isinstance(e, feed.Event)
                  and e.kind.startswith("flow_") for e in fed) and not any(e.kind == "flow_note" for e in fed))
        rep = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        ctx.check("report.json has the documented keys", {"run", "name", "project", "project_path", "status", "stop_reason",
                  "cost_usd", "budget_usd", "steps", "artboards", "accepted", "posts", "metrics"} <= set(rep))
        ctx.check(f"cost per step adds up to the run cost, got {rep['cost_usd']}", abs(rep["cost_usd"] - 0.07) < 1e-9
                  and abs(sum(s["cost_usd"] for s in rep["steps"]) - rep["cost_usd"]) < 1e-9)
        ctx.check("flow.json is finished with every step done", read_flow(run_dir)["status"] == "finished"
                  and all(s["state"] == "done" for s in read_flow(run_dir)["steps"]))
        again = run(run_dir, adapters=ad)
        ctx.check("running a finished run again returns its report, no new calls", again["run"] == report["run"]
                  and len(shot.calls) == 2 and len(fake.prompts) == 1)


@test
def test_roles_use_the_lineups_models(ctx: Ctx):
    from halo_harness.flows.run import run
    from halo_harness.teams_yaml import user_teams_dir
    d = user_teams_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "flowtest.yaml").write_text("name: flowtest\nroles:\n  planner: researcher\n  researcher: researcher\n",
                                     encoding="utf-8")
    spec = template_spec(steps=[s for s in template_spec()["steps"] if s["id"] in ("intake", "plan", "done")])
    spec["steps"][1]["uses"] = "lineup:flowtest"
    with FakeComfy() as fake:
        shot = FakeOneShot()
        report = run(new_run(spec, project="flow-lineup"), adapters=make_adapters(fake.url, one_shot=shot))
        ctx.check("finished", report["status"] == "finished")
        ctx.check(f"each role used the lineup's model, got {[c['model'] for c in shot.calls]}",
                  [c["model"] for c in shot.calls] == ["or:anthropic/claude-sonnet-5"] * 2)
        shot2 = FakeOneShot()
        run(new_run(spec, project="flow-lineup"), adapters=make_adapters(fake.url, one_shot=shot2, model="or:x/y"))
        ctx.check("--model pins every role", [c["model"] for c in shot2.calls] == ["or:x/y"] * 2)


def _gated(fake, script: dict, slug: str):
    from halo_harness.flows.run import run
    answers = Answers(script)
    run_dir = new_run(template_spec(), project=slug)
    report = run(run_dir, adapters=make_adapters(fake.url, run_org=FakeOrg(gate=False), answers=answers))
    return run_dir, report, answers


@test
def test_confirm_redo_then_accept(ctx: Ctx):
    from halo_harness.flows.state import read_step
    with FakeComfy() as fake:
        run_dir, report, answers = _gated(fake, {"approve": [("redo", "warmer colours"), ("accept", "")]}, "flow-redo")
        ctx.check(f"finished after the redo, got {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check("two renders were queued", len(fake.prompts) == 2)
        ctx.check(f"the second prompt carries the instruction, got {fake.prompts[-1]['graph']['4']['inputs']['prompt']}",
                  fake.prompts[-1]["graph"]["4"]["inputs"]["prompt"] == "a lighthouse at dusk, cinematic. warmer colours")
        ctx.check("the gate showed the artboard path and the prompt", "render.png" in answers.seen[0]["text"]
                  and "a lighthouse" in answers.seen[0]["text"] and answers.seen[0]["position"] == "You")
        ctx.check("the gate rounds go 1, 2", [g["round"] for g in answers.seen] == [1, 2])
        ctx.check("the gate id is <run>:<step>", answers.seen[0]["id"] == f"{run_dir.name}:approve")
        ctx.check("render rounds 2, confirm rounds 2", read_step(run_dir, 4)["rounds"] == 2 and read_step(run_dir, 5)["rounds"] == 2)
        ctx.check("the render step keeps the instruction", read_step(run_dir, 4)["instructions"] == ["warmer colours"])
        proj_dir = Path(report["project_path"])
        ctx.check("the redo wrote over the same artboard as version 2",
                  (proj_dir / "artboards" / "hero" / "v2" / "render.png").is_file()
                  and not (proj_dir / "artboards" / "hero-2").exists())
        ctx.check("no gate or answer file is left", not list((run_dir / "steps").glob("*.gate.json"))
                  and not list((run_dir / "steps").glob("*.answer.json")))


@test
def test_confirm_stop_and_the_redo_cap(ctx: Ctx):
    with FakeComfy() as fake:
        run_dir, report, _ = _gated(fake, {"approve": [("stop", "not on brand")]}, "flow-stop")
        ctx.check(f"stop stops the run with the reason, got {report.get('stop_reason')}",
                  report["status"] == "stopped" and report["stop_reason"] == "stopped at approve: not on brand")
        states = {s["id"]: s["state"] for s in report["steps"]}
        ctx.check(f"approve failed, publish never ran, got {states}", states["approve"] == "failed" and states["publish"] == "pending")
        posts = json.loads((Path(report["project_path"]) / "posts.json").read_text(encoding="utf-8"))
        ctx.check("posts.json stays empty", posts == [])
        n = len(fake.prompts)
        _, capped, answers = _gated(fake, {"approve": [("redo", f"try {i}") for i in range(9)]}, "flow-cap")
        ctx.check(f"the redo cap stops after 5 renders, got {capped.get('stop_reason')}",
                  capped["status"] == "stopped" and "rendered 5 times" in capped["stop_reason"] and len(fake.prompts) - n == 5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow run tests"))
