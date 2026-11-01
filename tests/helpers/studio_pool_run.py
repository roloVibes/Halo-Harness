"""tests.helpers.studio_pool_run -- Local -> Pool's Warm and Stop (Halo 3.3.8.0 R3) in headless Chrome, over
tests/helpers/pool_run_rig.RunRig (pc through its halo host with qwen3.8:27b resident; me: this machine's 40 GB card;
the controller's llama-server the loopback fake; pc's rpc-server the FakeRpc stand-in), whose home's Studio serves the
page. No model call, no real rpc-server or llama-server, never a request beyond 127.0.0.1 (the rig refuses one).

`preflight`: the preflight's eight checks (each row read with its data), Warm enabled once green, the Wi-Fi switch,
the capacity note (no "arrive in R2" line any more), nothing opened over the page.
`warm`: Warm pressed -> the state reads running, both members with their claims and leases, the Warm's lines (the
pivot line for pc's resident model among them), Stop enabled, Warm disabled.
`stop`: Stop pressed -> stopped, the stop's lines said, the preflight back.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
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

CHECKS = "[data-testid=pool-preflight-check]"
STATE = "[data-testid=pool-run-state]"
MEMBERS = "[data-testid=pool-run-member]"
WARM, STOP = "[data-testid=pool-warm]", "[data-testid=pool-stop]"


def preflight(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=pool&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'pool'", 40)
    rows = f"{qa(CHECKS)}.map((r) => [r.dataset.check, !!r.dataset.ok])"
    out = {"checks": c.wait(f"{qa(CHECKS)}.length === 8 && {rows}", 40)}
    out["line"] = c.wait(f"{q('[data-testid=pool-preflight][data-ok]')} && {q('[data-testid=pool-preflight-line]')}.textContent", 20)
    out["warm_enabled"] = c.wait(f"{q(WARM)} && !{q(WARM)}.disabled && 'enabled'", 20)
    out["stop_disabled"] = c.js(f"{q(STOP)}.disabled")
    out["model"] = c.wait(f"{q('[data-testid=pool-run-model]')}?.value", 15)
    out["wifi"] = c.js(f"{q('[data-testid=pool-run-wifi]')}?.type || ''")
    out["note"] = c.wait(f"{q('[data-testid=pool-note]')}?.textContent", 15)
    out["not_yet"] = c.js(f"!!{q('[data-testid=pool-not-yet]')}")
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    out["state_before"] = c.wait(f"{q(STATE)}?.dataset.state === 'stopped' && {q(STATE)}.textContent", 15)
    return out


def warm(c, url, ctx) -> dict:
    running = f"{q(STATE)}?.dataset.state === 'running' && {qa(MEMBERS)}.length === 2"
    press(c, q(WARM), f"{q(WARM)}.disabled")
    members = f"{qa(MEMBERS)}.map((r) => [r.dataset.name, r.dataset.up, r.dataset.live || '', r.textContent])"
    out = {"members": c.wait(f"{running} && {members}", 60)}
    out["state"] = c.wait(f"{running} && {q(STATE)}.textContent", 15)
    lines = f"{qa('[data-testid=pool-warm-lines] li')}.map((x) => x.textContent)"
    out["lines"] = c.wait(f"{q('[data-testid=pool-warm-lines]')}?.dataset.ok === '1' && {lines}", 30)
    out["stop_enabled"] = c.wait(f"!{q(STOP)}.disabled && 'enabled'", 15)
    out["warm_disabled"] = c.js(f"{q(WARM)}.disabled")
    out["cooldown"] = c.wait(f"{q('[data-testid=pool-run-cooldown]')}?.textContent", 15)
    return out


def stop(c, url, ctx) -> dict:
    press(c, q(STOP), f"{q(STATE)}?.dataset.state === 'stopped'")
    out = {"state_after": c.wait(f"{q(STATE)}?.dataset.state === 'stopped' && {q(STATE)}.textContent", 30)}
    out["entry_gone"] = ctx["entry"]() is None
    out["preflight_back"] = c.wait(f"{qa(CHECKS)}.length === 8 && {qa(CHECKS)}.length", 30)
    return out


class PoolRunDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.local_pool.entry import current
        from halo_harness.providers import ollama_panel as OP
        from tests.helpers.pool_run_rig import RunRig
        saved = (OP.probe_version, OP.fetch_ps)  # the shell's capability catalog probes every configured Ollama host:
        OP.probe_version = OP.fetch_ps = lambda *_a, **_k: None  # pc is a placeholder, so it reads as not reachable
        with ExitStack() as stack:
            rig = stack.enter_context(RunRig())
            srv, url = serve(rig.peer, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "rig": rig, "entry": current}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (preflight, warm, stop))
            finally:
                self.out["blocked"] = [str(a) for a in rig.rig.blocked]
                self.out["rpc_argv"] = rig.fake.argvs
                srv.shutdown()
                srv.server_close()
                OP.probe_version, OP.fetch_ps = saved


if __name__ == "__main__":
    sys.exit(PoolRunDriver(sys.argv[1:]).main())
