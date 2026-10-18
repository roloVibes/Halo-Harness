"""tests.test_orchestra_forecast -- Halo 3.1.2.0 round R2: the cost forecast
of an Orchestra plan (orchestra/forecast.py, work/forecast.py): the lead's
`est_tokens` (the split prompt asks for it), the stated heuristic when a job
has none, the catalog price (in and out, the band, free and unlisted
models), the total against the goal's `budget_usd`, forecast.json, `GET
orchestra/<run>/forecast` and the plan payload, Approve's warning (it still
approves), and `halo orchestra plan`'s Cost column and total line. No model
is called: the lead is the fixture's fake, the catalog rows are given.

Run: python -m tests.test_orchestra_forecast
"""
from __future__ import annotations

import io
import json
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import orchestra_fixtures as F  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ROWS = [{"ref": "or:vendor/mid", "provider": "openrouter", "price_in_per_m": 1.0, "price_out_per_m": 4.0},
        {"ref": "or:vendor/in-only", "provider": "openrouter", "price_in_per_m": 2.0},
        {"ref": "ollama:qwen", "provider": "ollama", "price_in_per_m": None}]
# models.json as OpenRouter writes it (per-token prices) plus the per-million field the catalog's own rows read
MODELS = {"vendor/mid": {"price_in_per_m": 1.0, "pricing": {"prompt": "0.000001", "completion": "0.000004"}}}


def _answer() -> str:
    data = json.loads(F.split_answer([[f] for f in F.FUNCS]))
    data["jobs"][0]["est_tokens"] = {"in": 30000, "out": 5000}
    data["jobs"][1]["est_tokens"] = 10000
    return json.dumps(data)


