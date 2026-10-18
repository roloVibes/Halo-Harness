"""tests.test_coach_ask -- Halo 3.1.3.0 R1: "Ask the model" on a coach card
(orchestra/coach_ask.py) over seeded run folders (tests/helpers/coach_seed.py).
No model is called: the `ASK` seam and `HALO_COACH_FAKE` stand in for it.

1. one paragraph per card, kept in <run>/coach.ask.json; a second ask reads it
   back without a call, refresh asks again; the prompt carries the card, its
   why lines and the run's evidence; the overlay puts `paragraph` on the card;
2. a model error is one line on that card, never a crash, and the next ask
   tries again;
3. the lead is the run's lineup lead (the lineup's role entry, its bio's model);
4. `halo coach <run> --model [--json]` and HALO_COACH_FAKE.
Run: python -m tests.test_coach_ask
"""
from __future__ import annotations

import io
import json
import os
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


class Seam:
    """coach_ask.ASK set to `fn` (recording each prompt) and HALO_COACH_FAKE put back after."""

    def __init__(self, fn=None, fake=None):
        self.fn, self.fake, self.prompts = fn, fake, []

    def __enter__(self):
        from halo_harness.orchestra import coach_ask
        self.saved, self.env = coach_ask.ASK, os.environ.get("HALO_COACH_FAKE")
        if self.fn is not None:
            coach_ask.ASK = lambda prompt, model, cwd: (self.prompts.append((prompt, model)), self.fn(prompt))[1]
        if self.fake is not None:
            os.environ["HALO_COACH_FAKE"] = self.fake
        return self

    def __exit__(self, *a):
        from halo_harness.orchestra import coach_ask
        coach_ask.ASK = self.saved
        if self.env is None:
            os.environ.pop("HALO_COACH_FAKE", None)
        else:
            os.environ["HALO_COACH_FAKE"] = self.env


def _cli(argv):
    from halo_harness.coach_cli import cmd_coach
    o, e = io.StringIO(), io.StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        rc = cmd_coach(argv)
    return rc, o.getvalue(), e.getvalue()


def _run(h):
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
    return run, cached(run, catalog=S.CATALOG, state_dir=h.state)


@test
def test_one_paragraph_per_card_kept_with_the_run(ctx: Ctx):
    from halo_harness.orchestra.coach import cached, format_card
    from halo_harness.orchestra.coach_ask import STORE, ask
    from tests.helpers import coach_seed as S
    with Home() as h, Seam(lambda p: {"text": "The worker needed WebFetch.\n\nA second paragraph.", "ok": True,
                                      "cost_usd": 0.001}) as seam:
        run, result = _run(h)
        r = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check(f"one paragraph, the first, got {r}", r["paragraph"] == "The worker needed WebFetch." and r["error"] == ""
                  and r["cached"] is False and len(seam.prompts) == 1)
        prompt = seam.prompts[0][0]
        ctx.check("the prompt carries the card, its why and the evidence", "could not call `WebFetch`" in prompt
                  and "- lane 1: WebFetch denied 1 time(s)" in prompt and '"lanes"' in prompt and "ONE paragraph" in prompt)
        kept = json.loads((run / STORE).read_text(encoding="utf-8"))
        ctx.check(f"kept in {STORE}, got {kept}", kept["tools-1-WebFetch"]["paragraph"] == "The worker needed WebFetch.")
        again = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check("a second ask reads it back with no call", again["cached"] is True and len(seam.prompts) == 1)
        ask(run, result, "tools-1-WebFetch", refresh=True, state_dir=h.state)
        ctx.check("refresh asks again", len(seam.prompts) == 2)
        card = cached(run, catalog=S.CATALOG, state_dir=h.state)
        ctx.check(f"the overlay puts the paragraph on the card, got {card['suggestions'][0].get('paragraph')}",
                  card["suggestions"][0]["paragraph"] == "The worker needed WebFetch." and card["model"] is True)
        ctx.check("the card's text shows it", "  the lead: The worker needed WebFetch." in format_card(card))
        miss = ask(run, result, "nope", state_dir=h.state)
        ctx.check(f"an unknown id is one error line, got {miss}", miss["paragraph"] == "" and "no suggestion 'nope'" in miss["error"])


