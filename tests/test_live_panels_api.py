"""tests.test_live_panels_api -- Halo 3.0.5.0 round R4, the live panels' backend over real HTTP to an in-process
Studio (tests/helpers/studio_session_rig.py): the attention queue merges every source and an answer reaches the right
handler and is journaled; the spend caps are written and read back with today's costs. Hand-offs, recordings and the
replay: tests/test_live_panels_extras.py; conflicts: tests/test_live_panels_more.py.

Run: python -m tests.test_live_panels_api
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOW = time.time()


def _kinds(rows: list) -> list:
    return sorted({r["kind"] for r in rows})


@test
def test_attention_builds_one_queue_from_every_source(ctx: Ctx):
    from halo_harness.live import attention
    view = {"harnesses": [
        {"id": "L", "name": "me", "local": True, "sessions": [
            {"session_id": "s1", "title": "one", "pending": {"permission": ["p1"], "question": ["q1"], "plan": ["pl1"], "approval": ["ap1"]},
             "agents": [{"agent_id": "main", "state": "waiting"}, {"agent_id": "a2", "name": "tester", "state": "paused"}]},
            {"session_id": "s2", "title": "two", "agents": [{"agent_id": "main", "state": "running"},
                                                            {"agent_id": "w1", "name": "verifier", "state": "waiting"}]}]}]}
    asks = {("L", "s1", "p1"): {"kind": "permission", "agent_id": "main", "data": {"id": "p1", "name": "Bash", "input": {"command": "make clean"}}}}
    a = {"key": "L|s1|main", "harness": "L", "harness_name": "me", "session_id": "s1", "agent_id": "main", "name": "main"}
    b = {**a, "key": "L|s2|main", "session_id": "s2"}
    rows = attention.build(view, asks=asks,
                           orchestra=[{"run_id": "o1", "state": "stopped", "created": NOW - 60, "stop_reason": "the return cap"},
                                      {"run_id": "o0", "state": "finished", "created": NOW - 60}],
                           reached=[{"scope": "harness", "key": "L", "label": "me", "spent": 2.0, "cap": 1.0, "sessions": [["L", "s1"]]}],
                           conflicts=[{"repo": "shop", "file": "basket.py", "a": a, "b": b}],
                           now=NOW)
    ctx.check(f"every kind once, got {_kinds(rows)}", _kinds(rows) == sorted(
        ["permission", "question", "plan", "approval", "waiting", "paused", "orchestra_gate", "cap", "conflict"]))
    perm = next(r for r in rows if r["kind"] == "permission")
    ctx.check(f"the permission row says what is asked, its keys and the card id, got {perm}",
              perm["what"] == "Permission: Bash" and "make clean" in perm["detail"] and set(perm["keys"]) == {"a", "r", "s", "o"}
              and perm["target"] == {"request_id": "p1"} and perm["text_for"] == "r")
    ctx.check("an agent waiting with no card of its own is a row", any(r["kind"] == "waiting" and r["agent_id"] == "w1" for r in rows))
    ctx.check("the orchestra row carries the stop reason; a finished run is no row",
              [r["detail"] for r in rows if r["kind"] == "orchestra_gate"] == ["the return cap"])
    again = attention.build(view, asks=asks, seen={r["id"]: r["since"] for r in rows}, acks=[perm["id"]], now=NOW + 50)
    ctx.check("a set-aside row is gone and the rest keep their first-seen time",
              perm["id"] not in {r["id"] for r in again} and all(r["since"] == NOW for r in again))


@test
def test_the_stewards_note_is_a_row_that_sets_aside_and_opens_ollama(ctx: Ctx):
    """3.3.4.0 R4: a steward note with an error finding or a change raises an `ollama_steward` row (its first line);
    `a` sets it aside (journal kind ack, as orchestra_gate), `o` opens the Ollama panel."""
    import tempfile
    from types import SimpleNamespace
    from halo_harness.live import attention
    from halo_harness.ollama_steward import notes
    from halo_harness.studio.live_answer import act
    home = Path(tempfile.mkdtemp(prefix="r4_attention-"))
    notes.append(home, "note", "qwen3-coder:30b on pc reloaded 9 times: two halos sent it two windows",
                 lines=["qwen3-coder:30b on pc reloaded 9 times: two halos sent it two windows", "one window now"],
                 attention=True)
    rows = [r for r in attention.build({"harnesses": []}, home=home, now=NOW) if r["kind"] == "ollama_steward"]
    ctx.check(f"one row with the note's first line, got {[r['what'] for r in rows]}",
              len(rows) == 1 and rows[0]["what"].startswith("qwen3-coder:30b on pc reloaded") and rows[0]["detail"] == "one window now")
    watcher = SimpleNamespace(acks=set(), home=home)
    status, body, label = act(SimpleNamespace(state_dir=home), watcher, rows[0], "o", "")
    ctx.check(f"o opens the Ollama panel, got {body}", status == 200 and body["open"]["panel"] == "ollama")
    status, body, label = act(SimpleNamespace(state_dir=home), watcher, rows[0], "a", "")
    ctx.check(f"a sets it aside, got {status} {body} {label!r}", status == 200 and body == {"set_aside": True}
              and rows[0]["id"] in watcher.acks and label == "set aside")


def _wait(fn, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.1)
    return None


def _seed_gates(rig) -> Path:
    from halo_harness.orchestra import jsonl
    orch = rig.proj / ".halo" / "orchestra" / "20261014-090000-ab12"
    orch.mkdir(parents=True)
    jsonl.write_json(orch / "goal.json", {"what": "split the basket module"})
    jsonl.write_json(orch / "run.json", {"created": NOW - 120})
    jsonl.write_json(orch / "report.json", {"run_id": orch.name, "status": "stopped", "cost_usd": 0.1,
                                            "stop_reason": "lane 2 reached the return cap (3) and the tests still fail"})
    return orch


@test
def test_the_queue_over_the_rig_and_answers_reach_their_handlers(ctx: Ctx):
    from halo_harness.live import journal
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        _seed_gates(rig)
        from halo_harness.studio.live_watch import watcher_for
        watcher_for(rig.server, rig.state).tick()  # the GET serves a snapshot up to 1 s old; build it after the seed
        status, got = rig.api("GET", "live/attention")
        rows = got.get("rows") or []
        ctx.check(f"the orchestra gate is a row, got {_kinds(rows)}", status == 200 and "orchestra_gate" in _kinds(rows)
                  and got["count"] == len(rows))
        og = next(r for r in rows if r["kind"] == "orchestra_gate")
        ctx.check("an orchestra gate row says why it stopped", "return cap" in og["detail"])
        ctx.check("a key the row does not take is a 422", rig.api("POST", "live/attention/answer", {"id": og["id"], "key": "x"})[0] == 422)
        ctx.check("an unknown row is a 404", rig.api("POST", "live/attention/answer", {"id": "nope", "key": "a"})[0] == 404)
        status, res = rig.api("POST", "live/attention/answer", {"id": og["id"], "key": "a"})
        left = {r["id"] for r in rig.api("GET", "live/attention")[1]["rows"]}
        ctx.check(f"set aside: the orchestra row is gone, got {status} {res}", status == 200 and og["id"] not in left)
        rows_j = journal.read(rig.state, NOW - 60)
        decisions = [r for r in rows_j if r["kind"] == "decision"]
        ctx.check(f"the decision is journaled with who answered, got {[(d['row_kind'], d['by']) for d in decisions]}",
                  {d["row_kind"] for d in decisions} >= {"orchestra_gate"} and all(d["by"] == "you@studio" for d in decisions)
                  and any(r["kind"] == "ack" for r in rows_j))


@test
def test_the_caps_are_written_and_read_back_with_todays_costs(ctx: Ctx):
    from tests.helpers.studio_session_rig import StudioSessionRig
    with StudioSessionRig() as rig:
        status, got = rig.api("POST", "live/caps", {"per_harness_usd_per_day": 5, "per_project_usd_per_day": None})
        cfg = json.loads((rig.state / "config.json").read_text(encoding="utf-8"))["caps"]
        ctx.check(f"written as caps.*, got {status} {cfg}", status == 200 and cfg["per_harness_usd_per_day"] == 5
                  and cfg.get("per_project_usd_per_day") is None and got["caps"]["per_harness_usd_per_day"] == 5)
        ctx.check("the keys are this harness's and a project's", got["keys"] == ["per_harness_usd_per_day", "per_project_usd_per_day"])
        ctx.check("a negative cap is a 422", rig.api("POST", "live/caps", {"per_harness_usd_per_day": -1})[0] == 422)
        costs = rig.api("GET", "live/costs")[1]
        from halo_harness.live.session_cost import today  # 3.4.0.1: this harness's finished PAST_SID counts when it started today
        mine = today(rig.state)["usd"]
        ctx.check(f"costs: this harness's total and per project, under the cap, got {costs.get('total')}",
                  abs(costs["total"] - mine) < 1e-9 and mine in (0.0, 0.02) and not costs["reached"]
                  and all(p["key"] == "shop" for p in costs["projects"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="live panels api tests"))
