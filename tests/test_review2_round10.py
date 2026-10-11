"""tests.test_review2_round10 -- pins for the vibes/review.md fix pass,
round 10, telemetry and logs (findings 84, 85, 86, 89):

  * f84  a sub-agent's cost landed on the parent model's stats row
  * f85  the stats cache had no schema version and never pruned
  * f86  replay's list of non-prompt kinds missed what the log writes
  * f89  readers split logs with splitlines() and lost U+2028/U+2029 lines

The rest of round 10 lives in tests/test_review2_round10b.py (87, 88, 91)
and tests/test_review2_round10c.py (90, 92).
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

LS = " "
PS = " "


@contextlib.contextmanager
def scoped_home():
    """A fresh BRIDGE_TEST_HOME for one test; the old value comes back."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="r10-home-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _summarize(nodes):
    from halo_harness.telemetry import _summarize_nodes
    return _summarize_nodes(session_id="s", slug="p", path="s.jsonl", mtime=0, size=0, nodes=nodes,
                            corrupt_lines=0)


# ---- f84: sub-agent spend goes to the child's model ---------------------------

@test
def test_f84_rollup_is_charged_to_the_child_model_not_the_parent(ctx: Ctx):
    s = _summarize([
        {"type": "meta", "model": "or:vendor/parent"},
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 5}, "cost_usd": 0.01,
         "model": "or:vendor/parent", "provider": "p1"},
        {"type": "usage", "usage": {"input_tokens": 900, "output_tokens": 100}, "cost_usd": 0.5,
         "agent_id": "ag1", "role": "coder", "model": "or:vendor/child", "provider": "p2"},
        {"type": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}]},
    ])
    parent = s.models.get("or:vendor/parent\x1fp1")
    child = s.models.get("or:vendor/child\x1fp2")
    ctx.check(f"two rows, got {sorted(s.models)}", parent is not None and child is not None)
    ctx.check(f"parent row keeps only its own cost, got {parent['cost_usd']}", abs(parent["cost_usd"] - 0.01) < 1e-9)
    ctx.check(f"child row has the rollup cost, got {child['cost_usd']}", abs(child["cost_usd"] - 0.5) < 1e-9)
    ctx.check("the parent's later tool call stays on the parent row",
              parent["tool_use_total"] == 1 and child["tool_use_total"] == 0)


@test
def test_f84_rollup_without_a_recorded_model_gets_its_own_row(ctx: Ctx):
    s = _summarize([
        {"type": "meta", "model": "or:vendor/parent"},
        {"type": "usage", "usage": {"input_tokens": 1}, "cost_usd": 0.001, "model": "or:vendor/parent",
         "provider": "p1"},
        {"type": "usage", "usage": {"input_tokens": 40}, "cost_usd": 0.2, "agent_id": "ag1", "role": "x"},
    ])
    parent = s.models["or:vendor/parent\x1fp1"]
    ctx.check(f"parent cost untouched, got {parent['cost_usd']}", abs(parent["cost_usd"] - 0.001) < 1e-9)
    rows = [k for k in s.models if k.startswith("(sub-agents)")]
    ctx.check(f"a labelled row holds the unattributed spend, got {sorted(s.models)}",
              len(rows) == 1 and abs(s.models[rows[0]]["cost_usd"] - 0.2) < 1e-9)


@test
def test_f84_the_rollup_node_carries_the_childs_own_model(ctx: Ctx):
    from halo_harness.agent.subagent import _rollup_child_cost_into_parent
    logged = []
    parent = SimpleNamespace(
        log=SimpleNamespace(append_usage=lambda *a, **kw: logged.append((a, kw))),
        _agent_notices_lock=threading.Lock(),
        cost_meter=SimpleNamespace(add_child_total=lambda **kw: None))
    child_nodes = [
        {"type": "usage", "usage": {"input_tokens": 5}, "model": "or:vendor/small", "provider": "pa"},
        {"type": "usage", "usage": {"input_tokens": 500, "output_tokens": 50}, "model": "or:vendor/big",
         "provider": "pb", "route": "or"},
    ]
    child = SimpleNamespace(cost_meter=SimpleNamespace(turns=2, total_usd=0.3, has_cost_data=True),
                            log=SimpleNamespace(nodes=lambda: child_nodes),
                            model_ref=SimpleNamespace(raw="or:vendor/fallback"))
    _rollup_child_cost_into_parent(parent, child, agent_id="ag1", role="coder")
    kw = logged[0][1]
    ctx.check(f"heaviest model recorded, got {kw}", kw.get("model") == "or:vendor/big"
              and kw.get("provider") == "pb" and kw.get("route") == "or")
    child.log = SimpleNamespace(nodes=lambda: [])
    logged.clear()
    _rollup_child_cost_into_parent(parent, child, agent_id="ag2")
    ctx.check("no usage nodes -> the child's configured model",
              logged[0][1].get("model") == "or:vendor/fallback")


@test
def test_f84_session_stats_charge_the_childs_model(ctx: Ctx):
    from halo_harness.controller import compute_session_stats
    stats = compute_session_stats([
        {"type": "meta", "model": "or:vendor/parent"},
        {"type": "usage", "usage": {}, "cost_usd": 0.1},
        {"type": "usage", "usage": {}, "cost_usd": 0.4, "agent_id": "a", "model": "or:vendor/child"},
    ])
    pm = stats["per_model"]
    ctx.check(f"parent 0.1 / child 0.4, got {pm}",
              abs(pm["or:vendor/parent"]["cost_usd"] - 0.1) < 1e-9
              and abs(pm["or:vendor/child"]["cost_usd"] - 0.4) < 1e-9)


# ---- f85: stats cache schema + pruning ----------------------------------------

