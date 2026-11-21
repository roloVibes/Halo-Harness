"""tests.test_crew_flow_run -- Halo 3.6.0.6 P (batch 2, entry 1): Studio RUNS a crew workflow for real, by name.

`POST crew/run {name, task}` (studio/crew_flow_api.py `post_run`) is owner-only; it starts a session the way POST
sessions/new does (studio/sessions_new_api.py `start`: Studio's child, it ends with Studio) with `--run-workflow <name>
--workflow-task <task>`, and that session runs the workflow on its own command pump (`run_workflow`, crew/flow_run.py)
through the Workflow tool's code (crew/flow_door.run): no model is asked to call a tool, main gets no turn. Over a
real Studio and a real headless child on the fake upstream (tests/helpers/headless_rig.py), with the pack that ships
with Halo (doc-review) installed and enabled in the scratch home:

1. without the proof: 403 NEEDS_OWNER; an unknown name and an empty task: a plain refusal, and no session starts;
2. the pack's workflow: 202 naming the session, the workflow and the folder; the session's record holds the receipt
   "crew workflow doc-review--review-docs · ran on the step runner · done", each step ran as a child, main had no turn;
3. Studio ending ends that session (end_started), nothing survives.
Run: python -m tests.test_crew_flow_run
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FLOW = "doc-review--review-docs"
RECEIPT = f"crew workflow {FLOW} · ran on the step runner · done"


def with_pack(rig, name: str = "doc-review") -> None:
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    from halo_harness.packs.install import install
    from tests.helpers.packs_home import fixture
    src = rig.home / "sources" / name
    shutil.copytree(fixture(name), src, ignore=shutil.ignore_patterns("__pycache__"))
    ok, lines = install(str(src), project=False, cwd=rig.proj)
    assert ok, lines
    ok, lines = enable(find(name, cwd=rig.proj), grant=["bash"])
    assert ok, lines
    registry.invalidate()


def call(server, path: str, body, owner: bool):
    from halo_harness.studio.owner_proof import HEADER, header_for
    from tests.helpers.kept_http import request
    heads = {"Authorization": "Bearer " + server.token, "Content-Type": "application/json"}
    if owner:
        heads[HEADER] = header_for(server)
    status, data, _h = request(server.server_address[1], "POST", "/api/" + path, json.dumps(body).encode("utf-8"),
                               heads, timeout=30, who=server.token)
    return status, json.loads(data.decode("utf-8") or "{}")


def _rows(rig) -> list:
    try:
        return json.loads((rig.state / "studio-sessions.json").read_text("utf-8")).get("sessions") or []
    except (OSError, ValueError):
        return []


@test
def test_studio_runs_a_packs_workflow_by_name_in_a_session_that_ends_with_studio(ctx: Ctx):
    from halo_harness.bg_run import pid_alive
    from halo_harness.studio import sessions_new_api as N
    from halo_harness.studio.owner_proof import NEEDS_OWNER
    from tests.helpers.headless_rig import MODEL, HeadlessRig
    from tests.helpers.session_rig import wait_for
    with HeadlessRig() as rig:
        with_pack(rig)
        rig.spawn_env()
        server = rig.studio()
        status, got = call(server, "crew/run", {"name": FLOW, "task": "Review README.md"}, owner=False)
        ctx.check(f"without the proof: 403 NEEDS_OWNER, got {status} {got}", status == 403 and got.get("error") == NEEDS_OWNER)
        status, got = call(server, "crew/run", {"name": "no-such-flow", "task": "Review README.md"}, owner=True)
        ctx.check(f"an unknown name: a plain refusal, got {status} {got}", status == 404 and "no-such-flow" in str(got.get("error")))
        status, got = call(server, "crew/run", {"name": FLOW, "task": "  "}, owner=True)
        ctx.check(f"an empty task: a plain refusal, got {status} {got}", status == 422 and got.get("error"))
        ctx.check(f"no session started for a refusal, got {_rows(rig)}", _rows(rig) == [])
        status, got = call(server, "crew/run", {"name": FLOW, "task": "Review README.md", "model": MODEL}, owner=True)
        sid, pid = str(got.get("session_id") or ""), got.get("pid")
        if pid:
            rig.pids.append(pid)
        ctx.check(f"202 naming the session, the workflow and the folder, got {status} {got}",
                  status == 202 and len(sid) == 32 and got.get("workflow") == FLOW
                  and Path(str(got.get("cwd"))).resolve() == rig.proj.resolve())
        if status != 202:
            return
        entry = rig.entry(sid, 90)
        ctx.check("the session registered", entry is not None)
        text = wait_for(lambda: (lambda t: t if RECEIPT in t else None)(rig.log_text(sid)), 120, 0.3) or rig.log_text(sid)
        log = Path(str(got.get("log") or "")).read_text("utf-8", "replace")[-1500:] if got.get("log") else ""
        ctx.check(f"the session's record holds the receipt {RECEIPT!r}\n{text[-1500:]}\n{log}", RECEIPT in text)
        rows = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
        ctx.check("main had no turn: no prompt was sent to a model to ask it to run the workflow",
                  not any(r.get("type") in ("user", "user_message") for r in rows))
        ctx.check("each step ran as a child, by its agent's name",
                  "doc-review--reviewer" in text and "doc-review--writer" in text)
        code, tree = rig.api(server, "GET", f"sessions/{sid}/agents")
        keys = [str(((r.get("spawn") or {}).get("group") or {}).get("key") or "") for r in (tree.get("agents") or [])]
        ctx.check(f"each step's helper is in the run's group, as the Workflow tool's (Live draws it), got {code} {keys}",
                  code == 200 and sum(k.startswith(f"workflow:{FLOW}#") for k in keys) >= 2)
        ended = N.end_started(wait_s=30.0)
        ctx.check(f"Studio ending ends the session it started, got {[r.get('session_id') for r in ended]}",
                  any(r.get("session_id") == sid for r in ended))
        ctx.check("the child ended", wait_for(lambda: not pid_alive(pid) and "ended", 30) == "ended")
    ctx.check(f"no child survives, got {rig.survivors()}", rig.survivors() == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
