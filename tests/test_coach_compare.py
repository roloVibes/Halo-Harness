"""tests.test_coach_compare -- Halo 3.1.6.0 R2: the probe's compare and compose
(orchestra/coach_compare.py, orchestra/coach_compose.py), over a reference run made
with the fake lead, workers and judge (tests/helpers/coach_probe_rig.py):

1. the judge sees the deliverables shuffled and labelled A, B, C with no harness,
   run, bio, model or candidate named; the verdict maps the labels back; a judge
   whose answer cannot be read leaves the ranking to code;
2. compose adopts the judged best when it beat the run on tests or rank within
   1.5x the cost, merges when the invariant and domain candidates won on
   different axes, keeps otherwise; a probe that stopped wins nothing;
3. a merged overlay's Apply writes the lineup (the lead role's model, an
   entry's use_for words), the bios and the run's plan draft, and Undo puts
   them back (the draft it created removed).
No model is ever called. Run: python -m tests.test_coach_compare
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_coach_probe import NOTE_D, NOTE_I, PAIR

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@test
def test_the_judge_sees_shuffled_labels_and_no_harness(ctx: Ctx):
    from halo_harness.orchestra import coach_compare as C
    from halo_harness.orchestra import coach_probe as CP
    from tests.helpers.coach_probe_rig import Probe, ask
    seen = []

    def judge(prompt, model, cwd):
        seen.append(prompt)
        return {"text": '```json\n{"best": "B", "ranking": ["B", "A", "C"], "why": "B is the cleanest change."}\n```',
                "ok": True, "cost_usd": 0.0002}
    with Probe(lineup=True) as p:
        CP.ASK, C.JUDGE = ask({"pairs": [PAIR]}), judge
        data = CP.probe(p.run_dir, rng=random.Random(3))
        prompt, labels = seen[0], data["judge"]["labels"]
        ctx.check("three deliverables, labelled A to C", all(f"Deliverable {L}" in prompt for L in "ABC") and sorted(labels) == ["A", "B", "C"]
                  and "WHAT YOU WANT: Write the five functions" in prompt and "DONE WHEN: the tests pass" in prompt)
        names = [c["id"] for c in data["candidates"]] + [p.run_dir.name, "invariant", "domain", "reference", "probe", "harness",
                                                         "coach-cheap", "coach-strong", "or:vendor", NOTE_I, NOTE_D, "probe-line"]
        ctx.check(f"no harness named in the prompt, found {[n for n in names if n in prompt]}", not [n for n in names if n in prompt])
        ctx.check(f"the verdict maps the labels back, got {data['judge']['ranking']}",
                  data["judge"]["ranking"] == [labels["B"], labels["A"], labels["C"]] and data["judge"]["best"] == labels["B"])
        ctx.check("the prompt is kept beside the probes", (p.run_dir / "probes" / "judge.prompt.txt").read_text(encoding="utf-8") == prompt)
        rows = {"reference": data["reference"], **{k: o["deliverable"] for k, o in data["outcomes"].items()}}
        orders = {tuple(C.judge(data_goal(p), rows, rng=random.Random(s))["labels"].values()) for s in range(6)}
        ctx.check(f"the order is shuffled, got {len(orders)} orders", len(orders) > 1)
        C.JUDGE = lambda prompt, model, cwd: {"text": "I cannot pick one.", "ok": True}
        coded = C.judge(data_goal(p), rows, rng=random.Random(1))
        ctx.check(f"an unreadable answer leaves the ranking to code, got {coded['why']!r}", "ranked by code" in coded["why"]
                  and coded["error"] and coded["best"] == min(rows, key=lambda k: (rows[k]["cost_usd"], k)))


def data_goal(p):
    from halo_harness.orchestra.goal import load_goal
    return load_goal(p.run_dir / "goal.json")


@test
def test_compose_adopts_merges_and_keeps(ctx: Ctx):
    from halo_harness.orchestra.coach_compare import contrast
    from halo_harness.orchestra.coach_compose import compose
    ref = {"cost_usd": 0.01, "passed": 5, "tests_ok": True, "steps": 2}
    cands = [{"id": "i", "kind": "invariant", "overlay": {"workers": {"prompt_notes": "inv note", "max_iterations": 30}}},
             {"id": "d", "kind": "domain", "overlay": {"workers": {"prompt_notes": "dom note"}, "plan": [{"job": "job-2", "after": ["job-1"]}]}}]

    def row(cid, kind, rank, wins, cost):
        return {"id": cid, "kind": kind, "rank": rank, "ref_rank": 2, "wins": wins, "cost_usd": cost, "status": "finished",
                "tests_delta": 1 if "tests" in wins else 0, "tests_by": "passed", "passed": 6, "cost_x": cost / 0.01,
                "steps": 2, "steps_delta": 0}
    got = compose(cands, [row("i", "invariant", 1, ["tests"], 0.012), row("d", "domain", 3, [], 0.01)], ref)
    ctx.check(f"adopt: the judged best beat the run on tests within 1.5x, got {got['pick']}", got["pick"] == "invariant"
              and got["from"] == ["i"] and got["overlay"] == cands[0]["overlay"] and "tests -> " not in got["why"][:10])
    got = compose(cands, [row("i", "invariant", 1, ["tests"], 0.02), row("d", "domain", 3, ["cost"], 0.008)], ref)
    ctx.check(f"merge: 2x the cost is not adopted, two axes merge, got {got['pick']} {got['overlay']}", got["pick"] == "merged"
              and got["from"] == ["i", "d"] and got["overlay"]["workers"]["prompt_notes"] == "inv note\ndom note"
              and got["overlay"]["workers"]["max_iterations"] == 30 and got["overlay"]["plan"] == cands[1]["overlay"]["plan"])
    got = compose(cands, [row("i", "invariant", 2, [], 0.02), row("d", "domain", 3, [], 0.01)], ref)
    ctx.check(f"keep: nothing won, got {got['pick']}", got["pick"] == "kept" and got["overlay"] == {} and "kept" in got["why"])
    got = compose(cands, [row("i", "invariant", 1, ["cost"], 0.005), row("d", "domain", 3, ["cost"], 0.006)], ref)
    ctx.check(f"keep: the same axis twice does not merge, got {got['pick']}", got["pick"] == "kept")
    stopped = {"i": {"id": "i", "kind": "invariant", "status": "stopped", "deliverable": {
        "status": "stopped", "tests_ok": True, "passed": 6, "cost_usd": 0.001, "steps": 1}}}
    rows = contrast(ref, stopped, {"ranking": ["i", "reference"]})
    ctx.check(f"a probe that stopped wins nothing, got {rows[0]['wins']}", rows[0]["wins"] == [] and rows[0]["rank"] == 1)


@test
def test_a_merged_overlay_writes_the_lineup_and_the_plan_and_undoes(ctx: Ctx):
    from halo_harness.orchestra import coach_probe_card as PC
    from halo_harness.orchestra import coach_record as R
    from halo_harness.orchestra.coach_compose import changes
    from halo_harness.orchestra.coach_probe_schema import facts, merge
    from halo_harness.teams_yaml import load_team_template_raw, user_teams_dir
    from tests.helpers.coach_probe_rig import Probe
    with Probe(lineup=True) as p:
        overlay = merge(dict(PAIR["invariant"], lead={"model": "or:vendor/top", "effort": "high"}), PAIR["domain"])
        ch, skipped = changes(overlay, facts(p.run_dir, state_dir=p.state))
        where = sorted({(c["target"], c["name"], c["field"]) for c in ch})
        ctx.check(f"the writes, got {where} {skipped}", ("lineup", "probe-line", "roles.main") in where
                  and ("bio", "coach-strong", "models.effort") in where and ("lineup", "probe-line", "agents.coach-strong.use_for") in where
                  and ("plan", p.run_dir.name, "job-2.after") in where and ("bio", "coach-strong", "context.prompt_notes") in where)
        lineup = user_teams_dir(p.state) / "probe-line.yaml"
        before = R.text_of(lineup)
        s = {"id": "probe-1", "kind": "probe", "apply": {"target": "overlay", "name": "merged", "field": "overlay", "changes": ch}}
        row = PC.apply({"run": p.run_dir.name, "kind": "orchestra"}, s, p.run_dir, state_dir=p.state)
        raw = load_team_template_raw("probe-line", state_dir=p.state)
        main = next(e for e in raw["agents"] if e["role"] == "main")
        draft = json.loads((p.run_dir / "plan.draft.json").read_text(encoding="utf-8"))["jobs"]
        ctx.check(f"the lineup's lead model and use_for, the plan draft, got {main} {draft[1].get('after')}",
                  main["models"]["preference"] == "or:vendor/top" and main.get("use_for") == ["basket"]
                  and draft[1]["after"] == ["job-1"] and len(row["files"]) == 4)
        ok, msg, _ = R.undo(row["apply_id"], p.state)
        ctx.check(f"Undo: the lineup back, the plan draft gone, got {msg!r}", ok and R.text_of(lineup) == before
                  and not (p.run_dir / "plan.draft.json").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach compare tests"))
