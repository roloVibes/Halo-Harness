"""tests.test_models_auto_learn -- Auto learns (Halo 3.1.9.0 R3,
halo_harness/outcomes/learn.py, models_auto.pick): what was measured weighs
the `auto` pick, on fixture index rows and the seeded outcomes fixture
tests/fixtures/outcomes/learn-pick.jsonl (or:t/strong code 1/4, or:t/cheap
5/5 and five failed rows 40 days old, or:t/a 0/3, or:t/main plan 2/2):

1. the weight function: under min_tasks 1.0, else 0.5 + 0.5 x rate (1.0,
   0.75, 0.5), off -> 1.0; the settings read a bool, a word or an object;
2. a cheaper model that keeps succeeding beats a stronger one that keeps
   returning, the reason saying "(learned: code 1/4 on or:t/strong, so
   or:t/cheap instead)"; a confirmed pick says "(code 5/5 here)";
3. a model that keeps failing loses its place among equals (band mid, band
   low, and when it is main's own model);
4. `models.learn: false` (the setting and the config file) restores R2's
   order and reason;
5. the window (older rows do not count; 0 counts every row) and min_tasks;
   the same through a seeded outcomes.jsonl and the config file.
No model call. Run: python -m tests.test_models_auto_learn
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

test, TESTS = new_registry()
ON = {"enabled": True, "min_tasks": 3, "window_days": 30, "drop_below": 0.34}


def _facts(pin, pout):
    return {"provider": "openrouter", "price_in_per_m": pin, "price_out_per_m": pout, "modalities_in": ["text"],
            "modalities_out": ["text"], "tools": True, "reasoning": {"kind": "none"}, "context_tokens": 100000,
            "local": False}


ROWS = {"or:t/strong": {"kinds": ["code"], "scores": {"code": 0.9}, "facts": _facts(2.0, 8.0)},
        "or:t/cheap": {"kinds": ["code"], "scores": {"code": 0.6}, "facts": _facts(0.5, 2.0)}}
EQUALS = {"or:t/a": {"kinds": ["code"], "scores": {"code": 0.7}, "facts": _facts(1.0, 4.0)},
          "or:t/b": {"kinds": ["code"], "scores": {"code": 0.7}, "facts": _facts(1.0, 4.0)}}


def _stats(cfg=ON):
    from halo_harness.outcomes.learn import numbers
    return numbers(rows=R.fixture_rows("learn-pick"), cfg=cfg, now=R.FIXTURE_NOW)


def _pick(rows=ROWS, cfg=ON, stats="fixture", **kw):
    from halo_harness.models_auto import pick
    kw.setdefault("needs", ["tools"])
    kw.setdefault("main_ref", "or:t/main")
    return pick(None, rows=rows, kind="code", learn=cfg, stats=_stats(cfg) if stats == "fixture" else stats, **kw)


@test
def test_the_weight_function_and_the_settings(ctx: Ctx):
    from halo_harness.outcomes.learn import DEFAULTS, settings, weight
    stats = {("m", "code"): {"n": n, "passed": p, "rate": round(p / n, 3)} for n, p in ((4, 4),)}
    stats.update({("half", "code"): {"n": 4, "passed": 2, "rate": 0.5}, ("zero", "code"): {"n": 3, "passed": 0, "rate": 0.0},
                  ("few", "code"): {"n": 2, "passed": 0, "rate": 0.0}})
    got = [weight(m, "code", stats, ON) for m in ("m", "half", "zero", "few", "nobody")]
    ctx.check(f"rate 1.0 -> 1.0, 0.5 -> 0.75, 0.0 -> 0.5; under min_tasks and unmeasured 1.0, got {got}",
              got == [1.0, 0.75, 0.5, 1.0, 1.0])
    ctx.check("the other kind is not this one's", weight("m", "plan", stats, ON) == 1.0)
    ctx.check("off: every weight 1.0", weight("zero", "code", stats, dict(ON, enabled=False)) == 1.0)
    ctx.check("min_tasks 2 counts the two", weight("few", "code", stats, dict(ON, min_tasks=2)) == 0.5)
    ctx.check(f"the defaults, got {settings(True)}", settings(True) == DEFAULTS == ON)
    ctx.check("false and a word turn it off", not settings(False)["enabled"] and not settings("off")["enabled"])
    obj = settings({"min_tasks": 5, "window_days": 0, "drop_below": 0.5})
    ctx.check(f"an object sets the knobs and stays on, got {obj}",
              obj == {"enabled": True, "min_tasks": 5, "window_days": 0, "drop_below": 0.5})
    bad = settings({"enabled": "false", "min_tasks": "lots", "window_days": -3, "drop_below": 2})
    ctx.check(f"a knob that does not read keeps its default, got {bad}",
              bad == {"enabled": False, "min_tasks": 3, "window_days": 30, "drop_below": 0.34})


@test
def test_a_cheaper_succeeding_model_beats_a_stronger_returning_one(ctx: Ctx):
    before = _pick(stats={}, band="high")
    p = _pick(band="high")
    ctx.check(f"nothing learned: the strongest, got {before.line()!r}",
              before.ref == "or:t/strong" and "learned" not in before.reason and before.reason.endswith("($2.00/$8.00 per 1M)"))
    ctx.check(f"learned: the cheaper one that keeps succeeding, saying why, got {p.line()!r}",
              p.ref == "or:t/cheap" and p.reason == "the bio asks for tools, the strongest tools model ($0.50/$2.00 per 1M) "
                                                   "(learned: code 1/4 on or:t/strong, so or:t/cheap instead)")
    ctx.check(f"the one it beat is the next alternative, got {p.alternatives}", p.alternatives == ["or:t/strong"])
    low = _pick(band="low")
    ctx.check(f"a confirmed pick says its numbers, got {low.line()!r}",
              low.ref == "or:t/cheap" and low.reason.endswith("($0.50/$2.00 per 1M) (code 5/5 here)"))
    from halo_harness.models_auto import pick
    plan = pick(None, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", kind="plan", learn=ON, stats=_stats())
    ctx.check(f"another kind's numbers do not move it, got {plan.line()!r}", plan.ref == "or:t/strong" and "(" not in plan.reason[-12:])
    role = pick(None, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", role="coder coder coder", learn=ON,
                stats=_stats())
    ctx.check(f"no kind given: the role's words name it (coder -> code), got {role.line()!r}", role.ref == "or:t/cheap")


@test
def test_a_failing_model_loses_its_place_among_equals(ctx: Ctx):
    for band in ("mid", "low"):
        before = _pick(rows=EQUALS, stats={}, band=band)
        p = _pick(rows=EQUALS, band=band)
        ctx.check(f"band {band}: equals go by name, then or:t/a (0/3) gives way, got {before.ref} -> {p.line()!r}",
                  before.ref == "or:t/a" and p.ref == "or:t/b"
                  and p.reason.endswith("(learned: code 0/3 on or:t/a, so or:t/b instead)"))
    tie = _pick(rows=EQUALS, stats={}, main_ref="or:t/a")
    p = _pick(rows=EQUALS, main_ref="or:t/a")
    ctx.check(f"main's own model wins a tie until it keeps failing, got {tie.line()!r} -> {p.line()!r}",
              tie.ref == "or:t/a" and tie.reason.endswith("; a tie, so main's own model")
              and p.ref == "or:t/b" and "a tie" not in p.reason and "(learned: code 0/3 on or:t/a" in p.reason)


@test
def test_learning_off_restores_r2s_order(ctx: Ctx):
    from halo_harness.models_auto import pick
    from halo_harness.outcomes.learn import settings
    from halo_harness.theme import set_config_value
    for rows, band in ((ROWS, "high"), (EQUALS, "mid"), (EQUALS, "low")):
        r2 = pick(None, rows=rows, needs=["tools"], main_ref="or:t/main", band=band)
        off = _pick(rows=rows, band=band, cfg=dict(ON, enabled=False))
        ctx.check(f"band {band}, learning off: R2's pick and reason, got {off.line()!r}",
                  (off.ref, off.reason, off.alternatives) == (r2.ref, r2.reason, r2.alternatives))
    with R.home("learn-off-") as state:
        R.seed_fixture(state, "learn-pick")
        on = pick(state, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", kind="code")
        set_config_value("models.learn", False)
        off = pick(state, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", kind="code")
        cfg = settings()
    ctx.check(f"through the file: on learns, got {on.line()!r}", on.ref == "or:t/cheap" and "(learned:" in on.reason)
    ctx.check(f"config models.learn false: R2's pick, got {off.line()!r} ({cfg})",
              off.ref == "or:t/strong" and "learned" not in off.reason and not cfg["enabled"])


@test
def test_the_window_and_min_tasks(ctx: Ctx):
    from halo_harness.models_auto import pick
    from halo_harness.theme import set_config_value
    stats = _stats()
    ctx.check(f"the 30-day window leaves out the five old failures, got {stats.get(('or:t/cheap', 'code'))}",
              stats[("or:t/cheap", "code")]["n"] == 5 and stats[("or:t/cheap", "code")]["passed"] == 5)
    ctx.check("unchecked rows (done, stopped) are not learned from", ("or:t/b", "code") not in stats)
    ctx.check(f"how many were the model's own picks, got {stats[('or:t/cheap', 'code')].get('picked')}",
              stats[("or:t/cheap", "code")]["picked"] == 5 and stats[("or:t/main", "plan")]["picked"] == 0)
    every = dict(ON, window_days=0)
    p = _pick(band="high", cfg=every)
    ctx.check(f"window 0 counts every row: or:t/cheap is 5/10 and the strongest stays, got {p.line()!r}",
              _stats(every)[("or:t/cheap", "code")]["n"] == 10 and p.ref == "or:t/strong" and p.reason.endswith("(code 1/4 here)"))
    p = _pick(band="high", cfg=dict(ON, min_tasks=5))
    ctx.check(f"min_tasks 5: or:t/strong's four tasks do not weigh yet, got {p.line()!r}",
              p.ref == "or:t/strong" and "learned" not in p.reason and "here)" not in p.reason)
    p = _pick(band="high", cfg=dict(ON, min_tasks=6))
    ctx.check(f"min_tasks 6: nothing weighs, got {p.line()!r}", p.ref == "or:t/strong" and p.reason.endswith("per 1M)"))
    with R.home("learn-window-") as state:
        R.seed_fixture(state, "learn-pick")
        set_config_value("models.learn", {"window_days": 0})
        p = pick(state, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", kind="code")
        set_config_value("models.learn.min_tasks", 6)
        q = pick(state, rows=ROWS, needs=["tools"], main_ref="or:t/main", band="high", kind="code")
    ctx.check(f"the config file's window: every row counts, got {p.line()!r}", p.ref == "or:t/strong" and "(code 1/4 here)" in p.reason)
    ctx.check(f"the config file's min_tasks: nothing weighs, got {q.line()!r}", q.ref == "or:t/strong" and q.reason.endswith("per 1M)"))
    same = [_pick(band=b).line() for b in ("low", "mid", "high") for _ in range(2)]
    ctx.check("the same numbers give the same pick every time", same[0::2] == same[1::2])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