@test
def test_a_model_error_is_one_line_on_that_card(ctx: Ctx):
    from halo_harness.orchestra.coach import cached, format_card
    from halo_harness.orchestra.coach_ask import ask

    def boom(prompt):
        raise RuntimeError("provider answered 503\nwith a long body")
    with Home() as h:
        run, result = _run(h)
        with Seam(boom):
            r = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check(f"one line, no crash, got {r}", r["paragraph"] == "" and r["error"] == "RuntimeError: provider answered 503")
        from tests.helpers import coach_seed as S
        card = cached(run, catalog=S.CATALOG, state_dir=h.state)
        ctx.check("the card says the lead could not answer", "the lead could not answer: RuntimeError: provider answered 503"
                  in format_card(card) and card["suggestions"][0]["paragraph"] is None and card["model"] is False)
        with Seam(lambda p: {"text": "", "ok": False, "error": "no credits left"}):
            r = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check(f"a failed result is its error, got {r}", r["error"] == "no credits left")
        with Seam(lambda p: {"text": "Now it answers.", "ok": True}) as seam:
            r = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check("an error is asked again next time", r["paragraph"] == "Now it answers." and len(seam.prompts) == 1)


@test
def test_the_lead_is_the_run_s_lineup_lead(ctx: Ctx):
    from halo_harness.orchestra.coach_ask import ask, lead_of
    from halo_harness.teams_yaml import save_team_template
    from tests.helpers import coach_seed as S
    with Home() as h:
        ok, problems = save_team_template("coach-line", {"description": "x", "agents": [
            {"agent": "coach-strong", "role": "main"}, {"agent": "coach-cheap", "role": "subagent"}]}, state_dir=h.state)
        ctx.check(f"the lineup saved, got {problems}", ok)
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)], goal={"lineup": "coach-line"})
        ctx.check(f"the lead role's bio model, got {lead_of(run, 'orchestra', state_dir=h.state)}",
                  lead_of(run, "orchestra", state_dir=h.state) == ("main", "or:vendor/strong"))
        flow = S.flow_run(h.state)
        ctx.check("a flow asks the main role", lead_of(flow, "flow", state_dir=h.state)[0] == "main")
        from halo_harness.orchestra.coach import cached
        result = cached(run, catalog=S.CATALOG, state_dir=h.state)
        with Seam(lambda p: {"text": "ok", "ok": True}) as seam:
            r = ask(run, result, "tools-1-WebFetch", state_dir=h.state)
        ctx.check(f"the call goes to the lead's model, got {seam.prompts[0][1]} / {r.get('model')}",
                  seam.prompts[0][1] == "or:vendor/strong" and r["model"] == "or:vendor/strong" and r["role"] == "main")


@test
def test_halo_coach_model_and_the_fake_lead(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h, Seam(fake="1"):
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        rc, out, err = _cli([str(run), "--model"])
        ctx.check(f"the card with the lead's paragraph, got {rc} {out[-300:]!r} {err!r}", rc == 0
                  and "  the lead: The fake lead on" in out and "could not call `WebFetch`" in out)
        rc, out, _ = _cli([str(run), "--json"])
        s = json.loads(out)["suggestions"][0]
        ctx.check(f"--json carries paragraph per suggestion, got {s.get('paragraph')!r}", rc == 0
                  and s["paragraph"].startswith("The fake lead on") and "applied" in s)
        os.environ["HALO_COACH_FAKE"] = "error"
        rc, out, _ = _cli([str(run), "--model", "--refresh"])
        ctx.check(f"a failed lead is one line, exit 0, got {rc} {out[-200:]!r}", rc == 0
                  and "the lead could not answer: the fake lead failed" in out)
        rc, out, err = _cli(["nope-run", "--repo", str(h.root)])
        ctx.check(f"an unknown run exits 1, got {rc} {err!r}", rc == 1 and "no run 'nope-run'" in err)
        rc, out, _ = _cli(["--help"])
        ctx.check("--help names the flags", rc == 0 and all(f in out for f in ("--model", "--refresh", "--apply", "--undo", "--yes")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach ask tests"))
