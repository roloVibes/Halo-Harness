"""tests.test_coach_apply -- Halo 3.1.3.0 R1: a coach card's Apply writes after
one confirm, with Undo (orchestra/coach_apply.py, orchestra/coach_record.py),
over seeded run folders in a scratch home (tests/helpers/coach_seed.py):

1. a bio field: the preview (file, before -> after diff) writes nothing; Apply
   writes through agents_yaml.save_agent_bio and records {apply_id, id, run,
   file, before, after, ts}; the card shows Applied; Undo restores the text;
2. Undo is refused when the file changed after the apply (and when undone);
3. a plan field: the run's plan draft (orchestra.plan.write_draft) is created,
   and Undo removes it; a lineup role's model through save_team_template;
4. `halo coach <run> --apply ID`: y/N (no answer writes nothing), --yes, --json,
   `halo coach --undo [ID]`.
Run: python -m tests.test_coach_apply
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
DENIED = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]


def _card(h, run):
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    return cached(run, catalog=S.CATALOG, state_dir=h.state)


def _cli(argv, stdin: str = ""):
    from halo_harness.coach_cli import cmd_coach
    o, e = io.StringIO(), io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(o), redirect_stderr(e):
            rc = cmd_coach(argv)
    finally:
        sys.stdin = saved
    return rc, o.getvalue(), e.getvalue()


@test
def test_a_bio_apply_previews_writes_records_and_undoes(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw, user_agents_dir
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_record as R
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        bio = user_agents_dir(h.state) / "coach-deny.yaml"
        start = R.text_of(bio)
        p = CA.preview(_card(h, run), "tools-1-WebFetch", run, state_dir=h.state)
        ctx.check(f"the confirm card names the file and the diff, got {p['file']} {p['diff']}", Path(p["file"]) == bio
                  and p["exists"] and "-  - WebFetch" in p["diff"] and any(d.startswith("@@") for d in p["diff"]))
        ctx.check("the preview wrote nothing", R.text_of(bio) == start and not (h.state / "coach" / R.APPLIED).exists())
        row = CA.apply(_card(h, run), "tools-1-WebFetch", run, state_dir=h.state)
        ctx.check(f"written through the bio writer, got {load_agent_bio_raw('coach-deny', state_dir=h.state)['tools']}",
                  load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["Agent"])
        ctx.check("the confirm card's after is what the writer wrote",
                  p["after"].replace("\r\n", "\n") == R.text_of(bio).replace("\r\n", "\n"))
        rec = json.loads((h.state / "coach" / R.APPLIED).read_text(encoding="utf-8").splitlines()[0])
        ctx.check(f"the record's shape, got {sorted(rec)}", {"op", "apply_id", "id", "run", "run_dir", "kind", "target", "name",
                  "field", "value", "file", "existed", "before", "after", "ts"} <= set(rec) and rec["before"] == start
                  and rec["after"] == R.text_of(bio) and rec["id"] == "tools-1-WebFetch" and rec["run"] == S.RUN)
        s = _card(h, run)["suggestions"][0]
        ctx.check(f"the card shows Applied, got {s['applied']}", s["applied"]["state"] == "applied"
                  and s["applied"]["apply_id"] == row["apply_id"])
        ok, msg, _ = R.undo(row["apply_id"], h.state)
        ctx.check(f"undo restores the before text, got {ok} {msg!r}", ok and R.text_of(bio) == start)
        ctx.check("the card shows Undone", _card(h, run)["suggestions"][0]["applied"]["state"] == "undone")
        ok, msg, _ = R.undo(row["apply_id"], h.state)
        ctx.check(f"a second undo is refused, got {msg!r}", not ok and "already undone" in msg)
        ok, msg, _ = R.undo(None, h.state)
        ctx.check(f"nothing left to undo, got {msg!r}", not ok and "nothing to undo" in msg)


@test
def test_undo_is_refused_when_the_file_changed(ctx: Ctx):
    from halo_harness.agents_yaml import user_agents_dir
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_record as R
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-strong", pieces_returned=2, history=S.returned(2),
                                              model="or:vendor/strong")])
        row = CA.apply(_card(h, run), "prompt-1-gate", run, state_dir=h.state)
        bio = user_agents_dir(h.state) / "coach-strong.yaml"
        ctx.check("the prompt note is in the bio", "run the goal's test command" in R.text_of(bio))
        R.write_exact(bio, R.text_of(bio) + "# a hand edit\n")
        ok, msg, _ = R.undo(row["apply_id"], h.state)
        ctx.check(f"refused with the reason, nothing written, got {msg!r}", not ok and "changed after the apply" in msg
                  and R.text_of(bio).endswith("# a hand edit\n"))
        try:
            CA.preview(_card(h, run), "nope", run, state_dir=h.state)
            ctx.check("an unknown id raises", False)
        except CA.ApplyError as e:
            ctx.check(f"an unknown id names the card's ids, got {e}", "prompt-1-gate" in str(e))


@test
def test_a_plan_apply_and_a_lineup_apply(ctx: Ctx):
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_record as R
    from halo_harness.orchestra import plan as P
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template
    from tests.helpers import coach_seed as S
    with Home() as h:
        ok, problems = save_team_template("coach-line", {"description": "x", "agents": [
            {"agent": "coach-strong", "role": "main"}, {"agent": "coach-cheap", "role": "subagent"}]}, state_dir=h.state)
        ctx.check(f"the lineup saved, got {problems}", ok)
        run = S.orchestra_run(h.root, [S.lane(1), S.lane(2), S.lane(3, model="or:vendor/top", cost_usd=0.5, written={},
                                                                     state="merged")], goal={"lineup": "coach-line"})
        card = _card(h, run)
        ids = [s["id"] for s in card["suggestions"]]
        ctx.check(f"a drop card and a cheaper-model card, got {ids}", "structure-3-drop" in ids)
        row = CA.apply(card, "structure-3-drop", run, state_dir=h.state)
        ctx.check(f"the plan draft is written, got {[j['id'] for j in P.read_draft(run) or []]}",
                  [j["id"] for j in P.read_draft(run)] == ["job-1", "job-2"] and row["existed"] is False)
        ok, msg, _ = R.undo(row["apply_id"], h.state)
        ctx.check(f"undo removes the draft the apply created, got {msg!r}", ok and not (run / P.DRAFT).exists())
        line = {"id": "x-lineup", "kind": "model", "severity": "low", "lane_or_part": 3, "bio": "", "text": "t", "why": [],
                "apply": {"target": "lineup", "name": "coach-line", "field": "roles.subagent", "value": "or:vendor/mid"}}
        row = CA.apply(dict(card, suggestions=[line]), "x-lineup", run, state_dir=h.state)
        raw = load_team_template_raw("coach-line", state_dir=h.state)
        sub = next(e for e in raw["agents"] if e.get("role") == "subagent")
        ctx.check(f"the role's model through the lineup writer, got {sub}", sub["models"]["preference"] == "or:vendor/mid")
        ok, _, _ = R.undo(row["apply_id"], h.state)
        sub = next(e for e in load_team_template_raw("coach-line", state_dir=h.state)["agents"] if e.get("role") == "subagent")
        ctx.check("undo puts the lineup back", ok and "models" not in sub)
        bad = dict(line, apply=dict(line["apply"], field="roles.judge"))
        try:
            CA.preview(dict(card, suggestions=[bad]), "x-lineup", run, state_dir=h.state)
            ctx.check("a missing role raises", False)
        except CA.ApplyError as e:
            ctx.check(f"a missing role is the reason, got {e}", "has no judge role" in str(e))


@test
def test_halo_coach_apply_asks_y_n_and_undo(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        rc, out, _ = _cli([str(run), "--apply", "tools-1-WebFetch"], stdin="n\n")
        ctx.check(f"the confirm card, then no: nothing written, got {rc} {out!r}", rc == 0 and "file: " in out
                  and "-  - WebFetch" in out and "Apply this change? [y/N]" in out and "nothing written" in out
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["WebFetch", "Agent"])
        rc, out, _ = _cli([str(run), "--apply", "tools-1-WebFetch", "--json"])
        ctx.check("--json without --yes is the preview", rc == 0 and json.loads(out)["applied"] is None)
        rc, out, _ = _cli([str(run), "--apply", "tools-1-WebFetch"], stdin="y\n")
        ctx.check(f"y writes it, got {rc} {out[-160:]!r}", rc == 0 and "applied a-" in out and "halo coach --undo a-" in out
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["Agent"])
        rc, out, _ = _cli([str(run)])
        ctx.check("the card says applied", "  applied: a-" in out)
        rc, out, _ = _cli(["--undo"])
        ctx.check(f"--undo puts it back, got {rc} {out!r}", rc == 0 and "undid a-" in out
                  and load_agent_bio_raw("coach-deny", state_dir=h.state)["tools"]["deny"] == ["WebFetch", "Agent"])
        rc, out, err = _cli(["--undo"])
        ctx.check(f"nothing left: exit 1, got {rc} {err!r}", rc == 1 and "nothing to undo" in err)
        rc, out, _ = _cli([str(run), "--apply", "tools-1-WebFetch", "--yes", "--json"])
        ctx.check("--yes --json writes and prints the record", rc == 0 and json.loads(out)["applied"]["apply_id"].startswith("a-"))
        rc, _, err = _cli([str(run), "--apply", "nope", "--yes"])
        ctx.check(f"an unknown id exits 1, got {rc} {err!r}", rc == 1 and "no suggestion 'nope'" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach apply tests"))
