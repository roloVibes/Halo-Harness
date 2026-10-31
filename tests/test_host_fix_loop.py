"""tests.test_host_fix_loop -- Halo 3.3.7.0 R2 deliverable 3: the guards and the fix loop (host/guards.py,
host/verify.py) on a fake Ollama (tests/helpers/host_act_rig.py):

1. the guards' lines: a profile fix without evidence (422, a dry preview needs none), one change at a time per host
   (409), the cooldown per host|model (host.cooldown_s), the rate limit per peer (host.changes_per_hour, 429); a
   person's warm with no evidence is not a fix and is not held;
2. a change that improves is kept: "set_num_ctx 32768 on pc|qwen3-coder:30b: 16 -> 188 tok/s, no trims -- kept",
   the verdict in its row, an `event` frame, `GET changes`;
3. a change that worsens is reverted and says so (the profile goes back, the change row is reverted);
4. the window ends by calls (host.verify_calls) and by time (host.verify_s: no calls, nothing measured, kept).
Run: python -m tests.test_host_fix_loop
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import BIG, CODER, SMALL, ActRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
EV = {"finding": "cpu-spill-1a2b3c"}


def _fix(rig, model=BIG, value=16384, field="set_num_ctx"):
    return rig.act("control", field, {"model": model, "value": value}, evidence=EV, why="the card spills")


def _close(rig, later: float = 700.0):
    from halo_harness.host import verify
    return verify.tick(rig.svc, now=time.time() + later)


@test
def test_the_guards_lines(ctx: Ctx):
    with ActRig() as rig:
        status, got = rig.act("control", "set_num_ctx", {"model": BIG, "value": 16384})
        ctx.check(f"no evidence: 422, one line, got {status} {got}", status == 422
                  and got["error"].startswith("a fix names the finding it acts on") and len(got["error"].splitlines()) == 1)
        status, got = rig.act("control", "set_num_ctx", {"model": BIG, "value": 16384}, dry=True)
        ctx.check("a dry preview needs no evidence", status == 200 and got["dry"] is True)
        status, got = _fix(rig)
        ctx.check(f"the first fix lands, got {status} {got.get('say')}", status == 200 and got["change_id"])
        status, got = _fix(rig, CODER, 8192)
        ctx.check(f"one change at a time per host: 409, got {status} {got}", status == 409
                  and got["error"].startswith("one change at a time: set_num_ctx landed") and "verifying (0 of 5 calls" in got["error"])
        status, got = rig.act("control", "warm", {"model": SMALL, "num_ctx": 8192})
        ctx.check(f"a person's warm is not a fix: not held, got {status}", status == 200)
        _close(rig)
        status, got = _fix(rig, BIG, 12288)
        ctx.check(f"the cooldown on the same host|model, got {status} {got}", status == 409 and got["error"].startswith(
            "cooldown: set_num_ctx changed pc|qwen3.8:27b") and "host.cooldown_s is 120" in got["error"])
        status, got = _fix(rig, CODER, 8192)
        ctx.check(f"another model on that host is not in its cooldown, got {status}", status == 200)
    with ActRig() as rig:
        rig.rig.set_peer(**{"host.changes_per_hour": 2, "host.cooldown_s": 0})
        for model in (BIG, CODER):
            status, _got = _fix(rig, model, 8192)
            _close(rig)
        time.sleep(0.3)  # the audit lines are written as the answers go out
        status, got = _fix(rig, SMALL, 8192)
        ctx.check(f"the rate limit per peer: 429, got {status} {got}", status == 429
                  and got["error"].startswith("rate limit: carol@peer landed 2 fixes in the last hour")
                  and "host.changes_per_hour 2" in got["error"])


@test
def test_a_change_that_improves_is_kept(ctx: Ctx):
    from halo_harness.host import verify
    from halo_harness.host.jobs import of
    from halo_harness.ollama_steward import changes
    with ActRig() as rig:
        rig.lines(CODER, 10, tok_s=16.0, ago=600)
        status, got = _fix(rig, CODER, 32768)
        ctx.check(f"set_num_ctx 32768 for the coder lands, got {status} {got}", status == 200)
        before = got.get("before") or {}
        ctx.check(f"before: the ledger's median tok/s over the last calls, got {before}", before.get("tok_s") == 16.0
                  and before.get("calls") == 10)
        rig.lines(CODER, 4, tok_s=188.0, ago=-1)
        ctx.check("four of five calls: still verifying", verify.tick(rig.svc) == [])
        rig.lines(CODER, 1, tok_s=188.0, ago=-2)
        closed = verify.tick(rig.svc)
        line = closed[0]["line"] if closed else ""
        ctx.check(f"the window ends by calls: the brief's line, got {line!r}", line ==
                  "set_num_ctx 32768 on pc|qwen3-coder:30b: 16 -> 188 tok/s, no trims -- kept")
        frames = [f for f in of(rig.svc).bus.frames if f["type"] == "event" and f["data"].get("kind") == "fix-verdict"]
        ctx.check("an event frame with the line", frames and frames[-1]["data"]["say"] == line)
        status, rows = rig.get("changes")
        hit = next((r for r in rows.get("changes") or [] if r["id"] == got["change_id"]), {})
        ctx.check(f"GET changes: the verdict, before and after, got {hit.get('verdict')}", hit.get("verdict") == "kept"
                  and hit.get("verify_line") == line and hit.get("after_m", {}).get("tok_s") == 188.0)
        ctx.check("the change stays in force", any(r["id"] == got["change_id"] for r in changes.in_force(rig.home)))


@test
def test_a_change_that_worsens_is_reverted(ctx: Ctx):
    from halo_harness.host import verify
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.profiles import all_profiles
    with ActRig() as rig:
        rig.lines(BIG, 10, tok_s=40.0, ago=600)
        status, got = _fix(rig, BIG, 8192)
        rig.lines(BIG, 5, tok_s=38.0, trimmed=True, ago=-1)
        closed = verify.tick(rig.svc)
        line = closed[0]["line"] if closed else ""
        ctx.check(f"worse (more trims): reverted, and it says so, got {line!r}", "-- reverted" in line
                  and "5 trims" in line and "took num_ctx" in line)
        ctx.check("the profile went back", "num_ctx" not in (all_profiles().get("pc|qwen3.8:27b") or {}))
        ctx.check("the change row is reverted", not any(r["id"] == got["change_id"] for r in changes.in_force(rig.home)))


@test
def test_the_window_ends_by_time(ctx: Ctx):
    from halo_harness.host import verify
    with ActRig() as rig:
        rig.rig.set_peer(**{"host.verify_s": 60, "host.verify_calls": 3})
        status, got = _fix(rig, BIG, 8192)
        row = verify.open_on(rig.home, "pc")
        ctx.check(f"the window: host.verify_calls and host.verify_s, got {row}", row["need_calls"] == 3
                  and 59 <= row["ends_at"] - row["at"] <= 61)
        ctx.check("before its time, nothing closes", verify.tick(rig.svc, now=time.time() + 30) == [])
        closed = verify.tick(rig.svc, now=time.time() + 61)
        ctx.check(f"by time, no calls: kept, nothing measured, got {closed[0]['line'] if closed else None!r}", closed
                  and closed[0]["verdict"] == "kept" and "no calls in 60 s to judge by" in closed[0]["line"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
