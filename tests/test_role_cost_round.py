"""tests.test_role_cost_round -- Halo 2.0.6 round 2: per-role cost
attribution.

The v2.0.4 model review's "if I only got one" item: every cost entry
carries the role (and bio) that spent it; `/stats` and `halo stats`
show spend by role, cost per task and cost per accepted result, "so a
role assignment can be judged by evidence."

Data model: a usage node's `role` names the spender (main-session nodes
tag "main" since this round; a sub-agent rollup carries its resolved
role), `bio` the agent NAME on a rollup, and `ok` the Agent call's own
outcome -- a rollup node (agent_id set) IS one task; ok=True means the
child ran to a normal completion (an accepted result).
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _tmp_log():
    from halo_harness.agent.log import SessionLog
    d = Path(tempfile.mkdtemp(prefix="rolecost-"))
    log = SessionLog(d / "s.jsonl")
    return log


@test
def test_usage_node_carries_role_bio_ok(ctx: Ctx):
    log = _tmp_log()
    try:
        # a main-session node: role only, never a task
        log.append_usage({"input_tokens": 10, "output_tokens": 5}, 0.01, model="or:mock/x",
                         role="main")
        # a sub-agent rollup: role + bio + ok, agent_id set
        log.append_usage({"input_tokens": 100, "output_tokens": 50}, 0.50, model="or:mock/x",
                         agent_id="a1", role="worker", bio="implementer", ok=True)
        log.append_usage({"input_tokens": 100, "output_tokens": 50}, 0.25, model="or:mock/x",
                         agent_id="a2", role="worker", bio="implementer", ok=False)
        nodes = [n for n in log.nodes() if n.get("type") == "usage"]
        main_n, ok_n, fail_n = nodes
        ctx.check("the main node carries its role", main_n.get("role") == "main")
        ctx.check("a main node is never a task (no agent_id/ok/bio)",
                  "agent_id" not in main_n and "ok" not in main_n and "bio" not in main_n)
        ctx.check("the rollup carries role+bio+ok",
                  (ok_n.get("role"), ok_n.get("bio"), ok_n.get("ok")) == ("worker", "implementer", True))
        ctx.check("a failed task is ok=False", fail_n.get("ok") is False)
    finally:
        pass


@test
def test_compute_session_stats_roles_and_units(ctx: Ctx):
    from halo_harness.controller import compute_session_stats
    nodes = [
        {"type": "meta", "model": "or:mock/x"},
        {"type": "user", "kind": None},
        # main session: 2 calls, $0.02
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 5}, "cost_usd": 0.01, "role": "main"},
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 5}, "cost_usd": 0.01, "role": "main"},
        # worker: 2 tasks (1 ok), $1.00 -> $0.50/task, $1.00/accepted
        {"type": "usage", "usage": {"input_tokens": 100, "output_tokens": 50}, "cost_usd": 0.50,
         "agent_id": "a1", "role": "worker", "bio": "implementer", "ok": True},
        {"type": "usage", "usage": {"input_tokens": 100, "output_tokens": 50}, "cost_usd": 0.50,
         "agent_id": "a2", "role": "worker", "bio": "implementer", "ok": False},
        # a cc:-route estimate under main: subscription lane, not real spend
        {"type": "usage", "usage": {"input_tokens": 1, "output_tokens": 1}, "cost_usd": 0.30,
         "estimate": True, "role": "main"},
    ]
    stats = compute_session_stats(nodes)
    pr = stats.get("per_role") or {}
    ctx.check(f"both roles appear, got {sorted(pr)}", sorted(pr) == ["main", "worker"])
    main_r, worker_r = pr["main"], pr["worker"]
    ctx.check(f"main: 3 calls (2 real + 1 subscription), got {main_r['calls']}", main_r["calls"] == 3)
    ctx.check(f"main is never a task, got {main_r['tasks']}", main_r["tasks"] == 0)
    ctx.check(f"main real cost stays $0.02, got {main_r['cost_usd']}", abs(main_r["cost_usd"] - 0.02) < 1e-9)
    ctx.check(f"main subscription estimate lands its own lane, got {main_r['subscription_cost_usd']}",
              abs(main_r["subscription_cost_usd"] - 0.30) < 1e-9)
    ctx.check(f"worker: 2 calls 2 tasks 1 accepted, got {worker_r}",
              (worker_r["calls"], worker_r["tasks"], worker_r["accepted"]) == (2, 2, 1))
    ctx.check(f"worker cost $1.00, got {worker_r['cost_usd']}", abs(worker_r["cost_usd"] - 1.0) < 1e-9)
    ctx.check("total_cost_usd never counts the estimate", abs(stats["total_cost_usd"] - 1.02) < 1e-9)


@test
def test_telemetry_role_rows_give_the_units(ctx: Ctx):
    from halo_harness.telemetry import SessionSummary, aggregate_by_role
    s = SessionSummary(session_id="s1", slug="p", path="p/s1.jsonl", mtime=time.time(), size=10,
                       turns=1, models={}, tools={}, roles={})
    from halo_harness.telemetry import _new_role_counters
    w = _new_role_counters()
    w.update({"calls": 4, "tokens_in": 200, "tokens_out": 100, "tokens_cached": 0, "cost_usd": 2.0,
              "tasks": 4, "accepted": 2})
    s.roles["worker"] = w
    m = _new_role_counters()
    m.update({"calls": 10, "tokens_in": 500, "tokens_out": 250, "tokens_cached": 0, "cost_usd": 0.10,
              "tasks": 0, "accepted": 0})
    s.roles["main"] = m
    rows = aggregate_by_role([s])
    by = {r["role"]: r for r in rows}
    ctx.check(f"both roles rowed, got {sorted(by)}", sorted(by) == ["main", "worker"])
    wr = by["worker"]
    ctx.check(f"worker $/task = 0.5, got {wr['cost_per_task']}", wr["cost_per_task"] == 0.5)
    ctx.check(f"worker $/accepted = 1.0, got {wr['cost_per_accepted']}", wr["cost_per_accepted"] == 1.0)
    ctx.check(f"worker tasks/accepted carried, got {wr['tasks']}/{wr['accepted']}",
              (wr["tasks"], wr["accepted"]) == (4, 2))
    mr = by["main"]
    ctx.check(f"main has no tasks -> no $/task, got {mr['cost_per_task']}", mr["cost_per_task"] is None)
    ctx.check(f"main has no accepted -> no $/ok, got {mr['cost_per_accepted']}", mr["cost_per_accepted"] is None)


@test
def test_zero_denominators_never_divide(ctx: Ctx):
    from halo_harness.telemetry import SessionSummary, aggregate_by_role, _new_role_counters
    s = SessionSummary(session_id="s2", slug="p", path="p/s2.jsonl", mtime=time.time(), size=10,
                       turns=0, models={}, tools={}, roles={})
    # tasks with NO cost data at all (cost_usd 0.0 -- has_cost_data False)
    w = _new_role_counters()
    w.update({"calls": 2, "tasks": 2, "accepted": 0})
    s.roles["worker"] = w
    rows = aggregate_by_role([s])
    wr = rows[0]
    ctx.check(f"no cost -> $/task None (never $0.0000), got {wr['cost_per_task']!r}",
              wr["cost_per_task"] is None and wr["cost_per_accepted"] is None)


@test
def test_stats_cli_renders_the_new_columns(ctx: Ctx):
    from halo_harness.stats_cli import _ROLE_COLUMNS
    row = {"role": "worker", "sessions": 3, "calls": 4, "tokens_in": 200, "tokens_out": 100,
           "tokens_cached": 0, "cost_usd": 2.0, "tasks": 4, "accepted": 2,
           "cost_per_task": 0.5, "cost_per_accepted": 1.0, "model": "or:mock/x", "effort": "-"}
    names = [c[0] for c in _ROLE_COLUMNS]
    ctx.check(f"the role table gains tasks/ok/$ columns, got {names}",
              all(n in names for n in ("tasks", "ok", "$/task", "$/ok")))
    get = dict(_ROLE_COLUMNS)
    ctx.check(f"ok renders accepted/total, got {get['ok'](row)!r}", get["ok"](row) == "2/4")
    ctx.check(f"$/task renders, got {get['$/task'](row)!r}", get["$/task"](row) == "$0.5000")
    ctx.check(f"$/ok renders, got {get['$/ok'](row)!r}", get["$/ok"](row) == "$1.0000")
    empty = {**row, "tasks": 0, "accepted": 0, "cost_per_task": None, "cost_per_accepted": None}
    ctx.check(f"a roleless-spend row dashes instead of dividing, "
              f"got {get['tasks'](empty)!r} {get['ok'](empty)!r} {get['$/task'](empty)!r}",
              (get["tasks"](empty), get["ok"](empty), get["$/task"](empty)) == ("-", "-", "-"))


@test
def test_slash_stats_lines_carry_the_role_rows(ctx: Ctx):
    """The /stats rendering is a pure string build over compute_session_
    stats' dict -- pinned at the stats level (the pilot-level rendering
    is _handle_stats' own existing coverage)."""
    from halo_harness.controller import compute_session_stats
    stats = compute_session_stats([
        {"type": "meta", "model": "or:mock/x"},
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 5}, "cost_usd": 0.01, "role": "main"},
        {"type": "usage", "usage": {"input_tokens": 100, "output_tokens": 50}, "cost_usd": 0.50,
         "agent_id": "a1", "role": "worker", "bio": "implementer", "ok": True},
    ])
    pr = stats["per_role"]
    ctx.check(f"the slash view's data source has the roles, got {sorted(pr)}",
              sorted(pr) == ["main", "worker"])
    w = pr["worker"]
    ctx.check("worker carries task/accepted for the line build",
              (w["tasks"], w["accepted"]) == (1, 1))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
