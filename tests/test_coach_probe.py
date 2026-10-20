"""tests.test_coach_probe -- Halo 3.1.6.0 R2: the coach probes (orchestra/coach_probe.py,
probe_runs.py, probe_overlay.py, coach_compare.py, coach_compose.py, coach_probe_card.py),
over a reference run made with the fake lead, workers and judge (tests/helpers/coach_probe_rig.py):

1. the lead's candidates are cleaned to the strict schema (unknown keys, refs that do not
   resolve, a bio not the run's, a job not in the plan, a note over 600 characters dropped);
   k pairs; the fake lead and its error; the cost line;
2. a whole probe: two candidates run as probe runs under the reference (its split and base),
   the overlay reaches the worker's argv and its worktree's project scope, nothing of it is
   committed, no run list shows a probe, the worktrees and branches are gone after;
3. the budget: a lane whose forecast would pass the cap does not start; the probe stops with
   stop_reason budget;
4. the probe's card leads the run's card, Apply writes every file of the overlay with one group
   id, Undo puts them all back (and is refused when a file changed).
The anonymized judge and compose: tests/test_coach_compare.py.
No model is ever called. Run: python -m tests.test_coach_probe
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
NOTE_I, NOTE_D = "Run the goal's tests before you finish.", "Keep each function to its docstring."
PAIR = {"invariant": {"workers": {"prompt_notes": NOTE_I, "max_iterations": 30},
                      "bios": {"coach-cheap": {"model": "or:vendor/strong"}}, "why": "the cheap lane needs a stronger model"},
        "domain": {"bios": {"coach-strong": {"prompt_notes": NOTE_D, "use_for": ["basket"]}},
                   "plan": [{"job": "job-2", "after": ["job-1"]}], "why": "the totals build on the items"}}


def _flag(argv: list, name: str) -> str:
    return argv[argv.index(name) + 1] if name in argv else ""


@test
def test_the_lead_drafts_candidates_cleaned_to_the_schema(ctx: Ctx):
    import os
    from halo_harness.orchestra import coach_probe as CP
    from tests.helpers.coach_probe_rig import Probe, ask
    bad = {"pairs": [{"invariant": {"lead": {"model": "or:vendor/strong", "effort": "huge", "temperature": 1},
                                    "workers": {"model": "nope", "prompt_notes": "x" * 700, "max_iterations": 30,
                                                "tools": {"allow": ["Read", "Edit"], "deny": ["Web Fetch!"]}},
                                    "bios": {"coach-cheap": {"model": "or:vendor/ghost", "prompt_notes": "Run the tests."},
                                             "ghost": {"prompt_notes": "x"}}, "why": "w", "extra": 1},
                      "domain": {"bios": {"coach-strong": {"prompt_notes": "Read the docstrings.", "use_for": ["basket"]}},
                                 "plan": [{"job": "job-2", "after": ["job-1"]}, {"job": "job-9", "after": []}],
                                 "lead": {"model": "or:vendor/top"}}}]}
    with Probe(lineup=True) as p:
        seam = ask(bad)
        got = CP.draft(p.run_dir, 1, ask=seam)
        inv, dom = got["candidates"]
        ctx.check(f"two candidates, one of each kind, got {[c['id'] for c in got['candidates']]}", got["error"] == ""
                  and inv["kind"] == "invariant" and dom["kind"] == "domain" and inv["id"].endswith("-invariant-1")
                  and dom["id"].endswith("-domain-1") and inv["id"].split("-")[0] == dom["id"].split("-")[0])
        ctx.check(f"the invariant overlay keeps what fits, got {inv['overlay']}", inv["overlay"] == {
            "lead": {"model": "or:vendor/strong"}, "workers": {"max_iterations": 30, "tools": {"allow": ["Read", "Edit"]}},
            "bios": {"coach-cheap": {"prompt_notes": "Run the tests."}}, "why": "w"})
        dropped = " | ".join(inv["dropped"])
        for word in ("temperature", "effort", "workers.model", "workers.prompt_notes", "or:vendor/ghost", "ghost", "extra",
                     "deny"):
            ctx.check(f"dropped names {word}, got {dropped}", word in dropped)
        ctx.check(f"the domain overlay, got {dom['overlay']} {dom['dropped']}", dom["overlay"] == {
            "bios": {"coach-strong": {"prompt_notes": "Read the docstrings.", "use_for": ["basket"]}},
            "plan": [{"job": "job-2", "after": ["job-1"]}]} and any("job-9" in d for d in dom["dropped"])
                  and any("domain.lead" in d for d in dom["dropped"]))
        prompt = seam.prompts[0]
        ctx.check("the lead's prompt names the goal, the bios, the jobs and the shape",
                  "Draft 1 pair(s)" in prompt and "WHAT YOU WANT: Write the five functions" in prompt
                  and "coach-cheap" in prompt and "job-2" in prompt and '"pairs"' in prompt)
        four = CP.draft(p.run_dir, 2)
        ctx.check(f"k=2: two pairs from the fake lead, got {[c['id'] for c in four['candidates']]}",
                  [c["pair"] for c in four["candidates"]] == [1, 1, 2, 2] and len({c["id"] for c in four["candidates"]}) == 4
                  and all(c["overlay"].get("workers") for c in four["candidates"]))
        os.environ["HALO_COACH_FAKE"] = "error"
        failed = CP.draft(p.run_dir, 1)
        ctx.check(f"a failed lead is one line, no candidate, got {failed['error']!r}", failed["candidates"] == []
                  and "fake lead failed" in failed["error"])
        os.environ["HALO_COACH_FAKE"] = "1"
        est = CP.estimate(p.run_dir)
        ctx.check(f"the cost line, got {est['line']!r}", est["line"].startswith("probe: 2 runs, up to $0.0150")
                  and est["cap_usd"] == 0.0075 and CP.estimate(p.run_dir, k=2, factor=2)["line"].startswith("probe: 4 runs, up to $0.0400"))


@test
def test_a_whole_probe_runs_two_candidates_under_the_reference(ctx: Ctx):
    from halo_harness.orchestra import coach_probe as CP
    from halo_harness.orchestra.goal import list_runs, resolve_run
    from tests.helpers.coach_probe_rig import Probe, ask
    with Probe(lineup=True) as p:
        CP.ASK = ask({"pairs": [PAIR]})
        data = CP.probe(p.run_dir, rng=random.Random(7))
        ctx.check(f"done, got {data['state']} {data.get('error')}", data["state"] == "done"
                  and {"candidates", "reference", "outcomes", "pick", "why", "ts", "cost"} <= set(data))
        on_disk = json.loads((p.run_dir / "probe.json").read_text(encoding="utf-8"))
        ctx.check("probe.json holds it", on_disk["pick"] == data["pick"] and on_disk["state"] == "done")
        inv, dom = data["candidates"]
        base = json.loads((p.run_dir / "split.json").read_text(encoding="utf-8"))["base"]
        for c in (inv, dom):
            d = p.run_dir / "probes" / c["id"]
            split = json.loads((d / "split.json").read_text(encoding="utf-8"))
            plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
            ctx.check(f"{c['kind']}: the reference's split and base, no lead cost, got {split.get('lead_cost_usd')}",
                      split["base"] == base and split["lead_cost_usd"] == 0.0 and plan["approved"] is True)
            ctx.check(f"{c['kind']}: finished, its report and patch kept, its worktrees gone",
                      data["outcomes"][c["id"]]["status"] == "finished" and (d / "report.json").is_file()
                      and "basket.py" in (d / "deliverable.patch").read_text(encoding="utf-8")
                      and ".halo/" not in (d / "deliverable.patch").read_text(encoding="utf-8") and not (d / "wt").exists())
        jobs = json.loads((p.run_dir / "probes" / inv["id"] / "plan.json").read_text(encoding="utf-8"))["jobs"]
        ctx.check(f"the invariant plan gives lane 1 its bio and the overlay's model, got {jobs[0]}",
                  jobs[0].get("bio") == "coach-cheap" and jobs[0].get("model") == "or:vendor/strong" and "model" not in jobs[1])
        jobs = json.loads((p.run_dir / "probes" / dom["id"] / "plan.json").read_text(encoding="utf-8"))["jobs"]
        ctx.check(f"the domain plan takes the edit, got {jobs[1].get('after')}", jobs[1].get("after") == ["job-1"])
        one = next(r for r in p.log if r["cand"] == inv["id"] and r["lane"] == 1)
        argv = one["argv"]
        ctx.check(f"the worker's argv carries the overlay, got {argv[7:]}", _flag(argv, "--agent") == "coach-cheap"
                  and _flag(argv, "--model") == "or:vendor/strong" and _flag(argv, "--team") == "probe-line"
                  and NOTE_I in _flag(argv, "--append-system-prompt") and _flag(argv, "--max-turns") == "30")
        files = one["files"]
        ctx.check(f"the worktree's project scope, got {sorted(files)}", ".halo/.gitignore" in files
                  and files[".halo/.gitignore"].rstrip().endswith("*") and "or:vendor/strong" in files[".halo/agents/coach-cheap.yaml"]
                  and NOTE_I in files[".halo/agents/coach-cheap.yaml"] and "or:vendor/strong" in files[".halo/teams/probe-line.yaml"])
        two = next(r for r in p.log if r["cand"] == dom["id"] and r["lane"] == 2)
        ctx.check("the domain lane's bio note and use_for words", NOTE_D in two["files"][".halo/agents/coach-strong.yaml"]
                  and "basket" in two["files"][".halo/teams/probe-line.yaml"] and NOTE_D in _flag(two["argv"], "--append-system-prompt"))
        ctx.check(f"no run list shows a probe, got {[r.name for r in list_runs(p.repo)]}", list_runs(p.repo) == [p.run_dir]
                  and resolve_run(p.repo, inv["id"]) is None)
        ctx.check(f"the probes' branches are gone, got {p.git('branch', '--list', 'orchestra/p*')!r}",
                  not any(c["id"] in p.git("branch", "--list") for c in (inv, dom)))
        ctx.check("the probes' worktrees are gone", "probes" not in p.git("worktree", "list").replace("\\", "/"))
        ctx.check(f"each outcome records its cleanup, got {data['outcomes'][inv['id']].get('cleanup')}",
                  len(data["outcomes"][inv["id"]]["cleanup"]["branches"]) == 3)
        ctx.check(f"the cheaper invariant probe ranked first is adopted, got {data['pick']} {data['why']!r}",
                  data["pick"] == "invariant" and data["picked"] == [inv["id"]] and "beat the run on rank" in data["why"]
                  and data["cost"]["runs"] == 0.008)


@test
def test_the_budget_stops_a_lane_that_would_pass_the_cap(ctx: Ctx):
    from halo_harness.orchestra import coach_probe as CP
    from tests.helpers.coach_probe_rig import Probe
    with Probe() as p:
        data = CP.probe(p.run_dir, factor=0.5)
        ctx.check(f"the cap is half the run's cost, got {data['cap_usd']}", data["cap_usd"] == 0.0025)
        for c in data["candidates"]:
            o = data["outcomes"][c["id"]]
            ran = [r for r in p.log if r["cand"] == c["id"]]
            ctx.check(f"{c['kind']}: one lane ran, the other did not start, got {len(ran)} {o['stop_reason']!r}",
                      len(ran) == 1 and o["status"] == "stopped" and o["stop_reason"] == "budget"
                      and "over the probe's cap $0.0025" in o["budget_hit"])
            ctx.check(f"{c['kind']}: its branches are gone", c["id"] not in p.git("branch", "--list"))
        ctx.check(f"a stopped probe wins nothing: kept, got {data['pick']}", data["pick"] == "kept"
                  and all(r["wins"] == [] for r in data["contrast"]))


@test
def test_the_probe_card_applies_every_file_and_undoes_them(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw, user_agents_dir
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_probe as CP
    from halo_harness.orchestra import coach_record as R
    from halo_harness.orchestra.coach import cached, format_card
    from tests.helpers.coach_probe_rig import Probe, ask
    with Probe(lineup=True) as p:
        CP.ASK = ask({"pairs": [PAIR]})
        data = CP.probe(p.run_dir, rng=random.Random(5))
        res = cached(p.run_dir, state_dir=p.state)
        card = res["suggestions"][0]
        ctx.check(f"the probe's card leads, got {card['id']} {card['kind']}", card["id"] == data["card"] and card["kind"] == "probe"
                  and card["severity"] == "high" and res["probe"]["state"] == "done" and res["probe"]["pick"] == "invariant")
        ctx.check(f"its table: the run, then each candidate, the pick marked, got {[r['id'] for r in card['table']]}",
                  [r["id"] for r in card["table"]][0] == "reference" and len(card["table"]) == 3
                  and [r["id"] for r in card["table"] if r.get("picked")] == data["picked"])
        ctx.check(f"the judge's why in the paragraph slot, got {card['paragraph']!r}", str(card["paragraph"]).startswith("Deliverable "))
        fields = {(c["name"], c["field"]) for c in card["apply"]["changes"]}
        ctx.check(f"Apply = the composed overlay, got {sorted(fields)}", card["apply"]["target"] == "overlay" and fields == {
            ("coach-cheap", "context.prompt_notes"), ("coach-cheap", "limits.max_iterations"), ("coach-cheap", "models.preference"),
            ("coach-strong", "context.prompt_notes"), ("coach-strong", "limits.max_iterations")})
        cheap, strong = (user_agents_dir(p.state) / f"{n}.yaml" for n in ("coach-cheap", "coach-strong"))
        before = (R.text_of(cheap), R.text_of(strong))
        prev = CA.preview(res, card["id"], p.run_dir, state_dir=p.state)
        ctx.check(f"the confirm card lists both files, nothing written, got {prev['files']}",
                  [Path(f).name for f in prev["files"]] == ["coach-cheap.yaml", "coach-strong.yaml"]
                  and any("or:vendor/strong" in line and line.startswith("+") for line in prev["diff"])
                  and (R.text_of(cheap), R.text_of(strong)) == before)
        row = CA.apply(res, card["id"], p.run_dir, state_dir=p.state)
        bio = load_agent_bio_raw("coach-cheap", state_dir=p.state)
        ctx.check(f"written through the bio writer, got {bio}", bio["models"]["preference"] == "or:vendor/strong"
                  and NOTE_I in bio["context"]["prompt_notes"] and bio["limits"]["max_iterations"] == 30)
        rows = [r for r in R.applies(p.state) if r.get("group") == row["apply_id"]]
        ctx.check(f"one record row per file under one group, got {len(rows)}", len(rows) == 2 and row["apply_id"].startswith("g-"))
        state = cached(p.run_dir, state_dir=p.state)["suggestions"][0]["applied"]
        ctx.check(f"the card shows Applied with the group id, got {state}", state["state"] == "applied" and state["apply_id"] == row["apply_id"])
        ctx.check(f"the card prints first, got {format_card(res)[:160]!r}", "[high] probe" in format_card(res).splitlines()[2]
                  and "the judge: Deliverable" in format_card(res))
        ok, msg, _ = R.undo(row["apply_id"], p.state)
        ctx.check(f"Undo puts both files back, got {msg!r}", ok and (R.text_of(cheap), R.text_of(strong)) == before
                  and cached(p.run_dir, state_dir=p.state)["suggestions"][0]["applied"]["state"] == "undone")
        again = CA.apply(cached(p.run_dir, state_dir=p.state), card["id"], p.run_dir, state_dir=p.state)
        R.write_exact(strong, R.text_of(strong) + "# a hand edit\n")
        after_cheap = R.text_of(cheap)
        ok, msg, _ = R.undo(again["apply_id"], p.state)
        ctx.check(f"a file changed after the apply: refused, nothing written, got {msg!r}", not ok and "changed after the apply" in msg
                  and R.text_of(cheap) == after_cheap)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach probe tests"))
