"""tests.test_loading_tax -- Halo 3.3.7.0 R3 (G5): the loading tax (local_sched/loads.py), local cost in seconds:

1. the tally: a session's ledger lines that paid a load (load_ms over 2 s) plus the scheduler's own loads (a pivot,
   a warm), per model, one line ("loading: 3 loads, 1 m 15 s (qwen3.8:27b 2, qwen3-coder:30b 1)");
2. `/cost` carries it beside "Saved vs cloud" (and says "no loads" on a local session that paid none);
3. `halo session show <id>` prints it (and `--json` carries it); Studio's GET local/loads answers it (the Cost panel).
No model call, nothing sent.
Run: python -m tests.test_loading_tax
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SchedHome  # noqa: E402

test, TESTS = new_registry()


def _seed(h) -> None:
    from halo_harness.local_sched.loads import record
    h.loads(BIG, 30.0, 1.0, 25.0, session="s-tax")
    h.loads(CODER, 40.0, session="other")
    record(h.state, session="s-tax", host="pc", model=CODER, seconds=20.0, why="pivot")


@test
def test_the_tally(ctx: Ctx):
    from halo_harness.local_sched.loads import line_for, tally
    with SchedHome() as h:
        _seed(h)
        t = tally(h.state, "s-tax")
        ctx.check(f"two ledger loads over 2 s + the pivot, per model, got {t}", t["count"] == 3 and t["seconds"] == 75.0
                  and t["per_model"] == {BIG: {"count": 2, "seconds": 55.0}, CODER: {"count": 1, "seconds": 20.0}})
        ctx.check(f"the line, got {t['line']!r}", t["line"] == "loading: 3 loads, 1 m 15 s (qwen3.8:27b 2, qwen3-coder:30b 1)")
        ctx.check("none: said", tally(h.state, "nobody")["line"] == "loading: no loads" and line_for({"count": 0}) ==
                  "loading: no loads")


@test
def test_cost_carries_it_beside_the_dollars(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_cost
    from halo_harness.model import CostMeter
    with SchedHome() as h:
        _seed(h)
        cm = CostMeter(price_in=None, price_out=None)
        cm.has_cost_data, cm.turns = False, 2
        cm.set_savings_reference(price_in=0.000001, price_out=0.00001, source="catalog median")
        cm.add_savings({"input_tokens": 1000, "output_tokens": 100})
        s = SimpleNamespace(cost_meter=cm, state_dir=h.state, log=SimpleNamespace(session_id="s-tax"))
        out = _cmd_cost("", HeadlessFacade(cwd=Path("."), session=s, model_ref=f"ol:{BIG}@pc"))
        lines = out.splitlines()
        i = next(i for i, x in enumerate(lines) if x.startswith("Saved vs cloud:"))
        ctx.check(f"the loading line right after the saved line, got {lines}",
                  lines[i + 1] == "loading: 3 loads, 1 m 15 s (qwen3.8:27b 2, qwen3-coder:30b 1)")
        s.log.session_id = "quiet"
        out = _cmd_cost("", HeadlessFacade(cwd=Path("."), session=s, model_ref=f"ol:{BIG}@pc"))
        ctx.check(f"a local session with none: said, got {out!r}", "loading: no loads" in out)


@test
def test_session_show_and_studio(ctx: Ctx):
    from halo_harness.studio.api import Request, dispatch
    with SchedHome() as h:
        _seed(h)
        from halo_harness.session_trace_cli import _show
        import halo_harness.session_trace_cli as T
        saved = T.find_session_log
        T.find_session_log = lambda sid: (Path(h.root) / "s-tax.jsonl", "")
        (Path(h.root) / "s-tax.jsonl").write_text("", encoding="utf-8")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = _show(type("A", (), {"session": "s-tax", "json": False})())
        finally:
            T.find_session_log = saved
        ctx.check(f"halo session show prints it, got {out.getvalue()!r}", rc == 0
                  and "  loading: 3 loads, 1 m 15 s (qwen3.8:27b 2, qwen3-coder:30b 1)" in out.getvalue())
        code, got = dispatch(Request(method="GET", path="local/loads", query={"session": "s-tax"}, body={},
                                     cwd=Path(h.root), state_dir=h.state, server=None))
        ctx.check(f"GET local/loads, got {code} {got.get('line')}", code == 200 and got["count"] == 3
                  and got["line"].startswith("loading: 3 loads"))
        code, _got = dispatch(Request(method="GET", path="local/loads", query={}, body={}, cwd=Path(h.root),
                                      state_dir=h.state, server=None))
        ctx.check(f"no session: 422, got {code}", code == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
