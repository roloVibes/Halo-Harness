"""tests.test_checks_catalog -- Halo 3.2.2.0 R2: the five checks Halo offers (3.3.7.0 R5: the steward candidates)
after setup (halo_harness/checks/catalog.py, run.py; tests/test_start_checks.py until 3.4.0.0 B, when the guided
first run left for the first-run pack, whose Setup block is its row now).

1. the five rows in order, each with its what / cost / time / writes, the
   first three on by default
2. `explain`: a row per check, [x] for the ticked ones, then its detail line
3. each `run` through stubs (no model call, no network): doctor, catalog,
   hello, gym (a cloud model is named, not run)
4. `run_one` turns an unexpected error into one line; `run_many` keeps the
   order and stops when asked
5. the cost lines: hello at the catalog price, the gym per model
Run: python -m tests.test_checks_catalog
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@contextmanager
def _patched(module, **values):
    saved = {k: getattr(module, k) for k in values}
    try:
        for k, v in values.items():
            setattr(module, k, v)
        yield
    finally:
        for k, v in saved.items():
            setattr(module, k, v)


def _ctx(**kw):
    from halo_harness.config.paths import bridge_home
    from halo_harness.checks.catalog import CheckCtx
    return CheckCtx(cwd=Path.cwd(), state_dir=Path(bridge_home()), **kw)


@test
def test_five_rows_in_order_with_their_defaults(ctx: Ctx):
    from halo_harness.checks import catalog as C
    ctx.check(f"the five keys in order, got {C.KEYS}", C.KEYS == ("doctor", "catalog", "hello", "steward", "gym"))
    ctx.check(f"the first three on, got {C.DEFAULT_KEYS}", C.DEFAULT_KEYS == ("doctor", "catalog", "hello"))
    fields = ("key", "title", "what", "cost", "time", "writes", "default_on", "run")
    ctx.check("every row has every field", all(all(f in c for f in fields) and callable(c["run"]) for c in C.CHECKS))
    ctx.check("doctor and catalog are free; hello one tiny call", C.check("doctor")["cost"] == "free"
              and C.check("catalog")["cost"].startswith("free") and C.check("hello")["cost"] == "one tiny call")
    ctx.check("the gym is minutes per model and writes its cards", "per model" in C.check("gym")["time"]
              and "~/.halo/gym/" in C.check("gym")["writes"])
    ctx.check("ordered() keeps the list's order; start is no core check (3.4.0.0 B)",
              C.ordered(["start", "doctor", "nope", "gym"]) == ["doctor", "gym"])


@test
def test_explain_is_a_row_per_check(ctx: Ctx):
    from halo_harness.checks import catalog as C
    from tests.helpers.custom_lineup import custom_lineup
    with custom_lineup():
        lines = C.explain()
    ctx.check(f"two lines per check, got {len(lines)}", len(lines) == 10)
    ctx.check(f"the defaults ticked, got {lines[::2]}", lines[::2] == ["[x] Doctor (doctor)", "[x] Model catalog (catalog)",
                                                                       "[x] Hello (hello)", "[ ] Steward candidates (steward)",
                                                                       "[ ] Model gym, quick (gym)"])
    ctx.check("each detail line: what, cost, time, writes", all(l.startswith("    ") and ". Cost: " in l and ". Time: " in l
                                                                and ". Writes: " in l for l in lines[1::2]))
    with custom_lineup():
        ctx.check("explain(keys) ticks those", C.explain(["gym"])[8].startswith("[x] Model gym"))


@test
def test_doctor_catalog_and_hello_run_through_stubs(ctx: Ctx):
    from halo_harness import doctor, init_cli
    from halo_harness.checks import catalog as C
    from halo_harness.studio import catalog_env, models_refresh
    with _patched(doctor, run_checks=lambda cwd=None: (["[OK] config", "[WARN] a note"], True)):
        ctx.check("doctor: its lines, ok", C.run_one("doctor", _ctx()) == (True, ["[OK] config", "[WARN] a note"]))
    with _patched(doctor, run_checks=lambda cwd=None: (["[MISSING] halo on PATH"], False)):
        ctx.check("doctor: a MISSING line fails it", C.run_one("doctor", _ctx()) == (False, ["[MISSING] halo on PATH"]))
    outcomes = [{"name": "openrouter", "ok": True, "line": "ok, 300 models"}, {"name": "lan", "ok": False, "line": "timed out"}]
    with _patched(models_refresh, refresh=lambda s, e, **k: {"outcomes": outcomes}), _patched(catalog_env, catalog_env=lambda cwd=None: {}):
        ok, lines = C.run_one("catalog", _ctx())
        ctx.check(f"catalog: one line per provider, ok while one came back, got {ok} {lines}", ok and lines ==
                  ["[ok] openrouter: ok, 300 models", "[!!] lan: timed out"])
        with _patched(models_refresh, refresh=lambda s, e, **k: {"outcomes": outcomes[1:]}):
            ctx.check("catalog: none came back fails it", C.run_one("catalog", _ctx())[0] is False)
        with _patched(models_refresh, refresh=lambda s, e, **k: {"outcomes": []}):
            ok, lines = C.run_one("catalog", _ctx())
            ctx.check(f"catalog: no provider says so, got {lines}", ok and "halo init" in lines[0])
    ctx.check("catalog: --no-live skips it", C.run_one("catalog", _ctx(no_live=True)) == (True, ["skipped: --no-live"]))
    seen = []
    pong = lambda m, cwd: (seen.append(m) or (True, f"model={m} reply='pong' cost=$0.000010"))
    with _patched(init_cli, _run_live_pong=pong):
        ctx.check("hello: the pong line", C.run_one("hello", _ctx(model="or:v/m"))[1] == ["model=or:v/m reply='pong' cost=$0.000010"]
                  and seen == ["or:v/m"])
        ok, lines = C.run_one("hello", _ctx(model=""))
        ctx.check(f"hello: no default model skips it, got {lines}", ok and lines[0].startswith("skipped: no default model"))
    with _patched(init_cli, _run_live_pong=lambda m, cwd: (False, "live call failed: boom")):
        ok, lines = C.run_one("hello", _ctx(model="or:v/m"))
        ctx.check(f"hello: no valid reply fails it, got {lines}", not ok and lines[0] == "live call failed: boom")
    ctx.check("hello: --no-live skips it", C.run_one("hello", _ctx(model="or:v/m", no_live=True))[1] == ["skipped: --no-live"])


@test
def test_gym_runs_through_stubs(ctx: Ctx):
    from halo_harness import gym_run
    from halo_harness.checks import catalog as C
    ran = []

    def fake_gym(refs, quick=False, state_dir=None, on_each=None):
        ran.append((list(refs), quick))
        return [{"tool_call_accuracy": {"score": 1.0}, "edit_success": {"score": 0.5}, "errors": []} for _ in refs]
    with _patched(gym_run, run_gym=fake_gym):
        ok, lines = C.run_one("gym", _ctx(gym_models=["ol:qwen3", "or:v/cloud"]))
        ctx.check(f"gym: the local model runs --quick, got {ran}", ran == [(["ol:qwen3"], True)])
        ctx.check(f"gym: the cloud one is named, not run; the score shown, got {lines}", ok
                  and lines[0].startswith("or:v/cloud: not run") and "ol:qwen3: overall 0.75" in lines)
        ran.clear()
        ok, lines = C.run_one("gym", _ctx(gym_models=["or:v/cloud"]))
        ctx.check(f"gym: only cloud models runs nothing, got {ran} {lines}", ok and ran == [] and len(lines) == 1)
        ok, lines = C.run_one("gym", _ctx(gym_models=[]))
        ctx.check(f"gym: nothing picked says so, got {lines}", ok and lines[0].startswith("nothing to run"))
    with _patched(gym_run, run_gym=lambda refs, **k: [{"errors": ["unreachable"]} for _ in refs]):
        ok, lines = C.run_one("gym", _ctx(gym_models=["ol:qwen3"]))
        ctx.check(f"gym: no score at all fails it, got {lines}", not ok and "unreachable" in lines[0])


@test
def test_run_one_and_run_many(ctx: Ctx):
    from halo_harness.checks import catalog as C
    saved = {c["key"]: c["run"] for c in C.CHECKS}
    order = []

    def boom(_ctx):
        raise TypeError("bad value")
    try:
        for c in C.CHECKS:
            c["run"] = (lambda k: (lambda _c: order.append(k) or [k + " ok"]))(c["key"])
        C.check("hello")["run"] = boom
        seen = []
        from tests.helpers.custom_lineup import custom_lineup
        with custom_lineup():
            out = C.run_many(["hello", "gym", "doctor"], _ctx(), on_each=lambda k, ok, l: seen.append((k, ok)))
        ctx.check(f"in the list's order, an error is one line, got {out}", out == [("doctor", True, ["doctor ok"]),
                  ("hello", False, ["TypeError: bad value"]), ("gym", True, ["gym ok"])])
        ctx.check(f"on_each before and after each, got {seen}", seen == [("doctor", None), ("doctor", True), ("hello", None),
                  ("hello", False), ("gym", None), ("gym", True)])
        order.clear()
        out = C.run_many(C.KEYS, _ctx(), stop=lambda: len(order) >= 2)
        ctx.check(f"stop() ends the list before the next one, got {order}", order == ["doctor", "catalog"] and len(out) == 2)
    finally:
        for c in C.CHECKS:
            c["run"] = saved[c["key"]]


@test
def test_cost_lines(ctx: Ctx):
    from halo_harness.checks import catalog as C
    from halo_harness.checks import run as R
    from halo_harness.tui.dialogs import team_preview
    rows = {"or:v/m": {"price_in_per_m": 1.0, "price_out_per_m": 2.0}}
    with _patched(team_preview, catalog_by_ref=lambda: rows):
        got = C.cost_line(C.check("hello"), _ctx(model="or:v/m"))
        ctx.check(f"hello: the catalog price of one tiny call, got {got!r}", got == "one tiny call, about $0.0020 at or:v/m's catalog price")
        ctx.check("hello: a local model is free", C.cost_line(C.check("hello"), _ctx(model="ol:qwen3")).endswith("free (a local model)"))
        ctx.check("hello: an unpriced model is named", "price unknown for or:v/x" in C.cost_line(C.check("hello"), _ctx(model="or:v/x")))
    got = C.cost_line(C.check("gym"), _ctx(gym_models=["ol:qwen3", "or:v/m"]))
    ctx.check(f"gym: per model, got {got!r}", got == "ol:qwen3: free, a few minutes; or:v/m: " + R.GYM_LOCAL_ONLY)
    ctx.check("no ctx: the static cost", C.cost_line(C.check("gym")) == C.check("gym")["cost"])
    cands = R.gym_candidates(_ctx(model="ol:qwen3"))
    ctx.check(f"the gym's candidates start with the default model, once, got {cands}", cands[:1] == ["ol:qwen3"]
              and len(cands) == len(set(cands)) and "default" not in cands)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
