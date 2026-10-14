"""tests.test_orchestra_claims -- Halo 3.0.3.0 round R1: the claim log
(orchestra/claims.py): claim and refuse with the holder's name and expiry,
overlap by parent/child keys, TTL expiry and expire_stale, eight threads
racing for one key (one winner), steal only by the lead, release, the
writing/written steps, holder_for, the events lines, and the fold after
1000 appends. A fake clock drives every TTL; every run is a temp folder.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


class _Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def _run(lead=None):
    from halo_harness.orchestra.goal import Goal, new_run
    repo = Path(tempfile.mkdtemp(prefix="orch-claims-"))
    return new_run(repo, Goal(what="w", done_when="d", stop_when="s", files=["basket.py"]), lead_holder=lead)


@test
def test_claim_then_refuse_names_holder_and_expiry(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog, clock_text
    clock = _Clock()
    log = ClaimLog(_run(), clock=clock)
    a = log.claim("s1/a1", "basket.py#total", ttl_s=600)
    ctx.check("the first claim wins", a.ok and a.holder == "s1/a1" and a.state == "claimed")
    b = log.claim("s1/a2", "basket.py#total")
    ctx.check("a second holder is refused", not b.ok and b.holder == "s1/a1")
    ctx.check(f"the refusal names the holder and the time, got {b.text!r}",
              "s1/a1" in b.text and clock_text(clock.t + 600) in b.text and "ask the lead" in b.text)
    c = log.claim("s1/a2", "basket.py")
    ctx.check("the whole file overlaps a held function", not c.ok and c.conflict_key == "basket.py#total")
    d = log.claim("s1/a2", "basket.py#add_item")
    ctx.check("a different function is free", d.ok)
    renew = log.claim("s1/a1", "basket.py#total", ttl_s=60)
    ctx.check("re-claiming your own key renews it", renew.ok and log.active()["basket.py#total"].ttl_s == 60)
    ctx.check("active shows both", sorted(log.active()) == ["basket.py#add_item", "basket.py#total"])
    lines = log.entries()
    ctx.check("each line has the schema", set(lines[0]) == {"ts", "elapsed_s", "op", "holder", "key", "ttl_s", "note"})


@test
def test_parent_and_child_keys_overlap(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    log = ClaimLog(_run(), clock=_Clock())
    ctx.check("class claimed", log.claim("s/a", "basket.py#Basket").ok)
    ctx.check("its method is refused to another", not log.claim("s/b", "basket.py#Basket.total").ok)
    ctx.check("the same holder may claim inside its own class", log.claim("s/a", "basket.py#Basket.total").ok)
    ctx.check("held_by finds the most specific own claim",
              log.held_by("s/a", "basket.py#Basket.total").key == "basket.py#Basket.total"
              and log.held_by("s/a", "basket.py#Basket.refresh").key == "basket.py#Basket"
              and log.held_by("s/b", "basket.py#Basket") is None)


@test
def test_ttl_expiry_and_expire_stale(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    clock = _Clock()
    log = ClaimLog(_run(), clock=clock)
    log.claim("s/a", "basket.py#total", ttl_s=100)
    log.claim("s/b", "basket.py#add_item", ttl_s=1000)
    clock.t += 101
    ctx.check("past its TTL a claim is not active", sorted(log.active()) == ["basket.py#add_item"])
    ctx.check("another holder can take the expired key", log.claim("s/c", "basket.py#total").ok)
    clock.t += 2000
    expired = log.expire_stale()
    ctx.check(f"expire_stale writes both, got {expired}", sorted(expired) == ["basket.py#add_item", "basket.py#total"])
    ctx.check("expire lines are in the log", [e["op"] for e in log.entries()][-2:] == ["expire", "expire"])
    ctx.check("a second sweep finds nothing", log.expire_stale() == [])


@test
def test_writing_written_release_steps(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    clock = _Clock()
    log = ClaimLog(_run(), clock=clock)
    ctx.check("writing needs a claim", not log.mark_writing("s/a", "basket.py#total").ok)
    log.claim("s/a", "basket.py#total", ttl_s=100)
    clock.t += 90
    w = log.mark_writing("s/a", "basket.py#total")
    ctx.check("writing renews the TTL", w.ok and log.active()["basket.py#total"].state == "writing")
    clock.t += 50
    ctx.check("still live 140 s after the claim", "basket.py#total" in log.active())
    ctx.check("another holder cannot mark it", not log.mark_written("s/b", "basket.py#total").ok)
    ctx.check("written", log.mark_written("s/a", "basket.py#total").ok
              and log.active()["basket.py#total"].state == "written")
    r = log.release("s/a", "basket.py#total")
    ctx.check("release returns the released claim", r.ok and r.state == "released")
    ctx.check("released keys are not active", log.active() == {})
    ctx.check("releasing again is refused", not log.release("s/a", "basket.py#total").ok)


@test
def test_two_threads_race_one_winner(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    run = _run()
    results = []
    barrier = threading.Barrier(8)

    def worker(i):
        log = ClaimLog(run)
        barrier.wait()
        results.append(log.claim(f"s/a{i}", "basket.py#total"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for r in results if r.ok]
    ctx.check(f"exactly one of 8 wins, got {len(winners)}", len(winners) == 1)
    ctx.check("the log holds exactly one claim line", [e["op"] for e in ClaimLog(run).entries()] == ["claim"])
    ctx.check("the losers name the winner", all(r.holder == winners[0].holder for r in results if not r.ok))


@test
def test_steal_only_by_the_lead(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    log = ClaimLog(_run(lead="s/lead"), clock=_Clock())
    log.claim("s/a", "basket.py#Basket.total")
    no = log.steal("basket.py#Basket.total", "s/b", "stuck")
    ctx.check(f"a worker cannot steal, got {no.text!r}", not no.ok and "s/lead" in no.text)
    yes = log.steal("basket.py#Basket", "s/lead", "worker a is stuck")
    ctx.check("the lead steals the parent", yes.ok and yes.holder == "s/lead")
    active = log.active()
    ctx.check(f"the child claim is released by the steal, got {sorted(active)}", sorted(active) == ["basket.py#Basket"])
    unrecorded = ClaimLog(_run(), clock=_Clock())
    unrecorded.claim("s/a", "basket.py#x")
    ctx.check("with no lead recorded, a <session>/main holder is the lead",
              unrecorded.steal("basket.py#x", "s/main", "r").ok and not unrecorded.steal("basket.py#x", "s/a", "r").ok)


@test
def test_holder_for_session_folders(ctx: Ctx):
    from halo_harness.orchestra.claims import holder_for
    top = Path("/h/sessions/slug/abc123")
    ctx.check("top session is main", holder_for(top) == "abc123/main")
    ctx.check("a sub-agent", holder_for(top / "subagents" / "agent-x1") == "abc123/x1")
    ctx.check("a nested sub-agent", holder_for(top / "subagents" / "agent-x1" / "subagents" / "agent-y2") == "abc123/y2")
    ctx.check("an explicit agent id wins", holder_for(top, "w3") == "abc123/w3")


@test
def test_fold_after_1000_appends_and_events_lines(ctx: Ctx):
    from halo_harness.orchestra import events as run_events
    from halo_harness.orchestra.claims import ClaimLog
    clock = _Clock()
    run = _run()
    log = ClaimLog(run, clock=clock)
    for i in range(250):
        key = f"basket.py#f{i % 25}"
        holder = f"s/a{i % 25}"
        log.claim(holder, key)
        log.mark_writing(holder, key)
        log.mark_written(holder, key)
        if i < 225:
            log.release(holder, key)
        clock.t += 1
    for i in range(225, 250):
        log.claim(f"s/a{i % 25}", f"basket.py#f{i % 25}")  # renewals: 975 + 25 = 1000 lines
    ctx.check(f"1000 lines, got {len(log.entries())}", len(log.entries()) == 1000)
    ctx.check("a fresh reader folds the same", ClaimLog(run, clock=clock).active().keys() == log.active().keys())
    active = log.active()
    ctx.check(f"the last 25 claims stay held (renewed), got {len(active)}", len(active) == 25
              and all(c.state == "claimed" for c in active.values()))
    ctx.check("each key's holder is right", all(c.holder == "s/a" + c.key.split("#f")[1] for c in active.values()))
    ev = run_events.read(run)
    ctx.check(f"one claim event per op, got {len(ev)}", len(ev) == 1000 and all(e["kind"] == "claim" for e in ev))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