@test
def test_the_leads_estimate_and_the_heuristic_fallback(ctx: Ctx):
    from halo_harness.orchestra import forecast as FC
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.index import index_file
    from halo_harness.orchestra.split import load_split, split_goal
    repo = F.make_repo("orch-forecast-")
    run_dir = F.make_run(repo)
    goal = load_goal(run_dir / "goal.json")
    lead = F.FakeLead(_answer())
    split_goal(run_dir, goal, index_file(repo / "basket.py", root=repo), call_model=lead, base="HEAD")
    ctx.check("the split prompt asks for est_tokens in one sentence", lead.prompts[0].count('"est_tokens"') == 1)
    jobs = load_split(run_dir)["jobs"]
    ctx.check(f"split.json keeps the lead's estimates, got {[j.get('est_tokens') for j in jobs]}",
              jobs[0]["est_tokens"] == {"in": 30000, "out": 5000} and jobs[1]["est_tokens"] == {"in": 8000, "out": 2000}
              and "est_tokens" not in jobs[2])
    out = FC.write(run_dir, rows=ROWS)
    lanes = out["lanes"]
    ctx.check(f"lanes 1 and 2 come from the lead, got {[(x['source'], x['tokens_in'], x['tokens_out']) for x in lanes[:2]]}",
              (lanes[0]["source"], lanes[0]["tokens_in"], lanes[0]["tokens_out"]) == ("lead", 30000, 5000)
              and (lanes[1]["tokens_in"], lanes[1]["tokens_out"]) == (8000, 2000))
    size = (repo / "basket.py").stat().st_size
    text = (repo / "basket.py").read_text(encoding="utf-8").split("\n")
    unit = next(u for u in index_file(repo / "basket.py", root=repo) if u.key == "basket.py#subtotal")
    unit_bytes = sum(len(x) + 1 for x in text[unit.start_line - 1:unit.end_line])
    chars = sum(len(getattr(goal, k)) for k in ("what", "done_when", "stop_when"))
    want = (6000 + chars // 4 + 3 * size // 4, 800 + 3 * unit_bytes // 4)
    ctx.check(f"lane 3 falls back to the stated heuristic, got {(lanes[2]['tokens_in'], lanes[2]['tokens_out'])} want {want}",
              lanes[2]["source"] == "heuristic" and (lanes[2]["tokens_in"], lanes[2]["tokens_out"]) == want
              and "tokens_in = 6000" in out["heuristic"])
    ctx.check("forecast.json is beside split.json", json.loads((run_dir / "forecast.json").read_text(encoding="utf-8"))["lanes"]
              == lanes and FC.read(run_dir)["run_id"] == run_dir.name)


@test
def test_the_catalog_price_the_band_and_the_total(ctx: Ctx):
    from halo_harness.orchestra import forecast as FC
    from halo_harness.work import forecast as W
    x = W.line("job-1", "or:vendor/mid", 100000, 10000, "heuristic", ROWS)
    ctx.check(f"in at $1/M, out at $4/M, the heuristic's band, got {x}", x["usd"] == 0.14 and x["usd_low"] == 0.07
              and x["usd_high"] == 0.28 and x["priced"])
    lead = W.line("job-2", "or:vendor/in-only", 100000, 10000, "lead", ROWS)
    ctx.check(f"no out price: 4 x the in price; the lead's band, got {lead}", lead["usd"] == 0.28
              and lead["usd_low"] == round(0.28 * 0.8, 6) and lead["usd_high"] == round(0.28 * 1.5, 6))
    free = W.line("job-3", "ollama:qwen", 100000, 10000, "heuristic", ROWS)
    gone = W.line("job-4", "or:vendor/unknown", 100000, 10000, "heuristic", ROWS)
    ctx.check("a local model costs 0; an unlisted one is unpriced", free["usd"] == 0.0 and free["priced"]
              and gone["usd"] is None and not gone["priced"])
    t = W.total([x, lead, free, gone], 0.5)
    ctx.check(f"the total, against the budget, got {t}", t["usd"] == 0.42 and t["usd_high"] == 0.7 and t["over"]
              and t["unpriced"] == 1 and t["budget_usd"] == 0.5 and W.total([x], 1.0)["over"] is False)
    ctx.check(f"the words, got {W.words(t)!r}", W.words(t) == "forecast $0.294-$0.70 (+1 unpriced) against a budget of $0.50: over"
              and W.words(W.total([x])) == "forecast $0.07-$0.28, no budget set")
    repo = F.make_repo("orch-forecast-goal-")
    got = FC.for_goal({"what": "w", "done_when": "d", "stop_when": "s", "workers": 2, "files": ["basket.py"],
                       "budget_usd": 0.01}, repo, rows=ROWS)
    ctx.check(f"a goal before any split: workers lanes, the files shared, got {[x['job'] for x in got['lanes']]}",
              [x["job"] for x in got["lanes"]] == ["job-1", "job-2"] and got["total"]["budget_usd"] == 0.01)


def _review_run(budget: float):
    from halo_harness.orchestra import goal as G
    from halo_harness.orchestra.plan import is_planned
    from halo_harness.orchestra.run import run
    repo = F.make_repo("orch-forecast-review-")
    run_dir = F.make_run(repo)
    goal = G.load_goal(run_dir / "goal.json")
    goal.plan, goal.budget_usd = "review", budget
    G.save_goal(goal, run_dir / "goal.json")
    out = {}
    t = threading.Thread(target=lambda: out.update(report=run(run_dir, model_calls=F.FakeLead(_answer()), spawn=F.FakeWorker(),
                                                                judge=F.FakeJudge(), plan_poll_s=0.05)), daemon=True)
    t.start()
    end = time.monotonic() + 20
    while time.monotonic() < end and not is_planned(run_dir):
        time.sleep(0.05)
    return repo, run_dir, t, out


def _cli(argv):
    from halo_harness.orchestra_cli import cmd_orchestra
    o, e = io.StringIO(), io.StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        rc = cmd_orchestra(argv)
    return rc, o.getvalue(), e.getvalue()


@test
def test_the_route_the_cli_column_and_approve_warns(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from tests.helpers.orchestra_studio_rig import Studio, cleanup
    repo, run_dir, t, out = _review_run(0.0001)
    try:
        bridge_home().mkdir(parents=True, exist_ok=True)
        (bridge_home() / "models.json").write_text(json.dumps(MODELS), encoding="utf-8")
        draft = json.loads((run_dir / "split.json").read_text(encoding="utf-8"))["jobs"]
        draft = [dict(j, model="or:vendor/mid") for j in draft]
        from halo_harness.orchestra.plan import write_draft
        write_draft(run_dir, draft)
        rc, text, _ = _cli(["plan", "--repo", str(repo)])
        head = next(line for line in text.splitlines() if line.startswith("job "))
        row = next(line for line in text.splitlines() if line.startswith("job-1 "))
        ctx.check(f"`plan` has a Cost column and the total line, got {text!r}", rc == 0 and " cost " in head
                  and "$" in row and "cost: forecast $" in text and "against a budget of $0.0001: over" in text)
        with Studio(repo) as studio:
            (studio.state / "models.json").write_text(json.dumps(MODELS), encoding="utf-8")
            st, body = studio.get(f"orchestra/{run_dir.name}/forecast")
            ctx.check(f"GET forecast: a line per lane and the total vs the budget, got {st} {body.get('total')}",
                      st == 200 and len(body["lanes"]) == 5 and body["total"]["over"] is True
                      and body["total"]["budget_usd"] == 0.0001 and all(x["priced"] for x in body["lanes"]))
            st, plan = studio.get(f"orchestra/{run_dir.name}/plan")
            ctx.check("the plan payload carries the forecast", st == 200 and plan["forecast"]["total"]["over"] is True
                      and plan["forecast"]["lanes"][0]["source"] == "lead")
            st, put = studio.call("PUT", f"orchestra/{run_dir.name}/plan", {"jobs": draft[:2]})
            ctx.check("a PUT answers the edited plan's forecast", st == 200 and len(put["forecast"]["lanes"]) == 2)
            st, ok = studio.post(f"orchestra/{run_dir.name}/approve", {"jobs": draft})
            ctx.check(f"Approve warns over the budget and approves all the same, got {st} {ok.get('warning')!r}",
                      st == 200 and ok["ok"] and "over" in ok["warning"] and "Approve runs it anyway" in ok["warning"])
            t.join(90)
        ctx.check(f"the run took the plan and finished, got {(out.get('report') or {}).get('status')}",
                  (out.get("report") or {}).get("status") == "finished")
    finally:
        cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="orchestra forecast tests"))
