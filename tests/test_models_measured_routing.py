"""tests.test_models_measured_routing -- `models.preference: measured` (Halo
3.1.8.0 R3, outcomes/routing.py):

1. among the candidates that carry the task's needs, the best measured rate
   for the bio's kind wins (from 3 checked tasks); a tie goes by the band's
   rule; the reason ends "(measured 4/5 code)"; a model measured high that
   lacks a need is not a candidate;
2. nothing measured for the kind (or under 3 tasks): the `auto` pick, its
   reason starting "nothing measured for code yet";
3. `teams_yaml` reads `measured` like `auto` with its own source word, the
   shipped auto lineup's bios stay `auto`, `halo teams show` says how it is
   picked;
4. at spawn: a lineup card whose bio says `measured` runs on the measured
   best, the reason on its agent row; with nothing measured, on the auto pick.
No real model call (a mocked upstream). Run: python -m tests.test_models_measured_routing
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _rows():
    from tests import test_auto_spawn as A
    return A.ROWS


def _stats(**rates) -> dict:
    """`code_eyes=(4, 5)` -> {("or:mock/auto-eyes", "code"): {...}}."""
    out = {}
    for key, (passed, n) in rates.items():
        kind, name = key.split("_", 1)
        out[(f"or:mock/auto-{name}", kind)] = {"n": n, "passed": passed, "returned": 0, "failed": n - passed,
                                               "rate": round(passed / n, 3), "cost_mean": 0.01}
    return out


@test
def test_the_best_measured_rate_wins_and_says_so(ctx: Ctx):
    from halo_harness.outcomes.routing import pick_measured
    p = pick_measured(None, kind="code", needs=["tools"], main_ref="or:mock/auto-main", rows=_rows(),
                      stats=_stats(code_eyes=(4, 5), code_cheap=(2, 5), code_main=(3, 5)))
    ctx.check(f"the best code rate among the tools models, got {p.line()!r}",
              p.ref == "or:mock/auto-eyes" and p.reason.endswith("(measured 4/5 code)")
              and p.reason.startswith("the best measured code rate here among the tools models ($0.30/$1.20 per 1M)")
              and p.alternatives == ["or:mock/auto-main", "or:mock/auto-cheap"] and not p.fallback)
    p = pick_measured(None, kind="code", needs=["tools"], main_ref="or:mock/auto-main", band="low", rows=_rows(),
                      stats=_stats(code_eyes=(4, 5), code_cheap=(4, 5)))
    ctx.check(f"a tie on the rate goes by the band (low: the cheaper), got {p.line()!r}",
              p.ref == "or:mock/auto-cheap" and "a tie on the rate" in p.reason and p.reason.endswith("(measured 4/5 code)"))
    p = pick_measured(None, kind="code", task_text="look at shot.png", main_ref="or:mock/auto-main", rows=_rows(),
                      stats=_stats(code_eyes=(1, 5), code_cheap=(5, 5)))
    ctx.check(f"a model that lacks a need is no candidate however it measured, got {p.line()!r}",
              p.ref == "or:mock/auto-eyes" and p.reason.endswith("(measured 1/5 code)") and p.kinds == ["vision"])


@test
def test_nothing_measured_falls_back_to_the_auto_pick(ctx: Ctx):
    from halo_harness.models_auto import pick
    from halo_harness.outcomes.routing import pick_measured
    auto = pick(None, needs=["tools"], main_ref="or:mock/auto-main", rows=_rows())
    for stats, why in (({}, "no rows at all"), (_stats(code_eyes=(2, 2)), "under 3 tasks"),
                       (_stats(research_eyes=(5, 5)), "another kind only")):
        p = pick_measured(None, kind="code", needs=["tools"], main_ref="or:mock/auto-main", rows=_rows(), stats=stats)
        ctx.check(f"{why}: the auto pick, saying nothing was measured, got {p.line()!r}",
                  p.ref == auto.ref and p.reason == f"nothing measured for code yet, so the auto pick: {auto.reason}")
    p = pick_measured(None, kind="plan", main_ref="or:mock/auto-main", rows={}, stats={})
    ctx.check(f"no index either: main's model, both said, got {p.line()!r}",
              p.fallback and p.reason.startswith("nothing measured for plan yet, so the auto pick: no model index yet"))


@test
def test_teams_yaml_reads_measured_like_auto(ctx: Ctx):
    import os
    import tempfile
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio
    from halo_harness.models_auto import is_auto, is_measured, spawn_word
    from halo_harness.models_auto_spawn import pool_words
    from halo_harness.teams_yaml import bio_pinned_model, member_model, resolve_team_template
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    d = Path(tempfile.mkdtemp(prefix="measured-teams-"))
    os.environ["BRIDGE_TEST_HOME"], os.environ["BRIDGE_STATE_DIR"] = str(d), str(d / ".halo")
    try:
        state = d / ".halo"
        save_agent_bio("measured-coder", {"description": "routes by what succeeded", "kind": "coder",
                                          "models": {"preference": "measured", "needs": ["tools"]}}, state_dir=state)
        template = {"agents": [{"agent": "default-model", "role": "main"}, {"agent": "measured-coder", "role": "coder"}]}
        entry = template["agents"][1]
        got = member_model(template, entry, state_dir=state)
        ctx.check(f"the card's model is `measured`, its source word `measured`, got {got}", got == ("measured", "", "measured"))
        ctx.check("a tier's model still comes first (the bio pins nothing)", bio_pinned_model("measured-coder", state_dir=state) is None)
        ctx.check("the literals", is_auto("measured") and is_auto("auto") and is_measured("Measured") and not is_measured("auto")
                  and spawn_word("measured") == "measured" and spawn_word("auto") == "auto")
        words = pool_words(template, entry, state_dir=state)
        ctx.check(f"`halo teams show` says how it is picked, got {words!r}",
                  words == " -- model picked at spawn (by measured success at its kind, else as auto; needs: tools; band mid)")
        auto = resolve_team_template("auto", state_dir=state) or {}
        prefs = {e["agent"]: (resolve_agent_bio(e["agent"], state_dir=state) or {}).get("models", {}).get("preference")
                 for e in auto.get("agents") or [] if e.get("agent", "").startswith("auto-")}
        ctx.check(f"the shipped auto lineup's bios stay auto, got {prefs}", len(prefs) == 7 and set(prefs.values()) == {"auto"})
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_at_spawn_a_measured_card_runs_on_the_measured_best(ctx: Ctx):
    from tests import test_auto_spawn as A
    from tests.test_outcomes_measured import seed_outcomes
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    from halo_harness.theme import set_config_value
    mock = A._mock()
    try:
        with A._Env() as e:
            A._seed_index(e.state_dir, A.ROWS)
            save_agent_bio("measured-coder", {"description": "routes by what succeeded", "kind": "coder",
                                              "models": {"preference": "measured", "needs": ["tools"]}}, state_dir=e.state_dir)
            ok, problems = save_team_template("measured", {
                "description": "a coder routed by measured success", "routing": {"fix": "coder"},
                "agents": [{"agent": "default-model", "role": "main"}, {"agent": "measured-coder", "role": "coder"}]},
                state_dir=e.state_dir)
            set_config_value("team", "measured")
            session = A._session(e, mock)
            A._dispatch(session, "c1", "fix the bug in basket.py", description="fix the bug")
            row0 = A._child(session, "c1").get("row") or {}
            seed_outcomes(e.state_dir, "or:mock/auto-eyes", "code", ["passed", "passed", "passed", "passed", "failed"])
            seed_outcomes(e.state_dir, "or:mock/auto-cheap", "code", ["passed", "failed", "failed"])
            session = A._session(e, mock)
            out2 = A._dispatch(session, "c2", "fix the bug in basket.py", description="fix the bug")
            row = A._child(session, "c2").get("row") or {}
    finally:
        mock.stop()
    ctx.check(f"the lineup saves, got {problems}", ok)
    ctx.check(f"nothing measured yet: the auto pick, saying so, got {row0.get('model')!r} {row0.get('model_reason')!r}",
              str(row0.get("model_reason") or "").startswith("nothing measured for code yet, so the auto pick: the bio asks for tools"))
    ctx.check(f"measured: the best code rate runs it, the reason on its row, got {out2[:60]!r} {row.get('model')!r} "
              f"{row.get('model_reason')!r}", "EYES SAW IT" in out2 and row.get("model") == "or:mock/auto-eyes"
              and str(row.get("model_reason") or "").endswith("(measured 4/5 code)"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
