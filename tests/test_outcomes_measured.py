"""tests.test_outcomes_measured -- measured success per model and task kind
(Halo 3.1.8.0 R3, outcomes/measured.py):

1. the rates: checked `passed | returned | failed` tasks only, first-time
   success (`passed / n`), the newest row per task, no `auto` / `default` /
   empty model, the mean cost;
2. `halo models --measured` prints one row per model and kind (and marks a
   kind under 3 tasks as not routed on); `--json` gives the rows;
3. a catalog row's `measured.outcomes` carries them, the best-at line says
   "measured: code 4/5" from 3 checked tasks, a new outcome row makes the
   best-at cache stale, and `halo models analyze` lists the table;
4. the roster's model line gains the measured words.
Fixture caches only, no model call. Run: python -m tests.test_outcomes_measured
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def seed_outcomes(state_dir, model: str, kind: str, outcomes: list, *, check: str = "gate", run: str = "r", cost: float = 0.01):
    """One row per outcome word for `model` and `kind` (each its own task)."""
    from halo_harness.outcomes.records import append, make_row
    rows = [make_row(run=run, task=f"{model}-{kind}-{i}", source="orchestra", bio="b", model=model, kind=kind,
                     outcome=o, check=check, cost_usd=cost, ts=1760000000.0 + i) for i, o in enumerate(outcomes)]
    return append(rows, state_dir)


@test
def test_the_rates_count_checked_tasks_first_time(ctx: Ctx):
    from halo_harness.outcomes.measured import by_model, row_words, success_by_model_kind, words
    from halo_harness.outcomes.records import append, make_row
    with R.home() as state:
        seed_outcomes(state, "or:v/a", "code", ["passed", "passed", "passed", "passed", "failed"], cost=0.02)
        seed_outcomes(state, "or:v/a", "research", ["passed", "returned"])
        seed_outcomes(state, "or:v/b", "code", ["returned", "failed", "passed"])
        seed_outcomes(state, "or:v/b", "code", ["passed", "passed"], check="", run="unchecked")   # nothing checked them
        seed_outcomes(state, "or:v/b", "code", ["stopped", "done"], run="nv")                   # no verdict
        seed_outcomes(state, "auto", "code", ["passed"] * 3, run="lit")                         # not a model
        append([make_row(run="r", task="or:v/b-code-2", source="orchestra", model="or:v/b", kind="code",
                         outcome="failed", check="gate", cost_usd=0.01, ts=1760009999.0)], state)  # that task again: newest wins
        stats = success_by_model_kind(state)
        mine = by_model(state)
    a, b = stats.get(("or:v/a", "code")), stats.get(("or:v/b", "code"))
    ctx.check(f"or:v/a code: 4 of 5 first time, the mean cost, got {a}",
              a == {"n": 5, "passed": 4, "returned": 0, "failed": 1, "rate": 0.8, "cost_mean": 0.02})
    ctx.check(f"or:v/b code: returned is not a first-time pass, the newest row per task, got {b}",
              b == {"n": 3, "passed": 0, "returned": 1, "failed": 2, "rate": 0.0, "cost_mean": 0.01})
    ctx.check("no row for a literal model", not any(m == "auto" for m, _k in stats))
    ctx.check(f"by model, got {mine.get('or:v/a')}", mine["or:v/a"]["code"] == {"n": 5, "passed": 4, "rate": 0.8})
    ctx.check(f"the words: from 3 tasks, the most measured first, got {row_words(mine['or:v/a'])!r}",
              row_words(mine["or:v/a"]) == "code 4/5" and words("code", a) == "4/5 code"
              and row_words({"code": {"n": 3, "passed": 3}, "plan": {"n": 4, "passed": 1}}) == "plan 1/4, code 3/3")


def _models(argv) -> str:
    from halo_harness.catalog_cli import cmd_models
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_models(argv)
    return buf.getvalue()


@test
def test_halo_models_measured(ctx: Ctx):
    with R.home() as state:
        empty = _models(["--measured"])
        seed_outcomes(state, "or:v/a", "code", ["passed", "passed", "failed"])
        seed_outcomes(state, "or:v/a", "review", ["passed"])
        text = _models(["--measured"])
        rows = json.loads(_models(["--measured", "--json"]))
    ctx.check("nothing yet says how rows get there", "Nothing measured yet" in empty)
    ctx.check(f"one row per model and kind, got\n{text}",
              text.splitlines()[0].split() == ["model", "kind", "n", "passed", "rate", "mean", "cost"]
              and any(l.startswith("or:v/a") and " code " in l and "2/3" in l and "67%" in l for l in text.splitlines()))
    ctx.check("a kind under 3 tasks is marked", any(" review " in l and "not routed on" in l for l in text.splitlines()))
    ctx.check(f"--json, got {rows}", [(r["model"], r["kind"], r["n"], r["rate"]) for r in rows] ==
              [("or:v/a", "code", 3, 0.667), ("or:v/a", "review", 1, 1.0)])


@test
def test_the_catalog_row_the_best_at_line_and_analyze(ctx: Ctx):
    from halo_harness.capabilities_line import best_at_line
    from halo_harness.models_analyze_cli import summary_lines
    from halo_harness.models_best_at import index, is_fresh, load, rebuild
    with S.home("measured-") as (_root, state):
        env = S.seed(state)
        before = S.rows_by_ref(state, env)["or:v/cheap"]
        cache = rebuild(state, list(S.rows_by_ref(state, env).values()))
        seed_outcomes(state, "or:v/cheap", "code", ["passed", "passed", "passed", "passed", "failed"])
        seed_outcomes(state, "or:v/cheap", "plan", ["passed", "failed"])
        stale = not is_fresh(load(state), state)
        row = S.rows_by_ref(state, env)["or:v/cheap"]
        line = best_at_line(row)
        fresh = index(state, list(S.rows_by_ref(state, env).values()))
        text = "\n".join(summary_lines(fresh, state))
    ctx.check("no outcomes, no measured words", "measured:" not in best_at_line(before) and "outcomes" not in (before.get("measured") or {}))
    ctx.check(f"the row carries the outcomes, got {row.get('measured', {}).get('outcomes')}",
              row["measured"]["outcomes"] == {"code": {"n": 5, "passed": 4, "rate": 0.8}, "plan": {"n": 2, "passed": 1, "rate": 0.5}})
    ctx.check(f"the best-at line says it from 3 tasks (plan has 2), got {line!r}", "measured: code 4/5" in line and "plan" not in line)
    ctx.check("a new outcome row makes the cache stale", cache and stale)
    ctx.check(f"the rebuilt cache's line has it, got {fresh['rows']['or:v/cheap']['line']!r}",
              "measured: code 4/5" in fresh["rows"]["or:v/cheap"]["line"])
    ctx.check(f"analyze lists the table, got\n{text[-400:]}", "Measured success per model and kind here" in text
              and any("or:v/cheap" in l and " code " in l and "4/5" in l for l in text.splitlines()))


@test
def test_the_roster_line_gains_the_words(ctx: Ctx):
    from halo_harness.providers.roster import roster_block
    with S.home("measured-roster-") as (_root, state):
        env = S.seed(state)
        seed_outcomes(state, "or:v/cheap", "code", ["passed", "passed", "failed"])
        text = roster_block(state, list(S.rows_by_ref(state, env).values()))
    line = next((l for l in text.splitlines() if l.startswith("- or:v/cheap ")), "")
    ctx.check(f"the roster's model line names it, got {line!r}", line.endswith("measured: code 2/3") or "code 2/3" in line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
