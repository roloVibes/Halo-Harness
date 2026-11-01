"""tests.helpers.studio_pool -- Studio's Local -> Pool (Halo 3.3.8.0 R1) in headless Chrome: tests/helpers/host_rig.py's
fake host (its card for `pc`: a 24 GB card, nothing resident, a 2.5 GbE link) paired with this process's home, whose
Studio serves the page; the pool has two members -- `pc` (the paired host pc-host) and `worker1` (192.0.2.21, 40 GB
as stated); the scan's network layer is faked (rpc_probe.SEAMS) over two rpc-server stand-ins on 127.0.0.1:0. No
model call, no real ssh, never a request beyond 127.0.0.1 (the rig refuses one).

`members`: the two rows with their numbers (every wait reads the data it checks), the recommendation table (Qwen3-Next
fits the pool, gpt-oss does not), the line that says what R1 cannot do yet; nothing was scanned by the page load.
`scan`: Scan is a button: pressed, the two responders (one is the member pc), Add on the other makes a third member.
`library`: the Library's Pool preset shows the pool rows with their badges.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

ROWS = "[data-testid=pool-member]"
REC = "[data-testid=pool-rec-row]"
CANDS = "[data-testid=pool-scan-candidate]"
LINK = {"type": "wired", "speed_mbps": 2500, "iface": "eth0", "source": "fixture"}


def members(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=pool&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'pool'", 40)
    cells = f"{qa(ROWS)}.map((r) => [r.dataset.name, r.querySelector('[data-testid=pool-member-vram]').textContent, " \
            f"r.querySelector('[data-testid=pool-member-link]').textContent, r.querySelector('[data-testid=pool-member-gpu]').textContent])"
    out = {"members": c.wait(f"{qa(ROWS)}.length === 2 && {qa(ROWS)}.every((r) => !r.textContent.includes('reading')) && {cells}", 40)}
    rec = f"{qa(REC)}.map((r) => [r.dataset.model, r.dataset.state, r.dataset.rank || null, " \
          f"r.querySelector('[data-testid=pool-rec-badge]').textContent])"
    out["rec"] = c.wait(f"{qa(REC)}.length >= 2 && {rec}", 30)
    out["preview"] = c.wait(f"{q('[data-testid=pool-rec-preview]')}?.textContent", 15)
    out["not_yet"] = c.wait(f"{q('[data-testid=pool-not-yet]')}.textContent.includes('R2') && {q('[data-testid=pool-not-yet]')}.textContent", 15)
    out["head"] = c.js(f"{q('[data-testid=pool-members-head]')}.textContent")
    out["scanned_on_load"] = ctx["scan_file"].exists() or c.js(f"!!{q('[data-testid=pool-scan-candidates]')}")
    out["scan_line_before"] = c.js(f"{q('[data-testid=pool-scan-line]')}.textContent")
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


def scan(c, url, ctx) -> dict:
    out = {"is_button": c.js(f"{q('[data-testid=pool-scan]')}.tagName")}
    press(c, q("[data-testid=pool-scan]"), f"{qa(CANDS)}.length === 2")
    out["cands"] = c.wait(f"{qa(CANDS)}.length === 2 && {qa(CANDS)}.map((x) => [x.dataset.host, x.dataset.member || '', "
                          f"!!x.querySelector('[data-testid=pool-scan-add]')])", 20)
    out["scan_file"] = ctx["scan_file"].exists()
    out["rtt"] = c.wait(f"{q(ROWS + '[data-name=pc] [data-testid=pool-member-rtt]')}?.textContent.endsWith('ms') && "
                        f"{q(ROWS + '[data-name=pc] [data-testid=pool-member-rtt]')}.textContent", 20)
    press(c, q("[data-testid=pool-scan-add]"), f"{qa(ROWS)}.length === 3")
    out["after_add"] = c.wait(f"{qa(ROWS)}.length === 3 && {qa(ROWS)}.map((r) => r.dataset.name)", 20)
    return out


def library(c, url, ctx) -> dict:
    page(c, "library")
    press(c, q("[data-testid=local-preset][data-preset=pool]"), f"{qa('[data-testid=local-library-pool]')}.length === 3")
    rows = "[data-testid=local-library-row]"
    got = f"{qa(rows)}.map((r) => [r.dataset.key, r.querySelector('[data-testid=local-library-pool]')?.dataset.state || ''])"
    return {"lib": c.wait(f"{qa('[data-testid=local-library-pool]')}.length === 3 && {got}", 30),
            "lib_head": c.wait(f"{q('[data-testid=local-pool-head]')}?.textContent", 15),
            "lib_save": c.js(f"!!{q('[data-testid=local-save-template]')}")}


class PoolDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.local_pool import members as M
        from halo_harness.local_pool.scan import _file
        from halo_harness.providers import ollama_panel as OP
        from halo_harness.providers import rpc_probe as P
        from tests.helpers.host_rig import HostRig, readers
        from tests.helpers.ollama_panel_seed import cards
        from tests.helpers.pool_rig import rpc_listener
        saved = (OP.probe_version, OP.fetch_ps)  # the shell's capability catalog probes every configured Ollama host:
        OP.probe_version = OP.fetch_ps = lambda *_a, **_k: None  # pc is a placeholder, so it reads as not reachable
        card = {**cards()["pc"], "loaded": [], "other_users": []}
        with ExitStack() as stack:
            rig = stack.enter_context(HostRig(readers_={**readers(), "card": lambda h: dict(card), "link": lambda: dict(LINK)}))
            one, two = stack.enter_context(rpc_listener()), stack.enter_context(rpc_listener())
            rig.start()
            rig.pair()
            M.add("pc", f"pc-host:{one}", state_dir=rig.peer)
            M.add("worker1", "192.0.2.21", vram_gb=40, state_dir=rig.peer)
            P.SEAMS.update(sweep=lambda networks, ports, deadline: [("127.0.0.1", one), ("127.0.0.1", two)],
                           own=lambda: "192.0.2.5")
            srv, url = serve(rig.peer, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "rig": rig, "scan_file": _file(rig.peer)}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (members, scan, library))
            finally:
                self.out["blocked"] = [str(a) for a in rig.blocked]
                P.SEAMS.clear()
                srv.shutdown()
                srv.server_close()
                OP.probe_version, OP.fetch_ps = saved


if __name__ == "__main__":
    sys.exit(PoolDriver(sys.argv[1:]).main())
