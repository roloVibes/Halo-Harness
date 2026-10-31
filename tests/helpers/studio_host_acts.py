"""tests.helpers.studio_host_acts -- Studio's Local section acting through a paired `halo host` (Halo 3.3.7.0 R2) in
headless Chrome: tests/helpers/host_act_rig.PeerRig (the host on a scratch home, its `pc` a fake Ollama on 127.0.0.1:0;
this process's home the peer with `control` there, fleet.allow_control all), whose Studio serves the page. No model
call, no real ssh, never a request beyond 127.0.0.1 (the rig refuses one).

`hosts`: Local -> Hosts, pc's card: the grants line ("grants there: view, control"), Load on qwen3-coder:30b goes
through the host (the fake saw the load), "through halo host at 127.0.0.1"; the server setting's line (KV cache
q8_0): the exact line for the host's OS, applied false.
`probe`: Local -> Models, pc's qwen3-coder:30b, Probe: the battery runs on the host, its steps come back as this
Studio's probe frames (the strip running, then done).
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE, page  # noqa: E402
from tests.helpers.studio_packs_steps import q  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

CARD = '[data-testid=local-host-card][data-name="pc"]'
CODER = "qwen3-coder:30b"


def hosts(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=hosts&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'hosts'", 40)
    grants = q(f"{CARD} [data-testid=local-host-grants]")
    out = {"grants": c.wait(f"{grants} && {grants}.textContent", 40)}
    load = q(f'{CARD} [data-testid=local-host-model][data-model="{CODER}"] [data-testid=local-load]')
    out["load_enabled"] = c.wait(f"{load} && !{load}.disabled", 20)
    said = q(f'{CARD} [data-testid=local-host-model][data-model="{CODER}"] [data-testid=local-said]')
    press(c, load, f"!!{said}")
    out["load_said"] = c.wait(f"{said} && {said}.textContent", 30)
    out["loaded_on_fake"] = [g["model"] for g in ctx["rig"].mock.generated]
    out["via"] = c.js(f"{q(CARD + ' [data-testid=local-control-via]')}?.textContent || ''")
    ask = q(f"{CARD} [data-testid=local-host-stated-ask]")
    line = q(f"{CARD} [data-testid=local-host-stated-said]")
    press(c, ask, f"!!{line}")
    out["stated"] = c.wait(f"{line} && {line}.textContent", 30)
    out["posts_after_stated"] = len([r for r in ctx["rig"].mock.requests if r.get("method") == "POST"])
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


def probe(c, url, ctx) -> dict:
    from tests.helpers import mock_ollama_battery as MB
    mock = ctx["rig"].mock
    mock.scenarios[CODER] = MB.scenario("bt-coder:30b")
    mock.load_delay_s[CODER] = 0.4  # every probe takes a moment: the strip is seen running
    c.go(f"{ctx['base']}?mode=local&page=models&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'models'", 40)
    page(c, "models")
    row = f'[data-testid=local-model-row][data-host=pc][data-model="{CODER}"]'
    c.wait(f"!!{q(row)}", 30)
    btn = q(f"{row} [data-testid=local-model-probe]")
    out = {"probe_enabled": c.wait(f"{btn} && !{btn}.disabled", 20)}
    strip = q(f"{row} [data-testid=local-probe-strip]")
    press(c, btn, f"!!{strip}")
    step = f"{strip}?.querySelector('[data-testid=local-probe-step]')?.textContent || ''"
    out["running"] = c.wait(f"{strip} && !{strip}.dataset.done && ({step})", 30)
    out["done"] = c.wait(f"{strip}?.dataset.done && [{strip}.dataset.ok || '', {step}]", 90)
    out["host_jobs"] = [j["op"] for j in __import__("halo_harness.host.jobs", fromlist=["of"]).of(ctx["rig"].svc).jobs.list()]
    return out


class HostActsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.providers import ollama_panel as OP
        from tests.helpers.host_act_rig import PeerRig
        saved = (OP.probe_version, OP.fetch_ps)  # the shell's capability catalog probes every configured Ollama host:
        OP.probe_version = OP.fetch_ps = lambda *_a, **_k: None  # pc is a placeholder, so it reads as not reachable
        with PeerRig(cap="all", grants=("control",)) as rig:
            srv, url = serve(rig.peer, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "rig": rig}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (hosts, probe))
            finally:
                self.out["blocked"] = [str(a) for a in rig.rig.blocked]
                srv.shutdown()
                srv.server_close()
                OP.probe_version, OP.fetch_ps = saved


if __name__ == "__main__":
    sys.exit(HostActsDriver(sys.argv[1:]).main())
