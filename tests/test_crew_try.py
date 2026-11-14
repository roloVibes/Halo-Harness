"""tests.test_crew_try -- Halo 3.6.0.0 R1: Try it runs a real agent (halo_harness/crew/trial.py, trial_run.py), on the
repo's fake provider (the mock upstream; no network, no local model server):

1. the cost is said before the run (GET crew/estimate); the run is `halo -p` as the agent, in a throwaway git worktree
   of the project, removed when it ends: its reply, the tools it used, its time, where it ran; `crew` frames on the feed;
2. its careful mode is honoured: asking before changes, a command that writes is answered no and listed (and the
   project is untouched); working on its own, the same command runs (in the copy only);
3. Stop ends a run that waits on its model;
4. a run that ends unseen is an Attention row (`crew_try`) that opens the agent; seen (or set aside) it goes.
Run: python -m tests.test_crew_try
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import TRY_REPLY, CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _body(rig, model: str = "auto", careful: str = "ask-changes", uses=("read",)) -> dict:
    return {"format": "agent/1", "name": "my-reviewer", "does": "Reviews the basket.", "model": model, "uses": list(uses), "careful": careful}


def _wait(rig, tid: str, timeout: float = 120) -> dict:
    end = time.time() + timeout
    rec: dict = {}
    while time.time() < end:
        _st, got = rig.api("GET", f"crew/try/{tid}")
        rec = got.get("try") or {}
        if rec.get("state") not in ("running", "stopping"):
            return rec
        time.sleep(0.3)
    return rec


@test
def test_a_run_on_a_throwaway_copy(ctx: Ctx):
    from halo_harness.studio.events import bridge_for
    with CrewRig() as rig:
        server = rig.studio()
        frames: list = []
        bridge_for(server).taps.append(lambda f: f.get("event") == "crew" and frames.append(f))
        st, est = rig.api("GET", "crew/estimate?model=auto")
        ctx.check(f"the cost is said before: Auto says when it is known, got {est}", st == 200 and est["line"].startswith("Auto picks the model"))
        st, est = rig.api("GET", "crew/estimate?model=or:mock/crew-try")
        ctx.check(f"a model's typical task, got {est}", est["line"].startswith("one typical task"))
        st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig), "request": "Review the basket"})
        ctx.check(f"it starts, got {st} {r.get('try', {}).get('state')}", st == 200 and r["try"]["state"] == "running")
        rec = _wait(rig, r["try"]["id"])
        ctx.check(f"done with the model's reply, got {rec.get('state')} {rec.get('reply')!r} {rec.get('error')!r}", rec.get("state") == "done" and rec.get("reply") == TRY_REPLY)
        ctx.check(f"the tools it used, got {rec.get('used')}", rec.get("used") == {"Glob": 1})
        ctx.check(f"where it ran, got {rec.get('where')!r}", rec.get("where", "").startswith("a throwaway copy of shop (a git worktree"))
        trees = subprocess.run(["git", "worktree", "list"], cwd=str(rig.proj), capture_output=True, text=True).stdout.strip().splitlines()
        ctx.check(f"the copy is gone, its worktree too, got {trees}", len(trees) == 1)
        ctx.check(f"its record on the feed, got {len(frames)} frames", len(frames) >= 2 and frames[-1]["data"]["try"]["state"] == "done")


@test
def test_careful_is_honoured(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, ScriptedTurns
    from tests.helpers.session_rig import text_step, tool_step
    SCENARIOS["crew-write"] = ScriptedTurns([tool_step(("Bash", {"command": "echo made > made.txt", "description": "make a file"}, "call_w1")),
                                             text_step("I tried to make a file.")])
    try:
        with CrewRig() as rig:
            rig.studio()
            _st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig, "or:mock/crew-write", uses=("read", "bash")), "request": "make a file"})
            rec = _wait(rig, r["try"]["id"])
            ctx.check(f"asks before changes: the command is answered no and listed, got {rec.get('denied')}",
                      rec.get("state") == "done" and len(rec.get("denied") or []) == 1 and rec["denied"][0].startswith("Bash"))
            ctx.check("the project is untouched", not (rig.proj / "made.txt").exists())
            _st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig, "or:mock/crew-write", "own", ("read", "bash")), "request": "make a file"})
            rec = _wait(rig, r["try"]["id"])
            ctx.check(f"works on its own: it ran, nothing asked, got {rec.get('denied')} {rec.get('used')}",
                      rec.get("denied") == [] and rec.get("used") == {"Bash": 1})
            ctx.check("and still only in the copy", not (rig.proj / "made.txt").exists())
    finally:
        SCENARIOS.pop("crew-write", None)


@test
def test_stop_ends_a_run(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS
    from tests.helpers.session_rig import text_step
    gate = threading.Event()

    def held(handler, body):
        gate.wait(60)
        from tests.helpers.mock_openai import _finish
        _finish(handler, text_step("late"))
    SCENARIOS["crew-hold"] = held
    try:
        with CrewRig() as rig:
            rig.studio()
            _st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig, "or:mock/crew-hold"), "request": "wait"})
            tid = r["try"]["id"]
            end = time.time() + 60
            while time.time() < end and rig.api("GET", f"crew/try/{tid}")[1]["try"].get("now") != "running":
                time.sleep(0.2)
            st, got = rig.api("POST", f"crew/try/{tid}/stop")
            rec = _wait(rig, tid, 60)
            ctx.check(f"Stop: stopped by you, got {st} {rec.get('state')}", st == 200 and rec.get("state") == "stopped")
    finally:
        gate.set()
        SCENARIOS.pop("crew-hold", None)


@test
def test_an_unseen_end_is_an_attention_row(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        _st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig), "request": "Review the basket"})
        tid = r["try"]["id"]
        rec = _wait(rig, tid)
        ctx.check(f"the run ended well, got {rec.get('state')} {rec.get('error')!r}", rec.get("state") == "done")
        time.sleep(1.2)
        rows = [x for x in rig.api("GET", "live/attention")[1]["rows"] if x["kind"] == "crew_try"]
        ctx.check(f"one crew_try row, set aside or open, got {[(x['what'], x['keys']) for x in rows]}",
                  len(rows) == 1 and rows[0]["what"].startswith("Try it finished: my-reviewer") and set(rows[0]["keys"]) == {"a", "o"})
        st, got = rig.api("POST", "live/attention/answer", {"id": rows[0]["id"], "key": "o"})
        ctx.check(f"open: the Agents tab on that agent and run, got {got.get('open')}",
                  got.get("open") == {"section": "agents", "view": "crew", "agent": "my-reviewer", "try": tid})
        rig.api("POST", f"crew/try/{tid}/seen")
        time.sleep(1.2)
        ctx.check("seen: the row is gone", not [x for x in rig.api("GET", "live/attention")[1]["rows"] if x["kind"] == "crew_try"])
        _st, r = rig.api("POST", "crew/try", {"kind": "agent", "body": _body(rig), "request": "again"})
        _wait(rig, r["try"]["id"])
        time.sleep(1.2)
        row = next(x for x in rig.api("GET", "live/attention")[1]["rows"] if x["kind"] == "crew_try")
        rig.api("POST", "live/attention/answer", {"id": row["id"], "key": "a"})
        ctx.check("set aside: the run is marked seen", rig.api("GET", f"crew/try/{r['try']['id']}")[1]["try"]["seen"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
