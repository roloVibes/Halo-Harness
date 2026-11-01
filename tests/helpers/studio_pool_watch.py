"""tests.helpers.studio_pool_watch -- Local -> Pool measured and watched (Halo 3.3.8.0 R4) in headless Chrome, over
tests/helpers/pool_run_rig.RunRig with the pool warmed before the page opens (the controller's llama-server the
loopback fake: it loads no model and answers the battery with arithmetic; pc's rpc-server the FakeRpc stand-in), whose
home's Studio serves the page. No model call, no real rpc-server or llama-server, never a request beyond 127.0.0.1.

`bench`: the cost line first (seconds, the members busy), the penalty line extrapolated; Quick bench pressed -> the
card's lines and "pool: 11.2 tok/s measured"; each member's claim names its bundle.
`bundles`: Packs -> the Bundles group lists big-reasoner with its pool part and its priority chip -- read while the
pool is healthy: `route` says "degraded ... it takes no lane" once the log below carries the lost backend (the Linux
all-tiers run 41327065087 read it after `findings` and saw that line; the order below is the fix).
`findings`: an RPC backend lost in the controller's log -> the page's Findings block lists pool-degraded.
`adviser`: Local -> Models' Adviser shows the placement scores of the lineup's worker lane.
Every wait reads the data its assertion checks. The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

COST, PENALTY = "[data-testid=pool-bench-cost]", "[data-testid=pool-bench-penalty]"


def bench(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=pool&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'pool'", 40)
    out = {"cost": c.wait(f"{q(COST)}?.textContent.startsWith('local: ~') && {q(COST)}.textContent", 40)}
    out["before"] = c.wait(f"{q(PENALTY)} && !{q(PENALTY)}.dataset.measured && {q(PENALTY)}.textContent", 20)
    press(c, q("[data-testid=pool-bench-quick]"), f"{q(PENALTY)}?.dataset.measured === 'true'")
    out["after"] = c.wait(f"{q(PENALTY)}?.dataset.measured === 'true' && {q(PENALTY)}.textContent", 40)
    lines = f"{qa('[data-testid=pool-bench-card] li')}.map((x) => x.textContent)"
    out["card"] = c.wait(f"{qa('[data-testid=pool-bench-card] li')}.length >= 2 && {lines}", 20)
    member = "[data-testid=pool-run-member][data-name=pc]"
    out["claim"] = c.wait(f"{q(member)}?.textContent.includes('claimed by pool:') && {q(member)}.textContent", 20)
    return out


def findings(c, url, ctx) -> dict:
    ctx["degrade"]()
    c.go(f"{ctx['base']}?mode=local&page=pool&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'pool'", 40)
    row = "[data-testid=pool-finding][data-rule=pool-degraded]"
    return {"finding": c.wait(f"{q(row)}?.textContent.includes('degraded (pc down)') && {q(row)}.textContent", 40),
            "severity": c.wait(f"{q(row)}?.dataset.severity", 10)}


def bundles(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=packs&tour=off#{ctx['frag']}")
    row = "[data-testid=pm-bundle-row][data-id=big-reasoner]"
    part = f"{row} [data-testid=pm-bundle-part]"
    out = {"part": c.wait(f"{q(part)}?.dataset.host === 'pool' && {q(part)}.textContent", 60)}
    out["priority"] = c.wait(f"{q(row + ' [data-testid=pm-bundle-priority]')}?.textContent", 20)
    out["state"] = c.wait(f"{q(row)}?.dataset.state", 10)
    return out


def adviser(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=models&tour=off#{ctx['frag']}")
    score = "[data-testid=local-adviser-score]"
    return {"scores": c.wait(f"{qa(score)}.length > 0 && {qa(score)}.map((x) => x.textContent)", 60)}


class PoolWatchDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.local_pool import launch
        from halo_harness.ollama_steward import changes_pool, server_log_hf, servers_hf
        from halo_harness.providers import ollama_panel as OP
        from halo_harness.theme import set_config_value
        from tests.helpers.pool_run_rig import QWEN, RunRig
        from tests.helpers.sched_lineup import write
        saved = (OP.probe_version, OP.fetch_ps)  # the shell's capability catalog probes every configured Ollama host:
        OP.probe_version = OP.fetch_ps = lambda *_a, **_k: None  # pc is a placeholder, so it reads as not reachable
        with ExitStack() as stack:
            rig = stack.enter_context(RunRig())
            got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test", keep=True)
            if not got.get("ok"):
                raise RuntimeError(f"the pool did not warm: {got.get('lines')}")
            write(rig.peer, "pooled", {"worker": "ol:qwen3.8:27b@pc"})
            set_config_value("team", "pooled")

            def degrade() -> None:
                r = launch.run(rig.peer)
                with open(r["log"], "a", encoding="utf-8") as f:
                    f.write(f"Failed to connect to 127.0.0.1:{rig.rpc_port}\n")
                s = next(x for x in servers_hf.roster(rig.peer) if x.name == "pool")
                server_log_hf.scan(rig.peer, s, from_start=True)
            srv, url = serve(rig.peer, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "rig": rig, "degrade": degrade}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (bench, bundles, findings, adviser))
            finally:
                self.out["blocked"] = [str(a) for a in rig.rig.blocked]
                srv.shutdown()
                srv.server_close()
                OP.probe_version, OP.fetch_ps = saved
                changes_pool.stop(state_dir=rig.peer, by="test")


if __name__ == "__main__":
    sys.exit(PoolWatchDriver(sys.argv[1:]).main())
