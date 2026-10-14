"""tests.test_flows_run2 -- the flow runner's gates and stops (Halo 3.0.4.0
round R3): the org step's approval gate answered through the sink (accept,
redo with an instruction re-running the position, stop), the run budget
stop, resume after a killed render, stop.json between steps, live posting
stopping when the postiz CLI or its credentials are missing, intake checks and the answer file's rules.
ComfyUI, models and Postiz are fakes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers import fake_postiz  # noqa: E402
from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_flow import Answers, FakeOneShot, FakeOrg, make_adapters, new_run, template_spec  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_org_gate_accept_and_redo_through_the_sink(ctx: Ctx):
    from halo_harness.flows.run import run
    from halo_harness.flows.state import read_events, read_step
    with FakeComfy() as fake:
        org = FakeOrg()
        answers = Answers({"marketing": [("redo", "more neon"), ("accept", "")], "approve": [("accept", "")]})
        run_dir = new_run(template_spec(), project="flow-orggate")
        report = run(run_dir, adapters=make_adapters(fake.url, run_org=org, answers=answers))
        ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check(f"the sink turned redo into edit with the instruction, then accept, got {org.decisions}",
                  org.decisions == [{"action": "edit", "instruction": "more neon"}, {"action": "accept"}])
        gates_seen = [g for g in answers.seen if g["step"] == "marketing"]
        ctx.check("the org gate names the position and shows its result, rounds 1 and 2",
                  [g["position"] for g in gates_seen] == ["Art Director"] * 2 and [g["round"] for g in gates_seen] == [1, 2]
                  and gates_seen[1]["text"].endswith("more neon"))
        ctx.check("the re-run position's prompt went to the render",
                  fake.prompts[-1]["graph"]["4"]["inputs"]["prompt"] == "a lighthouse at dusk, cinematic, more neon")
        ctx.check("the org step counts its gate rounds and both org costs", read_step(run_dir, 3)["rounds"] == 2
                  and abs(read_step(run_dir, 3)["cost_usd"] - 0.10) < 1e-9)
        waits = [e for e in read_events(run_dir) if e["kind"] == "state" and e["data"].get("state") == "waiting"]
        ctx.check("the org step went to waiting while the gate was open", any(e["step"] == "marketing" for e in waits))
        notes = [e["text"] for e in read_events(run_dir) if e["kind"] == "note" and e["step"] == "marketing"]
        ctx.check(f"the org's own lines landed as notes, got {notes}", "marketing: Strategist started" in notes)
        stop_org = FakeOrg()
        r2 = run(new_run(template_spec(), project="flow-orgstop"),
                 adapters=make_adapters(fake.url, run_org=stop_org, answers=Answers({"marketing": [("stop", "wrong tone")]})))
        ctx.check(f"stop at the org gate stops the run, got {r2.get('stop_reason')}", r2["status"] == "stopped"
                  and r2["stop_reason"] == "Art Director's result was stopped at the gate: wrong tone")


@test
def test_run_budget_stop(ctx: Ctx):
    from halo_harness.flows.run import run
    with FakeComfy() as fake:
        org = FakeOrg()
        report = run(new_run(template_spec(budget_usd=0.02), project="flow-budget"),
                     adapters=make_adapters(fake.url, run_org=org, auto_accept=True))
        ctx.check(f"the run stops when its budget is spent, got {report.get('stop_reason')}",
                  report["status"] == "stopped" and report["stop_reason"] == "the run budget $0.02 is spent ($0.0200)")
        ctx.check("the org never ran", org.calls == [])
        states = {s["id"]: s["state"] for s in report["steps"]}
        ctx.check(f"plan done, marketing pending, got {states}", states["plan"] == "done" and states["marketing"] == "pending")
        org2 = FakeOrg()
        run(new_run(template_spec(budget_usd=0.5), project="flow-budget"),
            adapters=make_adapters(fake.url, run_org=org2, auto_accept=True))
        ctx.check(f"the org budget is min(step, run remaining), got {org2.calls[0]['budget_usd']}",
                  abs(org2.calls[0]["budget_usd"] - 0.48) < 1e-9)


class _Killed(KeyboardInterrupt):
    pass


@test
def test_resume_after_a_killed_render(ctx: Ctx):
    from halo_harness.flows.run import run
    from halo_harness.flows.state import read_events, read_flow
    from halo_harness.media.comfy_client import ComfyClient
    with FakeComfy() as fake:
        shot, org = FakeOneShot(), FakeOrg()

        def dying():
            raise _Killed()
        run_dir = new_run(template_spec(), project="flow-resume")
        try:
            run(run_dir, adapters=make_adapters(fake.url, one_shot=shot, run_org=org, auto_accept=True, comfy_factory=dying))
            killed = False
        except KeyboardInterrupt:
            killed = True
        ctx.check("the render was killed mid-run", killed and read_flow(run_dir)["steps"][3]["state"] == "running")
        report = run(run_dir, adapters=make_adapters(fake.url, one_shot=shot, run_org=org, auto_accept=True,
                                                     comfy_factory=lambda: ComfyClient(fake.url, timeout=10)))
        ctx.check(f"the resumed run finished, got {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check("roles and org were not run again", len(shot.calls) == 2 and len(org.calls) == 1)
        ctx.check("one render was queued", len(fake.prompts) == 1)
        ctx.check("the log says where it picked up", any(e["text"] == "resume: picking up at render" for e in read_events(run_dir)))
        ctx.check("the run cost counts the earlier steps once", abs(report["cost_usd"] - 0.07) < 1e-9)


@test
def test_stop_json_between_steps(ctx: Ctx):
    from halo_harness.flows.run import run
    from halo_harness.flows.state import request_stop
    holder = {}

    def hook(role, prompt, model):
        if role == "researcher":
            request_stop(holder["run"], "the owner said stop")
    with FakeComfy() as fake:
        org = FakeOrg()
        run_dir = new_run(template_spec(), project="flow-stopjson")
        holder["run"] = run_dir
        report = run(run_dir, adapters=make_adapters(fake.url, one_shot=FakeOneShot(hook=hook), run_org=org, auto_accept=True))
        ctx.check(f"stop.json stops the run before the next step, got {report.get('stop_reason')}",
                  report["status"] == "stopped" and report["stop_reason"] == "the owner said stop" and org.calls == [])
        ctx.check("the plan step itself finished", {s["id"]: s["state"] for s in report["steps"]}["plan"] == "done")
        again = run(run_dir, adapters=make_adapters(fake.url, run_org=org, auto_accept=True))
        ctx.check("resume clears stop.json and finishes", again["status"] == "finished" and not (run_dir / "stop.json").exists())


@test
def test_live_post_and_intake_checks(ctx: Ctx):
    from halo_harness.flows.run import run
    spec = template_spec()
    for s in spec["steps"]:
        if s["id"] == "publish":
            s["live"] = True
    with FakeComfy() as fake, tempfile.TemporaryDirectory() as empty, fake_postiz.put_on_path(empty, exclusive=True):
        r = run(new_run(spec, project="flow-live"), adapters=make_adapters(fake.url, auto_accept=True))
        ctx.check(f"live: true without the postiz CLI stops with that reason, got {r.get('stop_reason')}",
                  r["status"] == "stopped" and "needs the postiz CLI on PATH" in r["stop_reason"])
        r = run(new_run(template_spec(), brief="", project="flow-nobrief"), adapters=make_adapters(fake.url, auto_accept=True))
        ctx.check(f"a missing brief stops at intake, got {r.get('stop_reason')}",
                  r["status"] == "stopped" and r["stop_reason"].startswith("intake: brief is required"))
        r = run(new_run(template_spec(), platforms="x,myspace", project="flow-badplat"), adapters=make_adapters(fake.url, auto_accept=True))
        ctx.check(f"a platform outside the choices stops at intake, got {r.get('stop_reason')}",
                  r["status"] == "stopped" and "myspace" in r["stop_reason"])
        r = run(new_run(template_spec(), assets=["/no/such/file.png"], project="flow-noasset"), adapters=make_adapters(fake.url, auto_accept=True))
        ctx.check(f"a missing asset stops at intake, got {r.get('stop_reason')}", "no such file" in str(r.get("stop_reason")))


@test
def test_answer_file_rules(ctx: Ctx):
    from halo_harness.flows import gates
    from halo_harness.flows.state import Flow
    run_dir = new_run(template_spec(), project="flow-answer")
    ok, msg = gates.write_answer(run_dir, "approve", "accept")
    ctx.check(f"no gate open -> an error, got {msg}", not ok and "not waiting" in msg)
    flow = Flow(run_dir)
    gate = gates.post_gate(flow, 5, {"id": f"{run_dir.name}:approve", "step": "approve", "position": "You", "text": "x"})
    ctx.check("the gate file is there and open_gate finds it", gates.open_gate(run_dir)["id"] == gate["id"])
    for step, action, want in (("nope", "accept", "has no step"), ("approve", "maybe", "accept, redo")):
        ok, msg = gates.write_answer(run_dir, step, action)
        ctx.check(f"{step} {action} -> {want!r}, got {msg}", not ok and want in msg)
    ok, msg = gates.write_answer(run_dir, "approve", "approve")
    ctx.check("'approve' is an alias of accept", ok and "accept" in msg)
    ans = gates.wait_answer(flow, 5, gate, poll_s=0.01)
    ctx.check(f"wait_answer reads it and closes the gate, got {ans}", ans == {"action": "accept", "instruction": ""}
              and gates.open_gate(run_dir) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow run tests 2"))