@test
def test_f85_an_old_cache_is_rebuilt_and_deleted_sessions_are_pruned(ctx: Ctx):
    from halo_harness import telemetry
    with scoped_home() as home:
        sdir = home / ".halo" / "sessions" / "proj"
        sdir.mkdir(parents=True)
        keep, gone = sdir / "keep.jsonl", sdir / "gone.jsonl"
        for p in (keep, gone):
            p.write_text(json.dumps({"type": "user", "content": []}) + "\n", encoding="utf-8")
        telemetry.scan(since="all", all_projects=True)
        cache = json.loads(telemetry.cache_path().read_text(encoding="utf-8"))
        ctx.check("the cache file is stamped with its schema", cache.get("__schema__") == telemetry.STATS_CACHE_SCHEMA)
        # Rewrite the cache in the pre-schema shape with a lie inside it.
        st = keep.stat()
        stale = {str(keep): {"size": st.st_size, "mtime": st.st_mtime,
                             "summary": {"session_id": "keep", "slug": "proj", "path": str(keep),
                                         "mtime": st.st_mtime, "size": st.st_size, "turns": 99}}}
        telemetry.cache_path().write_text(json.dumps(stale), encoding="utf-8")
        out = telemetry.scan(since="all", all_projects=True)
        turns = {s.session_id: s.turns for s in out}
        ctx.check(f"the old-schema entry was not served, got {turns}", turns.get("keep") == 1)
        gone.unlink()
        telemetry.scan(since="all", all_projects=True)
        cache = json.loads(telemetry.cache_path().read_text(encoding="utf-8"))
        ctx.check(f"the deleted session left the cache, got {sorted(cache)}",
                  str(gone) not in cache and str(keep) in cache)


# ---- f86: replay's non-prompt kinds -------------------------------------------

@test
def test_f86_replay_skips_every_kind_the_log_writes(ctx: Ctx):
    from halo_harness.replay import parse_turns
    kinds = ["continuation", "compaction_summary", "compaction_tail", "agent_notice", "job_notice", "steer"]
    with scoped_home() as home:
        p = home / "s.jsonl"
        nodes = [{"type": "user", "content": [{"type": "text", "text": "first real prompt"}]}]
        nodes += [{"type": "user", "kind": k, "content": [{"type": "text", "text": f"note {k}"}]} for k in kinds]
        nodes.append({"type": "user", "content": [{"type": "text", "text": "second real prompt"}]})
        p.write_text("".join(json.dumps(n) + "\n" for n in nodes), encoding="utf-8")
        turns = parse_turns(p)
        ctx.check(f"two real turns, got {[t.user_text for t in turns]}", [t.user_text for t in turns] == [
            "first real prompt", "second real prompt"])
        ctx.check("--turn 2 lands on the second prompt's own line", turns[1].node_line == len(kinds) + 1)


# ---- f89: U+2028 / U+2029 inside a record -------------------------------------

@test
def test_f89_replay_and_fork_keep_records_with_line_separators(ctx: Ctx):
    from halo_harness.replay import _truncate_fork, parse_turns
    with scoped_home() as home:
        p = home / "s.jsonl"
        nodes = [{"type": "user", "content": [{"type": "text", "text": f"one{LS}two"}]},
                 {"type": "assistant", "content": [{"type": "text", "text": f"a{PS}b"}]},
                 {"type": "user", "content": [{"type": "text", "text": "second"}]}]
        p.write_text("".join(json.dumps(n, ensure_ascii=False) + "\n" for n in nodes), encoding="utf-8")
        turns = parse_turns(p)
        ctx.check(f"both turns found, got {[(t.index, t.user_text) for t in turns]}",
                  len(turns) == 2 and turns[0].user_text == f"one{LS}two" and turns[1].node_line == 2)
        ctx.check("the assistant text with a separator survived", turns[0].assistant_text == f"a{PS}b")
        _truncate_fork(p, keep_lines=turns[1].node_line)
        kept = [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x]
        ctx.check(f"the fork keeps exactly the two earlier records, got {len(kept)}", len(kept) == 2)


@test
def test_f89_other_readers_keep_records_with_line_separators(ctx: Ctx):
    from halo_harness.agent.sessions import _read_nodes
    from halo_harness.history import append_history_entry, load_merged_history
    from halo_harness.textlines import split_lines
    ctx.check("split_lines cuts at newline only",
              split_lines(f"a{LS}b\nc\n") == [f"a{LS}b", "c"] and split_lines("x\ny", keepends=True) == ["x\n", "y"]
              and split_lines("") == [])
    with scoped_home() as home:
        p = home / "s.jsonl"
        p.write_text(json.dumps({"type": "meta", "title": f"t{LS}x"}, ensure_ascii=False) + "\n", encoding="utf-8")
        ctx.check("session node reader keeps the record", len(_read_nodes(p)) == 1)
        append_history_entry(f"line{LS}one{PS}two", str(home), session_id="s1", timestamp=5)
        entries = load_merged_history(str(home))
        ctx.check(f"history entry with separators reads back, got {entries}",
                  any(e.get("display") == f"line{LS}one{PS}two" for e in entries))


@test
def test_f89_recall_index_keeps_entries_with_line_separators(ctx: Ctx):
    from halo_harness import recall
    with scoped_home() as home:
        path = home / "embeddings.jsonl"
        recall._save_index(path, {"x": {"id": "x", "kind": "session", "title": f"a{LS}b", "mtime": 1.0, "vec": [1.0]}})
        loaded = recall._load_index(path)
        ctx.check(f"entry survives the round trip, got {loaded}", loaded.get("x", {}).get("title") == f"a{LS}b")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
