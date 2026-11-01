"""tests.test_pool_claims -- Halo 3.3.8.0 R3 deliverable 4: claims with a lease (local_sched/claims_file.py `until` +
`renew`, local_sched/lease.py the heartbeat, host/ops_claim.py `lease_s` + `renew`, host/residency.claims,
local_pool/claims.py the pool's claim on every member); no model call, never a request beyond 127.0.0.1:

1. the file: a claim past its `until` is not read (an expired claim is not a claim), `expired=True` shows it, renew
   moves only live leased rows (a dead one stays dead), drop still finds an expired row, any write clears the dead;
2. the host: a claim with `lease_s` carries `until` in `GET residency`; past it residency.claims, ops_claim.held and
   the peer's reserve.claims all leave it out; `renew` of the peer's own claim is not queued under `ask`;
3. the pool: Warm claims every member with a lease; the heartbeat renews them on the host and here; with no heartbeat
   (a killed Studio) they expire within the lease; a bundle held by a halo process (Studio's tick) gets the same lease
   and the heartbeat, released with it (where the lease changed R5).
Run: python -m tests.test_pool_claims
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome  # noqa: E402
from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BUNDLE = f"pool:{QWEN}"


@test
def test_the_lease_in_the_file(ctx: Ctx):
    from halo_harness.local_sched import claims_file as CF
    with PoolHome() as h:
        p = CF.local_file(h.state)
        now = time.time()
        CF._write(p, [{"bundle": "old", "host": "pc", "model": "m1", "gb": 4.0, "until": now - 5},
                      {"bundle": "live", "host": "pc", "model": "m2", "gb": 2.0, "until": now + 60},
                      {"bundle": "cli", "host": "pc", "model": "m3", "gb": 1.0}])
        ctx.check(f"the expired claim is not read, got {[r['bundle'] for r in CF.read(p)]}",
                  [r["bundle"] for r in CF.read(p)] == ["live", "cli"])
        ctx.check("expired=True shows every row", [r["bundle"] for r in CF.read(p, expired=True)] == ["old", "live", "cli"])
        got = CF.renew(p, "live", now + 300)
        ctx.check(f"renew moves the live leased row, got {got}", len(got) == 1 and got[0]["until"] == round(now + 300, 3))
        ctx.check("renew of a claim with no lease renews nothing", CF.renew(p, "cli", now + 300) == [])
        ctx.check("the write cleared the dead row", [r["bundle"] for r in CF.read(p, expired=True)] == ["live", "cli"])
        CF.put(p, {"bundle": "gone", "host": "pc", "model": "m5", "gb": 1.0, "until": time.time() + 0.2})
        time.sleep(0.3)
        ctx.check("an expired claim stays dead: renew finds nothing", CF.renew(p, "gone", time.time() + 300) == []
                  and "gone" not in [r["bundle"] for r in CF.read(p)])
        CF.put(p, {"bundle": "late", "host": "pc", "model": "m4", "gb": 1.0, "until": time.time() + 0.2})
        time.sleep(0.3)
        gone = CF.drop(p, "late")
        ctx.check(f"drop still finds an expired row (its release lands), got {gone}", [r["bundle"] for r in gone] == ["late"])
        ctx.check(f"pool.claim_lease_s, got {CF.lease_s()}", CF.lease_s() == 120.0)
        h.config(**{"pool.claim_lease_s": 30})
        ctx.check("the lease is configurable", CF.lease_s() == 30.0)


@test
def test_the_host_reads_only_live_claims(ctx: Ctx):
    from halo_harness.host import residency
    from halo_harness.host.ops_claim import held
    from halo_harness.local_sched import claims_file as CF
    from tests.helpers.host_act_rig import ActRig, PeerRig
    with PeerRig() as rig:
        st, got = rig.act("control", "claim", {"model": "qwen3.5:9b", "gb": 6.0, "bundle": "b1", "lease_s": 60})
        _s, res = rig.get("residency")
        c = (res.get("claims") or [{}])[0]
        ctx.check(f"a claim with lease_s carries until, got {st} {c}", st == 200 and c.get("bundle") == "b1"
                  and abs(float(c.get("until") or 0) - (time.time() + 60)) < 5)
        later = float(c["until"]) + 1
        ctx.check("past it: residency.claims leaves it out", residency.claims(rig.home, now=later) == []
                  and len(residency.claims(rig.home)) == 1)
        CF.put(CF.host_file(rig.home), {**c, "until": time.time() - 1})
        from halo_harness.local_sched.reserve import claims, forget
        from halo_harness.providers.ollama import OllamaHost
        forget()
        ctx.check("expired: held() and the peer's reserve.claims leave it out", held(rig.home, "pc", "qwen3.5:9b") is None
                  and claims(OllamaHost(name="pc", url=rig.peer_url), state_dir=rig.peer) == [])
    with ActRig(cap="ask", grants=("control",)) as rig:
        CF.put(CF.host_file(rig.home), {"bundle": "b2", "host": "pc", "model": "qwen3.5:9b", "gb": 6.0,
                                        "by": "carol@peer", "until": time.time() + 30})
        st, got = rig.act("control", "renew", {"bundle": "b2", "lease_s": 90})
        ctx.check(f"renew under ask: not queued, renewed, got {st} {got}", st == 200 and got.get("renewed") == 1
                  and abs(float(got["until"]) - (time.time() + 90)) < 5)
        st, got = rig.act("control", "claim", {"model": "qwen3.5:9b", "gb": 1.0, "bundle": "b3"})
        ctx.check(f"a new claim under ask is still queued, got {st}", st == 202)


@test
def test_the_pools_claims_and_the_heartbeat(ctx: Ctx):
    from halo_harness.host import residency
    from halo_harness.local_sched import claims_file as CF, lease
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ctx.check(f"warmed, got {got['ok']} {got['lines'][-3:]}", got["ok"])
        on_pc = [c for c in residency.claims(rig.home) if c["bundle"] == BUNDLE]
        here = [c for c in CF.read(CF.local_file(rig.peer)) if c["bundle"] == BUNDLE]
        ctx.check(f"a claim on every member, each with a lease, got {on_pc} {here}", len(on_pc) == 1 and len(here) == 1
                  and on_pc[0]["gb"] > 19 and here[0]["host"] == "me" and all(c.get("until") for c in on_pc + here))
        ctx.check(f"the heartbeat holds it, got {lease.held()}", lease.held() == [BUNDLE])
        t0, t1 = float(on_pc[0]["until"]), float(here[0]["until"])
        time.sleep(0.6)
        lines = lease.beat()[BUNDLE]  # the host renews on its own clock: now + the lease there
        on_pc = [c for c in residency.claims(rig.home) if c["bundle"] == BUNDLE]
        here = [c for c in CF.read(CF.local_file(rig.peer)) if c["bundle"] == BUNDLE]
        ctx.check(f"a beat renews both, got {lines} {t0} -> {on_pc[0]['until']}", float(on_pc[0]["until"]) >= t0 + 0.5
                  and float(here[0]["until"]) >= t1 + 0.5 and any("renewed on pc" in ln for ln in lines))
        lease.reset()  # the controller dies: nothing renews
        after = float(on_pc[0]["until"]) + 1
        ctx.check("a killed controller's claims end with the lease", [c for c in residency.claims(rig.home, now=after)
                                                                        if c["bundle"] == BUNDLE] == []
                  and [c for c in CF.read(CF.local_file(rig.peer), now=after) if c["bundle"] == BUNDLE] == [])


@test
def test_a_process_held_bundle_gets_the_lease(ctx: Ctx):
    from halo_harness.local_sched import lease
    from halo_harness.local_sched.reserve_act import claim, release
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.host_act_rig import PeerRig
    with PeerRig() as rig:
        lease.reset()
        host = OllamaHost(name="pc", url=rig.peer_url)
        ok, lines, _v = claim("bulk-worker", host=host, holder="process", cwd=Path(rig.rig.root_p))
        _s, res = rig.get("residency")
        c = (res.get("claims") or [{}])[0]
        ctx.check(f"held by a process: the host's claim has a lease, got {ok} {c.get('until')}", ok
                  and isinstance(c.get("until"), (int, float)) and c["until"] > time.time() + 60)
        ctx.check(f"the heartbeat holds it, got {lease.held()}", lease.held() == ["bundle:bulk-worker"])
        time.sleep(0.6)
        beat = lease.beat()["bundle:bulk-worker"]
        _s, res = rig.get("residency")
        ctx.check(f"renewed there, got {beat} {res['claims'][0]['until']} vs {c['until']}",
                  float(res["claims"][0]["until"]) >= float(c["until"]) + 0.5 and "1 local" in beat)
        ok, lines = release("bulk-worker", cwd=Path(rig.rig.root_p))
        ctx.check(f"released: no heartbeat left, got {lease.held()}", ok and lease.held() == [])
        ok, lines, _v = claim("bulk-worker", host=host, cwd=Path(rig.rig.root_p))
        _s, res = rig.get("residency")
        ctx.check(f"from the CLI (keep): no lease, got {res['claims'][0].get('until')}", ok
                  and res["claims"][0].get("until") is None and lease.held() == [])
        release("bulk-worker", cwd=Path(rig.rig.root_p))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
