"""tests.test_policy_gate -- a pack's verdict decides a tool call (Halo 3.3.10.0 R2; agent/policy_gate.py, the seams
in agent/loop.py `_resolve_tool_call`; docs/EXTENSION_API.md "Policy hooks"). A real Session on the mock upstream
with the `policy-fence` fixture pack armed (its `run` is a real process speaking the protocol):

1. a Write outside the project is refused with the pack's own line in the model's tool result, the tool event,
   the transcript row and the permission denial (pack, policy, rule named); no "Permission denied" wording;
2. a Write inside proceeds, its allow verdict on the row;
3. a PreToolUse hook that rewrites the path to outside is asked again and refused;
4. ask reaches the approval card with the pack's line, and a permission mode cycle leaves it parked;
5. a sub-agent's Write outside is refused too, its agent id on the events log row;
6. with no pack armed the loop makes exactly the calls it made before (decide's call count, the events, no
   process, no row);
7. the process starts at session start: the first verdict's time is under a tenth of the budget.
Run: python -m tests.test_policy_gate
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.policy_session import Upstream, fenced_home, outside, policy_rows, rewrite_hook, session_in  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import ThreadedTurn, request_text, text_step, tool_step  # noqa: E402

test, TESTS = new_registry()
LINE = "policy: deny -- fence: outside the project (pack policy-fence, rule outside-project)"


def _results(evs) -> list:
    return [e for e in evs if e.kind == "tool_result"]


def _tool_rows(s) -> list:
    return [n for n in s.log.nodes() if n.get("type") == "tool_result"]


@test
def test_a_write_outside_is_refused_with_the_packs_line(ctx: Ctx):
    with fenced_home() as h:
        target = outside(h)
        with Upstream("pg-deny", [tool_step("Write", {"file_path": str(target), "content": "x"}), text_step("ok")]) as up:
            s = session_in(h, up)
            evs = list(s.turn("write the file"))
            reqs = up.requests
        res = _results(evs)
        ctx.check(f"one refused result with the pack's line, got {[r.data for r in res]}", len(res) == 1
                  and res[0].data["ok"] is False and res[0].data["summary"] == LINE)
        ctx.check("the file was not written", not target.exists())
        ctx.check("the model's tool result is the pack's line", len(reqs) == 2 and LINE in request_text(reqs[1]))
        ctx.check("no Halo wording of its own", "Permission denied" not in request_text(reqs[1]))
        pol = res[0].data.get("policy") or {}
        ctx.check(f"the event carries the verdict, got {pol}", pol.get("line") == "policy: deny -- fence: outside the project"
                  and pol["verdicts"][0]["winner"] is True and pol["verdicts"][0]["rule"] == "outside-project")
        ready = [e for e in evs if e.kind == "tool_use_ready"]
        ctx.check("tool_use_ready carries it too", ready and (ready[0].data.get("policy") or {}).get("line") == pol.get("line"))
        row = _tool_rows(s)[0]
        ctx.check(f"the transcript row carries it, got {row.get('policy')}", (row.get("policy") or {}).get("line") == pol.get("line")
                  and row.get("error_class") == "denied_by_rule")
        d = s.permission_denials[-1] if s.permission_denials else {}
        ctx.check(f"the denial names the pack, policy and rule, got {d}", d.get("pack") == "policy-fence"
                  and d.get("policy") == "fence" and d.get("rule") == "outside-project" and d.get("reason") == LINE)
        rows = policy_rows("before")
        ctx.check(f"the events log row: deny, the winner, this session, got {rows}", rows and rows[-1]["verdict"] == "deny"
                  and rows[-1]["winner"] is True and rows[-1]["session"] == s.log.session_id and rows[-1]["agent"] == "")


@test
def test_a_write_inside_proceeds(ctx: Ctx):
    with fenced_home() as h:
        target = h.repo / "notes.txt"
        with Upstream("pg-inside", [tool_step("Write", {"file_path": str(target), "content": "hi"}), text_step("ok")]) as up:
            s = session_in(h, up, mode="acceptEdits")
            evs = list(s.turn("write the notes"))
        res = _results(evs)
        ctx.check(f"the Write ran, got {[r.data.get('summary') for r in res]}", len(res) == 1 and res[0].data["ok"] is True
                  and target.read_text(encoding="utf-8") == "hi")
        ctx.check("its allow verdict on the row", (res[0].data.get("policy") or {}).get("line")
                  == "policy: allow -- fence: inside the project")


@test
def test_a_hook_rewrite_to_outside_is_asked_again(ctx: Ctx):
    with fenced_home() as h:
        target = outside(h)
        inside = h.repo / "fine.txt"
        with Upstream("pg-rewrite", [tool_step("Write", {"file_path": str(inside), "content": "x"}), text_step("ok")]) as up:
            s = session_in(h, up, mode="acceptEdits", hook_runner=rewrite_hook(h, target))
            evs = list(s.turn("write the file"))
        res = _results(evs)
        ctx.check(f"refused after the rewrite, got {[r.data.get('summary') for r in res]}", len(res) == 1
                  and res[0].data["summary"] == LINE)
        ctx.check("neither file was written", not target.exists() and not inside.exists())
        rows = policy_rows("before")
        ctx.check(f"asked twice: allow on the input, deny on the rewrite, got {[r['verdict'] for r in rows]}",
                  [r["verdict"] for r in rows][-2:] == ["allow", "deny"])


@test
def test_ask_reaches_the_card_and_a_mode_cycle_keeps_it(ctx: Ctx):
    from halo_harness.permissions import Decision
    with fenced_home(HALO_POLICY_TEST_ASK=1) as h:
        target = outside(h)
        with Upstream("pg-ask", [tool_step("Write", {"file_path": str(target), "content": "x"}), text_step("ok")]) as up:
            s = session_in(h, up, interactive=True)
            t = ThreadedTurn(s, "write the file")
            ev = t.wait_for("permission_request")
            want = "policy: ask -- fence: outside the project (pack policy-fence, rule outside-project)"
            ctx.check(f"the card's line names the pack and why, got {ev.data.get('reason')!r}", ev.data.get("reason") == want)
            s.permission_engine.mode = "bypassPermissions"
            ctx.check("a mode cycle never answers a pack's ask", s.reevaluate_pending_permission(ev.data["id"]) is None)
            s.resolve_permission(ev.data["id"], Decision("deny", "not there"))
            t.join()
        ctx.check("answered no: the file was not written", not target.exists())


@test
def test_a_sub_agents_write_outside_is_refused(ctx: Ctx):
    with fenced_home() as h:
        target = outside(h)
        steps = [tool_step("Agent", {"description": "write", "prompt": "write the file", "subagent_type": "general-purpose"}),
                 tool_step("Write", {"file_path": str(target), "content": "x"}, call_id="call_c"),
                 text_step("the child is done"), text_step("done")]
        with Upstream("pg-child", steps) as up:
            s = session_in(h, up, agents=True)
            list(s.turn("delegate the write"))
        ctx.check("the file was not written", not target.exists())
        rows = [r for r in policy_rows("before") if r["verdict"] == "deny"]
        ctx.check(f"the child's call was asked, its agent id on the row, got {rows}", rows and rows[-1]["agent"] != ""
                  and rows[-1]["tool"] == "Write")


def _counted_turn(h, scenario: str, *, gate: bool) -> "tuple[int, list, list]":
    from halo_harness.agent import policy_gate as G
    saved = (G.decide, G.after)
    if not gate:  # the loop as it was before R2: the engine alone, no post-call step
        G.decide = lambda s, item, name, ti, tool: s.permission_engine.decide(name, ti, tool=tool)
        G.after = lambda s, item, tr: tr
    try:
        steps = [tool_step("Write", {"file_path": str(h.repo / f"{scenario}.txt"), "content": "x"}),
                 tool_step("Read", {"file_path": str(h.repo / f"{scenario}.txt")}, call_id="call_r"), text_step("ok")]
        with Upstream(scenario, steps) as up:
            s = session_in(h, up, mode="acceptEdits")
            calls = []
            real = s.permission_engine.decide
            s.permission_engine.decide = lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1]
            evs = list(s.turn("write then read"))
        shape = [(e.kind, sorted((e.data or {}).keys())) for e in evs if e.kind in ("tool_use_ready", "tool_result")]
        return len(calls), shape, _tool_rows(s)
    finally:
        G.decide, G.after = saved


@test
def test_no_pack_armed_is_the_loop_as_before(ctx: Ctx):
    from halo_harness.packs import policy as P
    for label, kw in (("no pack", {"install": False}), ("the pack installed, not armed", {"armed": False})):
        with fenced_home(**kw) as h:
            base_n, base_shape, _ = _counted_turn(h, "pg-base-" + label.split()[0], gate=False)
            n, shape, rows = _counted_turn(h, "pg-gate-" + label.split()[0], gate=True)
            ctx.check(f"{label}: decide called as often as before ({base_n}), got {n}", n == base_n == 2)
            ctx.check(f"{label}: the same events, no policy field", shape == base_shape
                      and all("policy" not in keys for _, keys in shape))
            ctx.check(f"{label}: no policy on a transcript row", all("policy" not in r for r in rows))
            ctx.check(f"{label}: no process, no row", P._procs == {} and policy_rows() == [])


@test
def test_the_process_starts_with_the_session(ctx: Ctx):
    from halo_harness.agent import policy_gate as G
    from halo_harness.packs import policy as P
    with fenced_home() as h:
        G.warm(h.repo)  # what headless.build_session does as a session starts
        procs = list(P._procs.values())
        ctx.check(f"running before the first tool call, got {procs}", len(procs) == 1 and procs[0].alive)
        target = outside(h)
        with Upstream("pg-warm", [tool_step("Write", {"file_path": str(target), "content": "x"}), text_step("ok")]) as up:
            s = session_in(h, up)
            list(s.turn("write"))
        row = policy_rows("before")[-1]
        budget = P.default_budget_ms()
        ctx.check(f"the first verdict under a tenth of the budget ({budget} ms), got {row['ms']} ms",
                  row["ms"] < budget / 10 and procs[0].started == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
