"""tests.test_flows_cli -- `halo flow` (Halo 3.0.4.0 round R3): new (with
--name/--project, refusing to overwrite without --force), templates,
validate, run --yes with intake flags and --set overrides, runs, status,
report (text and --json), stop, answer over a prepared run folder, and a
run left waiting at the confirm gate answered from "another terminal"
(redo with an instruction, then accept). Models and ComfyUI are fakes,
wired in through cli_run.ADAPTER_FACTORY.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_flow import FakeOneShot, FakeOrg, make_adapters, new_run, template_spec, uniq  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _cli(*argv) -> "tuple[int, str, str]":
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(["flow", *argv])
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue(), err.getvalue()


@contextlib.contextmanager
def _fakes(fake, **kw):
    from halo_harness.flows import cli_run
    shot, org = kw.pop("one_shot", FakeOneShot()), kw.pop("run_org", FakeOrg())

    def factory(**args):
        return make_adapters(fake.url, one_shot=shot, run_org=org, auto_accept=args.get("auto_accept"),
                             model=args.get("model"), cwd=args.get("cwd"))
    cli_run.ADAPTER_FACTORY = factory
    try:
        yield shot, org
    finally:
        cli_run.ADAPTER_FACTORY = None


@test
def test_new_templates_validate(ctx: Ctx):
    from halo_harness.flows.spec import flows_dir, load_flow
    name = uniq("promo")
    code, out, _ = _cli("templates")
    ctx.check("templates lists social-post", code == 0 and "social-post" in out)
    code, out, err = _cli("new", "social-post", "--name", name, "--project", "My Demo Post")
    path = flows_dir() / f"{name}.flow.yaml"
    ctx.check(f"new writes the user flow, got {code} {out} {err}", code == 0 and path.is_file() and f"wrote {path}" in out)
    data = load_flow(path)
    ctx.check(f"the name and project are filled in, got {data.get('name')} {data.get('project')}",
              data["name"] == name and data["project"] == "my-demo-post")
    ctx.check("the template's comments are kept", "# Halo 3.0.4.0" in path.read_text(encoding="utf-8"))
    code, _, err = _cli("new", "social-post", "--name", name)
    ctx.check("a second new refuses to overwrite", code == 1 and "--force" in err)
    ctx.check("--force overwrites", _cli("new", "social-post", "--name", name, "--force")[0] == 0)
    ctx.check("an unknown template is an error", _cli("new", "nope")[0] == 2)
    code, out, _ = _cli("validate", name)
    ctx.check(f"validate says ok, got {out}", code == 0 and ": ok" in out)
    bad = flows_dir() / f"{name}-bad.flow.yaml"
    bad.write_text("name: bad\nsteps:\n  - {id: a, kind: teleport}\n", encoding="utf-8")
    code, out, _ = _cli("validate", f"{name}-bad")
    ctx.check(f"validate lists problems and exits 1, got {out}", code == 1 and "unknown kind 'teleport'" in out)
    ctx.check("run refuses a flow with problems", _cli("run", f"{name}-bad")[0] == 2)
    ctx.check("help prints the commands", "halo flow answer" in _cli("--help")[1])


@test
def test_run_yes_runs_status_report(ctx: Ctx):
    name = uniq("cli-run")
    _cli("new", "social-post", "--name", name, "--project", name)
    with FakeComfy() as fake, _fakes(fake) as (shot, org):
        code, out, err = _cli("run", name, "--yes", "--brief", "a one-line teaser", "--input", "platforms=x",
                              "--set", "render.width=512", "--set", "render.height=640")
        ctx.check(f"run --yes finishes, got {code}: {err[-400:]}", code == 0)
        ctx.check("it prints the run id, one line per step and the report", out.startswith("run ")
                  and "plan done" in out and "render done" in out and f"flow {name} run" in out and "artboard hero" in out)
        g = fake.prompts[-1]["graph"]
        ctx.check("--set overrides the render's set", g["5"]["inputs"]["width"] == 512 and g["5"]["inputs"]["height"] == 640)
        ctx.check("--input reached the intake", len(json.loads((Path(out.split("project ")[-1].strip()) / "posts.json")
                                                               .read_text(encoding="utf-8"))) == 1)
        run_id = out.split()[1].rstrip(":")
        code, out, _ = _cli("runs")
        ctx.check("runs lists it as finished", code == 0 and run_id in out and "finished" in out)
        code, out, _ = _cli("status", run_id)
        ctx.check(f"status shows each step, got {out}", code == 0 and "render" in out and "done" in out and "$0.07" in out)
        code, out, _ = _cli("report", run_id)
        ctx.check("report prints the text form", code == 0 and "finished" in out and "post x: dry run" in out)
        code, out, _ = _cli("report", run_id, "--json")
        ctx.check("report --json is the report.json", code == 0 and json.loads(out)["run"] == run_id)
        ctx.check("an unknown run is exit 2", _cli("status", "nope-nope")[0] == 2)
        code, out, _ = _cli("run", name, "--resume")
        ctx.check("--resume with nothing unfinished says so", code == 1)


@test
def test_answer_and_stop_on_a_prepared_run(ctx: Ctx):
    from halo_harness.flows import gates
    from halo_harness.flows.state import Flow
    run_dir = new_run(template_spec(), project="flow-cli-prep")
    flow = Flow(run_dir)
    gates.post_gate(flow, 5, {"id": f"{run_dir.name}:approve", "step": "approve", "position": "You",
                              "text": "/x/hero/render.png\na lighthouse", "round": 2})
    code, out, _ = _cli("status", run_dir.name)
    ctx.check(f"status shows the waiting gate and how to answer, got {out}", "waiting at approve" in out
              and "a lighthouse" in out and f"halo flow answer {run_dir.name} approve" in out)
    code, out, _ = _cli("answer", run_dir.name, "approve", "redo", "warmer", "colours")
    ans = json.loads((run_dir / "steps" / "5.answer.json").read_text(encoding="utf-8"))
    ctx.check(f"answer writes the answer file for that gate and round, got {ans}", code == 0 and ans["action"] == "redo"
              and ans["instruction"] == "warmer colours" and ans["id"] == f"{run_dir.name}:approve" and ans["round"] == 2)
    ctx.check("answering a step that is not waiting is exit 1", _cli("answer", run_dir.name, "plan", "accept")[0] == 1)
    ctx.check("a bad action is exit 1", _cli("answer", run_dir.name, "approve", "perhaps")[0] == 1)
    ctx.check("too few arguments is exit 2", _cli("answer", run_dir.name)[0] == 2)
    code, out, _ = _cli("stop", run_dir.name, "--reason", "enough")
    ctx.check("stop writes stop.json with the reason", code == 0 and json.loads((run_dir / "stop.json")
                                                                                .read_text(encoding="utf-8"))["reason"] == "enough")
    ctx.check("report before the run ends says there is none yet", _cli("report", run_dir.name)[0] == 1)


@test
def test_waiting_run_answered_from_another_terminal(ctx: Ctx):
    from halo_harness.flows.run import run
    from halo_harness.flows.state import read_step
    with FakeComfy() as fake:
        run_dir = new_run(template_spec(), project="flow-cli-wait")
        box = {}
        t = threading.Thread(target=lambda: box.setdefault("report", run(run_dir, adapters=make_adapters(
            fake.url, run_org=FakeOrg(gate=False)))), daemon=True)
        t.start()

        def wait_round(n):
            deadline = time.time() + 20
            while time.time() < deadline:
                g = json.loads((run_dir / "steps" / "5.gate.json").read_text(encoding="utf-8")) \
                    if (run_dir / "steps" / "5.gate.json").is_file() else {}
                if g.get("round") == n:
                    return True
                time.sleep(0.02)
            return False
        ctx.check("the run waits at the confirm gate", wait_round(1))
        ctx.check("redo from the CLI", _cli("answer", run_dir.name, "approve", "redo", "warmer colours")[0] == 0)
        ctx.check("the gate opens again for round 2", wait_round(2))
        ctx.check("accept from the CLI", _cli("answer", run_dir.name, "approve", "accept")[0] == 0)
        t.join(20)
        rep = box.get("report") or {}
        ctx.check(f"the run finished, got {rep.get('status')} {rep.get('stop_reason')}", rep.get("status") == "finished")
        ctx.check("the redo rendered again with the instruction", len(fake.prompts) == 2
                  and fake.prompts[-1]["graph"]["4"]["inputs"]["prompt"].endswith("warmer colours"))
        ctx.check("confirm took two rounds", read_step(run_dir, 5)["rounds"] == 2)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow cli tests"))
