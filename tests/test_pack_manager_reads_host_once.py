"""tests.test_pack_manager_reads_host_once -- GET pack/manager reads this host once (Halo 3.6.0.0 fix; packs/manager.py
`payload`, packs/capability_check.py `host_catalog`, peers/capabilities_host.py `hardware`).

On Windows Studio's Packs page waited 7.6 s on GET pack/manager: every pack row that contributes a capability built
the host catalog again (its row, then its doctor rows), and each build started PowerShell to read the network link's
type and speed, a fact no capability check reads. One payload() now builds the catalog once and never reads the link.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _counted(h, ctx: Ctx):
    """One payload() with the host probes counted (as if probing were allowed, the way Studio runs)."""
    from halo_harness.config import paths
    from halo_harness.local_pool import link
    from halo_harness.packs.manager import payload
    from halo_harness.peers import capabilities_host as host
    calls = {"link": 0, "gpus": 0}
    saved = (paths.background_net_disabled, link.read, host._gpus)

    def _link(*_a, **_k):
        calls["link"] += 1
        return {**link.UNKNOWN, "source": "counted"}

    def _gpus(spawn):
        calls["gpus"] += 1
        return [{"name": "Test GPU", "vram_gb": 8.0}] if spawn else []
    paths.background_net_disabled, link.read, host._gpus = (lambda: False), _link, _gpus
    try:
        got = payload(cwd=h.repo, state_dir=h.state)
    finally:
        paths.background_net_disabled, link.read, host._gpus = saved
    return got, calls


@test
def test_one_payload_reads_the_host_once_and_never_the_link(ctx: Ctx):
    """Two packs that contribute capabilities, one enabled (its doctor rows check them too): one payload() reads the
    GPUs once and the network link never; the rows still say what the checks found."""
    with PacksHome() as h:
        h.install(h.source("caps-needs-gpu"), enable=True)
        h.install(h.source("doc-review"))
        got, calls = _counted(h, ctx)
        ctx.check(f"the link is never read (it took PowerShell on Windows), got {calls['link']} reads", calls["link"] == 0)
        ctx.check(f"the GPUs are read once per payload, got {calls['gpus']}", calls["gpus"] == 1)
        row = next(p for p in got["packs"] if p["id"] == "caps-needs-gpu")
        caps = ((row.get("contributes") or {}).get("capabilities") or {}).get("capabilities") or []
        ctx.check(f"the row still checks the GPU it was given, got {[(c['name'], c['why']) for c in caps]}",
                  any(c["name"] == "gpu.render" and "Test GPU" in c["why"] for c in caps))
        _got, again = _counted(h, ctx)
        ctx.check(f"a second request reads the host afresh (no stale cache), got {again}", again == {"link": 0, "gpus": 1})


@test
def test_hardware_still_reads_the_link_for_the_catalog(ctx: Ctx):
    """hardware() keeps the link by default (3.3.8.0 R1's catalog shape, tests/test_pool_members.py); only the pack
    checks ask for it without."""
    from halo_harness.local_pool import link
    from halo_harness.peers import capabilities_host as host
    saved, n = (link.read, host._gpus), []
    link.read = lambda *_a, **_k: n.append(1) or {**link.UNKNOWN, "type": "wired", "speed_mbps": 1000}
    host._gpus = lambda _spawn: []
    try:
        hw = host.hardware(Path.cwd(), spawn=True)
        lean = host.hardware(Path.cwd(), spawn=True, link=False)
    finally:
        link.read, host._gpus = saved
    ctx.check(f"default: the link read once, got {len(n)} {hw.get('link')}", len(n) == 1 and hw["link"].get("type") == "wired")
    ctx.check(f"link=False: no link key, got {sorted(lean)}", "link" not in lean)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
