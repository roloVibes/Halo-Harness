"""tests.test_bundle_reserve -- Halo 3.3.7.0 R5: reservations (local_sched/reserve.py, reserve_act.py, claims_file.py;
host/ops_claim.py and the host's invariants; plans/local-model-fit-brief.md L2), locally (tests/helpers/bundle_rig) and
through the R1 host rig (R2's PeerRig: a real halo host on 127.0.0.1:0 over a fake Ollama):

1. `halo pack on meta-glasses` (ready) installs and enables it in the scratch home, claims lfm3:1.7b (1.2 GB) in
   <state>/ollama/claims.json, writes keep_alive -1 on pc|lfm3:1.7b as a `keep` change, and says the budget line;
   `halo local hosts`, GET local/warm-set and GET local/loads carry "1.2 GB reserved for meta-glasses; 20.8 GB free
   for tasks"; a bundle that is not ready is not turned on (nothing written);
2. the scheduler's pivot never evicts a reserved model, and a load that would breach a claim is queued with the
   claim and the numbers -- no load, no unload sent;
3. `halo pack off` releases it, puts keep_alive back and disables the pack;
4. Studio's tick holds it in this process (until-restart); at_exit releases it; a claim whose holder is gone counts
   for nothing;
5. through a halo host: the claim lands on the host (GET residency answers it), the host refuses a breaching warm and
   an unload of the reserved model with the claim's line, and `off` releases it there.
Run: python -m tests.test_bundle_reserve
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import LFM, BundleHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, ps_row  # noqa: E402

test, TESTS = new_registry()
LINE = "1.2 GB reserved for meta-glasses; 20.8 GB free for tasks"


def _claims(h):
    from halo_harness.local_sched import claims_file as CF
    return CF.read(CF.local_file(h.state))


@test
def test_on_claims_and_says_the_budget_line(ctx: Ctx):
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.profiles import lookup
    with BundleHome() as h:
        code, out, err = h.pack("on", "meta-glasses")
        ctx.check(f"on, got {code} {out!r} {err!r}", code == 0 and "reserved lfm3:1.7b on pc for meta-glasses: 1.2 GB held"
                  in out and f"{LINE} on pc" in out and "held until: halo pack off meta-glasses" in out)
        rows = _claims(h)
        ctx.check(f"one claim row, kept until off, got {rows}", len(rows) == 1 and rows[0]["model"] == LFM
                  and rows[0]["gb"] == 1.2 and rows[0]["holder"] == "keep" and rows[0]["via"] == "local")
        ctx.check("keep_alive -1 on the reserved model's profile", (lookup("pc", LFM) or {}).get("keep_alive") == -1)
        ch = [r for r in changes.in_force(h.state) if r["key"] == f"pc|{LFM}"]
        ctx.check(f"a keep change, recorded, got {ch}", len(ch) == 1 and ch[0]["scope"] == "keep" and ch[0]["by"] == "bundle"
                  and rows[0]["change_id"] == ch[0]["id"])
        from halo_harness.packs import state as S
        rec = S.entry("meta-glasses", h.state) or {}
        ctx.check(f"installed and enabled in the scratch home, got {rec}", rec.get("enabled") is True
                  and str(h.state) in str(rec.get("root")))
        from halo_harness.local_tab_cli import hosts_lines
        ctx.check("halo local hosts says it", f"  reserved: {LINE}" in hosts_lines(h.state))
        status, body = h.studio("GET", "local/warm-set", query={"host": "pc"})
        ctx.check(f"the Hosts card's line, got {status} {body}", status == 200 and body.get("claims_line") == LINE)
        status, body = h.studio("GET", "local/loads", query={"session": "s1"})
        ctx.check(f"the Cost panel's, got {body.get('claims')}", body.get("claims") == [{"host": "pc", "line": LINE}])
        code, out, _e = h.pack("list", "--bundles")
        ctx.check("list --bundles ticks it", any(ln.startswith("[x] meta-glasses") for ln in out.splitlines()))
    with BundleHome(lfm=False) as h:
        code, _o, err = h.pack("on", "meta-glasses")
        ctx.check(f"not ready: not turned on, the verdict's line, got {code} {err!r}", code == 1
                  and "meta-glasses is not turned on: needs 1 download" in err)
        from halo_harness.packs import state as S
        ctx.check("nothing written", _claims(h) == [] and S.entry("meta-glasses", h.state) is None)


@test
def test_the_pivot_never_evicts_a_reserved_model(ctx: Ctx):
    from halo_harness.local_sched.pivot import plan, run_now
    with BundleHome(loaded=[ps_row(LFM, 1.2, 8192)]) as h:
        h.pack("on", "meta-glasses")
        said: list = []
        got = run_now(plan(h.host, LFM, CODER, window=32768), say=said.append, host=h.host)
        ctx.check(f"queued, the claim named, got {got} {said}", not got["ok"] and got.get("queued")
                  and "lfm3:1.7b is reserved for meta-glasses on pc (1.2 GB held)" in said[-1])
        ctx.check(f"no unload or load sent, got {h.mock.generated}", h.mock.generated == [])
    with BundleHome() as h:
        h.claim("voice", LFM, 4.0)
        said = []
        got = run_now(plan(h.host, None, BIG, window=32768), say=said.append, host=h.host)
        ctx.check(f"a breaching load is queued with the numbers, got {said}", not got["ok"] and said[-1] ==
                  "qwen3.8:27b would need 18.9 GB with voice's 4.0 GB held; 18.0 GB free -- queued behind voice "
                  "(halo pack off voice frees it)")
        ctx.check("nothing loaded", h.mock.generated == [])


@test
def test_off_releases_and_puts_keep_alive_back(ctx: Ctx):
    from halo_harness.ollama_steward.profiles import lookup
    from halo_harness.packs import state as S
    with BundleHome() as h:
        h.pack("on", "meta-glasses")
        code, out, err = h.pack("off", "meta-glasses")
        ctx.check(f"off, got {code} {out!r} {err!r}", code == 0 and "released lfm3:1.7b on pc (1.2 GB)" in out
                  and "disabled meta-glasses" in out)
        ctx.check("the claim is gone", _claims(h) == [])
        ctx.check("keep_alive put back", "keep_alive" not in (lookup("pc", LFM) or {}))
        ctx.check("the pack disabled", (S.entry("meta-glasses", h.state) or {}).get("enabled") is False)
        status, body = h.studio("GET", "local/warm-set", query={"host": "pc"})
        ctx.check("no reservation line", body.get("claims_line") == "")


@test
def test_studio_holds_it_in_this_process(ctx: Ctx):
    from halo_harness.local_sched import reserve_act
    from halo_harness.local_sched.reserve import claims
    with BundleHome() as h:
        status, body = h.studio("POST", "pack/bundle/meta-glasses/on")
        rows = _claims(h)
        ctx.check(f"the tick, got {status} {body.get('lines')}", status == 200 and rows and rows[0]["holder"] == "process"
                  and rows[0]["holder_pid"] == os.getpid() and rows[0]["scope"] == "until-restart")
        lines = reserve_act.at_exit()
        ctx.check(f"this halo exits: released, got {lines}", _claims(h) == [] and any("released lfm3:1.7b" in ln for ln in lines))
        status, body = h.studio("POST", "pack/bundle/nosuch/on")
        ctx.check(f"an unknown bundle is a 404, got {status}", status == 404)
        from halo_harness.local_sched import claims_file as CF
        CF.put(CF.local_file(h.state), {"bundle": "gone", "host": "pc", "model": LFM, "gb": 1.2, "holder": "process",
                                        "holder_pid": 999999, "scope": "until-restart", "via": "local"})
        ctx.check("a claim whose holder is gone counts for nothing", claims(h.host, state_dir=h.state) == [])


@test
def test_through_a_halo_host(ctx: Ctx):
    from halo_harness.local_sched.reserve_act import claim, release
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.host_act_rig import PeerRig
    with PeerRig() as rig:
        host = OllamaHost(name="pc", url=rig.peer_url)
        # The claim judges the fit through the host's `route`; a route that does not answer yet reads as "not judged: no
        # card read for pc" (the Linux shard-1 run 41516126225 on the R0 head lost it once under load). Wait for the host
        # to answer the bundle's own model before claiming -- the readiness the check assumes, never a fixed sleep.
        import time
        from halo_harness.local_sched.bundle_needs import reads
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if reads(host, rig.peer).need(BIG, 32768).get("bytes"):
                break
            time.sleep(0.1)
        ok, lines, v = claim("bulk-worker", host=host, cwd=Path(rig.rig.root_p))
        ctx.check(f"claimed through the host, got {ok} {lines} {v.get('says')}", ok and any("held by the halo host" in ln
                                                                                           for ln in lines))
        st, got = rig.get("residency")
        held = got.get("claims") or []
        ctx.check(f"GET residency answers the claim, got {held}", len(held) == 1 and held[0]["bundle"] == "bulk-worker"
                  and held[0]["model"] == "qwen3.5:9b")
        st, got = rig.act("control", "warm", {"model": BIG, "num_ctx": 32768})
        ctx.check(f"a breaching warm is refused with the claim, got {st} {got}", st == 422
                  and "with bulk-worker's" in str(got.get("error")) and "queued behind bulk-worker" in str(got.get("error")))
        st, got = rig.act("control", "unload", {"model": "qwen3.5:9b"})
        ctx.check(f"the reserved model is not unloaded, got {st} {got}", st == 422
                  and "qwen3.5:9b is reserved for bulk-worker" in str(got.get("error")))
        ok, lines = release("bulk-worker", cwd=Path(rig.rig.root_p))
        st, got = rig.get("residency")
        ctx.check(f"off releases it there, got {lines} {got.get('claims')}", ok and got.get("claims") == [])
        ctx.check(f"no load reached the fake, got {rig.mock.generated}", rig.mock.generated == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
