"""tests.test_paperclip -- the Paperclip integration (Halo 2.2.0 rounds
C1-C3) over tests/helpers/fake_paperclip.py: the client's transport and
errors, `halo paperclip-run` (idle, todo -> checkout -> comment -> done,
a failed turn, the run-id header), lineup -> company sync (one agent per
assignment, reporting lines, idempotent) and pull (org.positions back).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_paperclip import FakePaperclip  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_client_transport_and_errors(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip, PaperclipError
    fake = FakePaperclip(require_token="tok")
    try:
        c = Paperclip(fake.base_url + "/api", "tok", run_id="run-1")
        ctx.check("a base URL ending in /api is normalised", c.base_url == fake.base_url)
        ctx.check("health reads", c.reachable() and c.health()["status"] == "ok")
        ctx.check("companies list", c.companies()[0]["name"] == "Fake Co")
        a = c.create_agent(fake.company["id"], {"name": "x", "adapterType": "process"})
        ctx.check("create agent posts and returns the row", a["name"] == "x" and a["id"] in fake.agents)
        c.comment(list(fake.issues.values())[0]["id"] if fake.issues else fake.add_issue("i")["id"], "hi")
        ctx.check("mutating calls carry the run id header", any(h.get("X-Paperclip-Run-Id") == "run-1" for m, p, b, h in fake.requests if m == "POST" and "comments" in p))
        bad = Paperclip(fake.base_url, "wrong")
        try:
            bad.companies()
            ctx.check("a 401 raises PaperclipError", False)
        except PaperclipError as e:
            ctx.check("a 401 raises PaperclipError with the status", e.status == 401)
        try:
            Paperclip("http://127.0.0.1:1").health()
            ctx.check("an unreachable server raises", False)
        except PaperclipError as e:
            ctx.check("an unreachable server raises status 0", e.status == 0)
    finally:
        fake.close()


def _env(fake, agent):
    return {"PAPERCLIP_API_URL": fake.base_url, "PAPERCLIP_API_KEY": "k", "PAPERCLIP_AGENT_ID": agent["id"],
            "PAPERCLIP_COMPANY_ID": fake.company["id"], "PAPERCLIP_RUN_ID": "run-9", "PATH": "x"}


@test
def test_heartbeat_run_idle_done_and_failed(ctx: Ctx):
    from halo_harness.paperclip.adapter import build_prompt, run_heartbeat
    fake = FakePaperclip()
    try:
        agent = fake.add_agent("worker", title="Builds things", metadata={"halo_agent": "implementer"})
        out = io.StringIO()
        ctx.check("no assigned issue -> idle heartbeat, exit 0", run_heartbeat(_env(fake, agent), runner=lambda *a: (0, "x"), out=out) == 0 and "idle" in out.getvalue())
        ctx.check("an idle heartbeat posts nothing", not fake.comments)
        issue = fake.add_issue("Do the thing", assignee=agent["id"], description="Please do it.")
        seen = {}

        def runner(prompt, model, cwd, env):
            seen.update(prompt=prompt, model=model, cwd=cwd, env=env)
            return 0, "Done: I did the thing."
        code = run_heartbeat(_env(fake, agent), runner=runner, out=io.StringIO())
        ctx.check("a todo issue is checked out, worked and marked done", code == 0 and fake.issues[issue["id"]]["status"] == "done")
        ctx.check("the checkout carried the run id", fake.issues[issue["id"]]["checkoutRunId"] == "run-9")
        ctx.check("the reply is posted as the comment", fake.comments and fake.comments[-1]["body"] == "Done: I did the thing.")
        ctx.check("the prompt names the issue, the goal, the project and the agent",
                  "Do the thing" in seen["prompt"] and "Ship it" in seen["prompt"] and "Halo" in seen["prompt"] and "worker" in seen["prompt"] and "Builds things" in seen["prompt"])
        ctx.check("the API key never reaches the child's env", "PAPERCLIP_API_KEY" in seen["env"] and seen["env"]["PAPERCLIP_API_KEY"] == "k")
        issue2 = fake.add_issue("Break", assignee=agent["id"])
        code = run_heartbeat(_env(fake, agent), runner=lambda *a: (1, "boom"), out=io.StringIO())
        ctx.check("a failed turn exits 1, comments the failure and leaves the issue in progress",
                  code == 1 and "failed" in fake.comments[-1]["body"] and fake.issues[issue2["id"]]["status"] == "in_progress")
        ctx.check("outside a heartbeat the command refuses with exit 2", run_heartbeat({"PATH": "x"}, runner=lambda *a: (0, ""), out=io.StringIO()) == 2)
        ctx.check("build_prompt caps its length", len(build_prompt({"issue": {"title": "t", "description": "x" * 100_000}}, {}, {})) <= 60_000)
    finally:
        fake.close()


@test
def test_sync_and_pull(ctx: Ctx):
    from halo_harness.paperclip.client import Paperclip
    from halo_harness.paperclip.sync import org_tree_lines, pull_reporting_lines, reporting_lines, sync_lineup
    from halo_harness.teams_yaml import load_team_template_raw
    fake = FakePaperclip()
    try:
        c = Paperclip(fake.base_url)
        out = io.StringIO()
        agents = sync_lineup(c, fake.company["id"], "halo-dev-cycle", cwd=Path("C:/proj"), out=out)
        ctx.check("one agent per assignment", len(agents) == 7 and len(fake.agents) == 7)
        boss = next(a for a in fake.agents.values() if a["name"] == "boss")
        ctx.check("the main slot is the ceo with no manager", boss["role"] == "ceo" and boss["reportsTo"] is None)
        ctx.check("every other member reports to boss", all(a["reportsTo"] == boss["id"] for a in fake.agents.values() if a is not boss))
        worker = next(a for a in fake.agents.values() if a["name"] == "worker")
        ctx.check("agents run halo paperclip-run through the process adapter in the project dir",
                  worker["adapterType"] == "process" and worker["adapterConfig"]["args"] == ["paperclip-run"] and worker["adapterConfig"]["cwd"] == "C:\\proj" or worker["adapterConfig"]["cwd"].endswith("proj"))
        ctx.check("metadata carries the lineup, slot and bio", worker["metadata"] == {"halo_lineup": "halo-dev-cycle", "halo_slot": "worker", "halo_agent": "implementer", "halo_role": "subagent"})
        ctx.check("a budget becomes cents", isinstance(worker.get("budgetMonthlyCents"), int) or "budgetMonthlyCents" not in worker)
        n_before = len(fake.requests)
        sync_lineup(c, fake.company["id"], "halo-dev-cycle", cwd=Path("C:/proj"), out=io.StringIO())
        ctx.check("a second sync updates in place, never duplicates", len(fake.agents) == 7 and not any(m == "POST" and p.endswith("/agents") for m, p, b, h in fake.requests[n_before:]))
        tree = org_tree_lines(c.org(fake.company["id"]))
        ctx.check("the org tree prints boss on top with six reports", tree[0].startswith("boss") and sum(l.startswith("  ") for l in tree) == 6)
        raw = load_team_template_raw("halo-dev-cycle")
        lines = reporting_lines(raw)
        ctx.check("reporting_lines defaults every member to main", set(lines.values()) == {"boss"} and len(lines) == 6)
        org = pull_reporting_lines(c, fake.company["id"], "halo-dev-cycle")
        ctx.check("pull writes org.positions with reports_to into the lineup (user scope copy)",
                  len(org["positions"]) == 7 and sum(1 for p in org["positions"] if p.get("reports_to") == "boss") == 6)
    finally:
        fake.close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="paperclip tests"))
