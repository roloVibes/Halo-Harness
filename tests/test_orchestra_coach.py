"""tests.test_orchestra_coach -- Halo 3.0.9.0 round R3: the post-run coach
(orchestra/coach.py and its coach_*_rules.py, coach_lane_facts.py, coach_prices.py) over
seeded run folders (tests/helpers/coach_seed.py: report.json, events.jsonl,
lanes/<n>.json written by hand), one per rule:

1. an empty run and a clean run yield no suggestion;
2. prompt: a lane sent back twice by the gate, a reply that restates the goal;
3. model: a cheap lane at the return cap beside a dearer lane that finished
   first try; a top-tier lane that finished first try, dear, with a small diff;
4. tools: a denied tool call (into tools.deny / tools.allow), a refused claim;
5. structure: a lane that waited on another's claims, a judged merge
   conflict, a lane that wrote nothing;
6. coordination: a gate that looped three times;
7. a flow, a mission and a team run through their seeds;
then the cache, the CLI verbs and the engine's new evidence: tests/test_orchestra_coach2.py.
Run: python -m tests.test_orchestra_coach
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


class Home:
    """A scratch root with a seeded state dir (BRIDGE_STATE_DIR for this test only, put back after)."""

    def __enter__(self):
        from tests.helpers.coach_seed import seed_home
        self.saved = os.environ.get("BRIDGE_STATE_DIR")
        self.root = Path(tempfile.mkdtemp(prefix="coach-"))
        self.state = self.root / ".state"
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        seed_home(self.state)
        return self

    def coach(self, run_dir):
        from halo_harness.orchestra.coach import coach
        from tests.helpers.coach_seed import CATALOG
        return coach(run_dir, catalog=CATALOG, cwd=self.root, state_dir=self.state)

    def __exit__(self, *a):
        if self.saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self.saved
        shutil.rmtree(self.root, ignore_errors=True)


def _by(result: dict) -> dict:
    return {s["id"]: s for s in result["suggestions"]}


@test
def test_the_empty_run_and_a_clean_run_yield_no_suggestions(ctx: Ctx):
    from halo_harness.orchestra.coach import format_card
    from tests.helpers import coach_seed as S
    with Home() as h:
        empty = h.coach(S.orchestra_run(h.root, []))
        ctx.check(f"no lanes: no suggestion, got {empty['suggestions']}", empty["suggestions"] == [] and empty["kind"] == "orchestra")
        ctx.check("the result's shape", set(empty) == {"run", "kind", "suggestions", "evidence", "model"} and empty["model"] is False)
        clean = h.coach(S.orchestra_run(h.root, [S.lane(1), S.lane(2)], run="20261017-120001-c0a2"))
        ctx.check(f"two clean lanes: no suggestion, got {[s['id'] for s in clean['suggestions']]}", clean["suggestions"] == [])
        ctx.check("the card says so", "nothing to suggest" in format_card(clean))
        ctx.check("the evidence has both lanes", [l["lane"] for l in clean["evidence"]["lanes"]] == [1, 2])


@test
def test_prompt_rule(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h:
        res = _by(h.coach(S.orchestra_run(h.root, [
            S.lane(1, bio="coach-strong", pieces_returned=2, history=S.returned(2), state="merged", model="or:vendor/strong"),
            S.lane(2, written={}, reply="Sure: Write the five functions of basket.py, as asked.", bio="coach-strong")])))
        p = res.get("prompt-1-gate")
        ctx.check(f"lane 1 sent back twice by the gate, got {sorted(res)}", p is not None and p["kind"] == "prompt" and p["severity"] == "medium")
        ctx.check(f"it names the bio and the reason, got {p['text']!r}", "coach-strong" in p["text"] and "tests failed" in p["text"])
        ctx.check(f"apply: the bio's prompt notes, got {p['apply']}", p["apply"]["target"] == "bio" and p["apply"]["name"] == "coach-strong"
                  and p["apply"]["field"] == "context.prompt_notes" and "test command" in p["apply"]["value"])
        ctx.check("why names the returns", any("returned 2 times" in w for w in p["why"]))
        r = res.get("prompt-2-restated")
        ctx.check(f"lane 2 restates the goal with nothing written, got {r}", r is not None and r["apply"]["field"] == "context.prompt_notes")
        ctx.check("and wrote nothing: drop it", "structure-2-drop" in res)


@test
def test_model_rules(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h:
        res = _by(h.coach(S.orchestra_run(h.root, [
            S.lane(1, bio="coach-strong", ended=1050.0),
            S.lane(2, bio="coach-cheap", pieces_returned=2, history=S.returned(2), state="merged"),
            S.lane(3, model="or:vendor/top", cost_usd=0.5)])))
        m = res.get("model-2-stronger")
        ctx.check(f"the cheap lane at the cap gets the sibling's model, got {sorted(res)}", m is not None and m["severity"] == "high")
        ctx.check(f"apply: bio coach-cheap models.preference = or:vendor/strong, got {m['apply']}",
                  m["apply"] == {"target": "bio", "name": "coach-cheap", "field": "models.preference", "value": "or:vendor/strong"})
        ctx.check(f"why: the cap on the cheap model, the first try on the strong one, got {m['why']}",
                  "hit the return cap (2)" in m["why"][0] and "$0.10/M in" in m["why"][0] and "finished first try" in m["why"][1])
        c = res.get("model-3-cheaper")
        ctx.check(f"the dear first-try lane gets a cheaper model, got {c}", c is not None and c["severity"] == "low")
        ctx.check(f"the most capable model under the top tier, into the lineup's role (no bio), got {c['apply']}",
                  c["apply"] == {"target": "lineup", "name": "", "field": "roles.subagent", "value": "or:vendor/strong"})


@test
def test_tools_rule(ctx: Ctx):
    from tests.helpers import coach_seed as S
    denied = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]
    with Home() as h:
        ev = [S.event(1010.0, "claim", "s2/main could not claim basket.py#f1", op="refused", holder="s2/main",
                      key="basket.py#f1", by="s1/main", other="basket.py#f1")]
        res = _by(h.coach(S.orchestra_run(h.root, [
            S.lane(1, bio="coach-deny", denied=denied), S.lane(2, bio="coach-allow", denied=[{"tool_name": "Bash", "reason": "x"}]),
            S.lane(3, denied=denied)], events=ev)))
        t = res.get("tools-1-WebFetch")
        ctx.check(f"a denied call, got {sorted(res)}", t is not None and t["severity"] == "high" and "could not call `WebFetch`" in t["text"])
        ctx.check(f"apply: out of tools.deny, got {t['apply']}", t["apply"] == {"target": "bio", "name": "coach-deny", "field": "tools.deny",
                                                                              "value": ["Agent"]})
        a = res.get("tools-2-Bash")
        ctx.check(f"apply: into tools.allow, got {a and a['apply']}", a["apply"]["field"] == "tools.allow" and a["apply"]["value"] == ["Read", "Edit", "Bash"])
        ctx.check("no bio: the text, no apply", res["tools-3-WebFetch"]["apply"] is None)
        c = res.get("tools-2-claim-basket.py#f1")
        ctx.check(f"a refused claim names the holder's lane, got {c}", c is not None and "lane 1 held" in c["text"] and c["apply"] is None)


@test
def test_structure_rules(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h:
        ev = [S.event(1010.0, "state", "lane 1: s1/main joined", lane=1, holder="s1/main"),
              S.event(1011.0, "state", "lane 2: s2/main joined", lane=2, holder="s2/main"),
              S.event(1020.0, "claim", "refused", op="refused", holder="s2/main", key="basket.py#f2", by="s1/main", other="basket.py"),
              S.event(1090.0, "claim", "s2/main claimed basket.py#f2", op="claim", holder="s2/main", key="basket.py#f2")]
        merge = {"order": [1, 2, 3], "merged": [1, 2, 3], "conflicts": [{"lane": 3, "file": "basket.py", "tests_ok": True}]}
        res = _by(h.coach(S.orchestra_run(h.root, [S.lane(1), S.lane(2), S.lane(3, written={}, state="merged")],
                                          events=ev, merge=merge)))
        w = res.get("structure-2-after-1")
        ctx.check(f"lane 2 waited 70s of 100s on lane 1, got {sorted(res)}", w is not None and "waited 70s of its 100s" in w["why"][0])
        ctx.check(f"apply: the plan's job-2.after, got {w['apply']}", w["apply"] == {"target": "plan", "name": S.RUN,
                                                                                   "field": "job-2.after", "value": ["job-1"]})
        j = res.get("structure-3-after-2")
        ctx.check(f"the judged conflict: lane 3 after lane 2 (the last lane before it in basket.py), got {j}",
                  j is not None and "conflicted in basket.py" in j["why"][0])
        d = res.get("structure-3-drop")
        ctx.check(f"lane 3 wrote nothing, got {d and d['apply']}", d["apply"] == {"target": "plan", "name": S.RUN, "field": "job-3.drop",
                                                                                "value": True} and d["severity"] == "low")


@test
def test_coordination_rule(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h:
        loops = [S.event(1000.0 + i, "gate", f"tests fail on orchestra/{S.RUN}", back=[1]) for i in range(3)]
        res = h.coach(S.orchestra_run(h.root, [S.lane(1)], events=loops))
        c = _by(res).get("coordination-gate-loops")
        ctx.check(f"three loops, got {res['suggestions']}", c is not None and "looped 3 times" in c["text"] and len(c["why"]) == 3
                  and c["apply"] is None)
        two = h.coach(S.orchestra_run(h.root, [S.lane(1)], events=loops[:2], run="20261017-120002-c0a3"))
        ctx.check("two loops are not a finding", two["suggestions"] == [] and two["evidence"]["gate_loops"] == 2)


@test
def test_a_flow_a_mission_and_a_team_run(ctx: Ctx):
    from tests.helpers import coach_seed as S
    with Home() as h:
        f = h.coach(S.flow_run(h.state))
        fb = _by(f)
        ctx.check(f"flow: the gate looped, the render was drawn again, got {sorted(fb)}", f["kind"] == "flow"
                  and "coordination-approve-loops" in fb and "prompt-render-redo" in fb)
        ctx.check("the redo instructions are the why", fb["prompt-render-redo"]["why"] == ["redo 1: make the sky darker",
                                                                                          "redo 2: the logo is too small"])
        m = h.coach(S.mission_folder(h.state))
        mb = _by(m)
        ctx.check(f"mission: asked, refused, conflict, drop, missing outputs, got {sorted(mb)}", m["kind"] == "mission" and {
            "coordination-2-asked", "tools-3-claim-README.md", "structure-3-after-1", "structure-4-drop",
            "prompt-missing-outputs"} == set(mb))
        ctx.check(f"a mission names depends_on and no Apply, got {mb['structure-3-after-1']['text']!r}",
                  "`depends_on: 1`" in mb["structure-3-after-1"]["text"] and all(s["apply"] is None for s in mb.values()))
        ctx.check("asked 200s against a 55s median", "200s" in mb["coordination-2-asked"]["text"]
                  and "median part took 55s" in mb["coordination-2-asked"]["why"][1])
        t = h.coach(S.team_run(h.root))
        tb = _by(t)
        ctx.check(f"team: gated twice, a refused write, got {sorted(tb)}", t["kind"] == "team" and set(tb) == {
            "coordination-copy-loops", "tools-ship-claim-site/index.html"})
        ctx.check("the redo answer is in the why", "redo: shorter" in tb["coordination-copy-loops"]["why"])
        ctx.check("the member who could not write is named", "member editor (stage ship)"
                  in tb["tools-ship-claim-site/index.html"]["text"])


@test
def test_the_rules_live_once_over_the_unit_model(ctx: Ctx):
    """3.1.2.0 R1 moved the Orchestra rules into coach_rules.py; 3.1.3.0 R1
    folded the flow, mission and team rules in: every kind's loader calls
    coach_rules's functions and defines no rule of its own, and each kind's
    seeded run still goes through them."""
    import inspect
    from halo_harness.orchestra import coach_flow_rules, coach_mission_rules, coach_orchestra_rules, coach_team_rules
    from halo_harness.orchestra import coach_rules as R
    from tests.helpers import coach_seed as S
    uses = {coach_orchestra_rules: ("prompt_rules", "model_rules", "tools_rules", "structure_rules", "coordination_rules",
                                    "wait_pairs", "conflict_pairs"),
            coach_flow_rules: ("prompt_rules", "coordination_rules"),
            coach_mission_rules: ("coordination_rules", "tools_rules", "structure_rules", "outputs_rules", "conflict_pairs"),
            coach_team_rules: ("coordination_rules", "tools_rules")}
    for loader, names in uses.items():
        short = loader.__name__.rsplit(".", 1)[1]
        for name in names:
            ctx.check(f"{short} uses coach_rules.{name}", getattr(loader, name) is getattr(R, name))
        src = inspect.getsource(loader)
        ctx.check(f"{short} builds no suggestion itself", "suggestion(" not in src and "import suggestion" not in src)
    with Home() as h:
        orch = h.coach(S.orchestra_run(h.root, [
            S.lane(1, bio="coach-strong", pieces_returned=2, history=S.returned(2), state="merged",
                   model="or:vendor/strong")]))
        ctx.check("the orchestra kind fires the shared prompt rule", any(s["kind"] == "prompt" for s in orch["suggestions"]))
        for maker, kind in ((S.flow_run(h.state), "flow"), (S.mission_folder(h.state), "mission"),
                            (S.team_run(h.root), "team")):
            res = h.coach(maker)
            ctx.check(f"{kind}: a seeded run yields suggestions of the shared shape",
                      res["kind"] == kind and res["suggestions"]
                      and all(set(s) == {"id", "kind", "severity", "lane_or_part", "bio", "text", "why", "apply"}
                              for s in res["suggestions"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="orchestra coach tests"))
