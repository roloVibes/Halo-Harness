"""tests.test_coach_summary -- Halo 3.1.3.0 R1: where the coach loop shows up
beyond its card, over seeded run folders (tests/helpers/coach_seed.py):

1. the run reports' coach line ("coach: N suggestions, M applied, top: ...") in
   `orchestra/report.format_report` and the flow report, and for a mission;
2. the Fleet digest's coach row per run the coach read;
3. Studio's coach routes: POST <coach path>/ask, /apply (confirm false: the
   preview, nothing written; true: written), /undo (409 with the reason), 405;
4. `/coach` (the slash command) prints the card and the confirm card.
Run: python -m tests.test_coach_summary
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_coach_ask import Seam
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
DENIED = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]


def _req(h, method, path, body=None, query=None):
    from halo_harness.studio.api import Request
    return Request(method=method, path=path, query=query or {}, body=body or {}, cwd=h.root, state_dir=h.state)


@test
def test_the_reports_carry_the_coach_line(ctx: Ctx):
    from halo_harness.flows.report import format_report as flow_report
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra.coach import cached
    from halo_harness.orchestra.coach_record import summary, summary_line
    from halo_harness.orchestra.report import format_report, load_report
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        text = format_report(load_report(run), run)
        ctx.check(f"the orchestra report's last line, got {text.splitlines()[-1]!r}",
                  text.splitlines()[-1] == "  coach: 1 suggestion, 0 applied, top: bio `coach-deny` could not call `WebFetch`")
        ctx.check("no run folder: no coach line", "coach:" not in format_report(load_report(run)))
        CA.apply(cached(run, state_dir=h.state), "tools-1-WebFetch", run, state_dir=h.state)
        ctx.check(f"one applied, got {summary(run)!r}", summary(run).startswith("coach: 1 suggestion, 1 applied, top: "))
        flow = S.flow_run(h.state)
        ftext = flow_report(json.loads((flow / "report.json").read_text(encoding="utf-8")), flow)
        ctx.check(f"the flow report's coach line above its total line, got {ftext.splitlines()[-2:]!r}",
                  ftext.splitlines()[-2].startswith("  coach: 2 suggestions, 0 applied, top: ") and "  total $" in ftext.splitlines()[-1])
        ctx.check("a mission's line", summary(S.mission_folder(h.state)).startswith("coach: 5 suggestions, 0 applied"))
        ctx.check("the empty run's line names no top", summary_line(0, 0, "") == "coach: 0 suggestions, 0 applied")


@test
def test_the_fleet_digest_has_a_coach_row_per_run(ctx: Ctx):
    from halo_harness.fleet import digest
    from halo_harness.orchestra.coach_record import summary
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        summary(run)
        summary(S.team_run(h.root))
        d = digest.compute(h.state, 0.0, local_id="me", local_name="here")
        mine = next(b for b in d["harnesses"] if b["local"])
        ctx.check(f"two coach rows, got {mine['coach']}", [r["kind"] for r in mine["coach"]] == ["orchestra", "team"]
                  and mine["coach"][0]["n"] == 1 and mine["coach"][0]["applied"] == 0 and not mine["quiet"])
        text = digest.text(d)
        ctx.check(f"the digest's line, got {text!r}", f"  coach    orchestra {S.RUN}: 1 suggestion, 0 applied, top: bio "
                  "`coach-deny` could not call `WebFetch`" in text)
        later = digest.compute(h.state, 4e9, local_id="me", local_name="here")
        ctx.check("a run read before `since` is not listed", next(b for b in later["harnesses"] if b["local"])["coach"] == [])


@test
def test_studio_s_coach_routes_ask_apply_and_undo(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw
    from halo_harness.studio.coach_api import dispatch_coach
    from tests.helpers import coach_seed as S
    with Home() as h, Seam(lambda p: {"text": "Allow WebFetch: the lane needed it.", "ok": True}):
        S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        base = f"orchestra/{S.RUN}/coach"
        status, got = dispatch_coach(_req(h, "GET", base))
        ctx.check(f"GET: the card with its overlay, got {status}", status == 200 and got["suggestions"][0]["paragraph"] is None
                  and got["suggestions"][0]["applied"] is None)
        status, got = dispatch_coach(_req(h, "POST", base + "/ask", {"id": "tools-1-WebFetch"}))
        ctx.check(f"ask: the paragraph, got {status} {got}", status == 200 and got["paragraph"] == "Allow WebFetch: the lane needed it.")
        status, got = dispatch_coach(_req(h, "POST", base + "/apply", {"id": "tools-1-WebFetch"}))
        ctx.check(f"apply without confirm: the preview, got {status}", status == 200 and got["applied"] is None
                  and got["preview"]["diff"] and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"]
                  == ["WebFetch", "Agent"])
        status, got = dispatch_coach(_req(h, "POST", base + "/apply", {"id": "tools-1-WebFetch", "confirm": True}))
        aid = (got.get("applied") or {}).get("apply_id")
        ctx.check(f"apply with confirm writes, got {status} {aid}", status == 200 and aid
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["Agent"])
        status, got = dispatch_coach(_req(h, "GET", base))
        ctx.check("the card is Applied", got["suggestions"][0]["applied"]["state"] == "applied"
                  and got["suggestions"][0]["paragraph"] == "Allow WebFetch: the lane needed it.")
        status, got = dispatch_coach(_req(h, "POST", base + "/undo", {"apply_id": aid}))
        ctx.check(f"undo, got {status} {got}", status == 200 and got["ok"])
        status, got = dispatch_coach(_req(h, "POST", base + "/undo", {"apply_id": aid}))
        ctx.check(f"a second undo is 409 with the reason, got {status} {got}", status == 409 and "already undone" in got["error"])
        status, got = dispatch_coach(_req(h, "POST", base + "/apply", {"id": "nope"}))
        ctx.check(f"an unknown id is 422, got {status}", status == 422 and "no suggestion" in got["error"])
        ctx.check("GET on a verb is 405", dispatch_coach(_req(h, "GET", base + "/apply"))[0] == 405)
        ctx.check("POST on the card is 405", dispatch_coach(_req(h, "POST", base))[0] == 405)
        ctx.check("an unknown run is 404", dispatch_coach(_req(h, "POST", "orchestra/nope/coach/ask", {"id": "x"}))[0] == 404)
        team = S.team_run(h.root)
        status, got = dispatch_coach(_req(h, "POST", "team/coach/ask", {"id": "coordination-copy-loops"}, {"run": team.name}))
        ctx.check(f"a team run's ask, got {status} {got}", status == 200 and got["paragraph"])


@test
def test_the_coach_slash_command(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw
    from halo_harness.commands.builtins import _cmd_coach
    from tests.helpers import coach_seed as S
    with Home() as h:
        S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        facade = SimpleNamespace(session=SimpleNamespace(cwd=h.root), cwd=h.root)
        out = _cmd_coach("", facade)
        ctx.check(f"/coach prints the card, got {out[:120]!r}", out.startswith(f"coach: orchestra run {S.RUN}: 1 suggestion"))
        out = _cmd_coach("--apply tools-1-WebFetch", facade)
        ctx.check(f"/coach --apply is the confirm card, nothing written, got {out[-200:]!r}", "-  - WebFetch" in out
                  and "add --yes to write it" in out
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["WebFetch", "Agent"])
        out = _cmd_coach("--apply tools-1-WebFetch --yes", facade)
        ctx.check(f"--yes writes, got {out[-120:]!r}", "applied a-" in out
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["Agent"])
        out = _cmd_coach("--undo", facade)
        ctx.check(f"/coach --undo, got {out!r}", out.startswith("undid a-"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach summary tests"))
