"""tests.helpers.studio_hosts_host -- Studio's Local section over a paired `halo host` (Halo 3.3.7.0 R1) in headless
Chrome: tests/helpers/host_rig.py's fake host (fixture card, catalog, tail and log status for `pc` at the 192.0.2.10
placeholder) paired with this process's home, whose Studio serves the page. No model call, no real ssh, never a
request beyond 127.0.0.1 (the rig refuses one).

`hosts`: Local -> Hosts groups pc under SERVED BY HALO HOST; its card says "served by halo host at 127.0.0.1 --
running since ..., last seen ..., N requests in its audit"; its log line reads "via host"; Load says why not yet.
`logs`: Local -> Logs with pc picked: the status line says "via host"; the tail's lines arrive from the host, the cut
prompt's sizes among them, the request-body line replaced by its size.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import set_field  # noqa: E402

CARD = '[data-testid=local-host-card][data-name="pc"]'


def hosts(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=hosts&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'hosts'", 40)
    line = q(f"{CARD} [data-testid=local-host-host]")
    out = {"host_line": c.wait(f"{line} && {line}.textContent.includes('running since') && {line}.textContent", 40)}
    out["group"] = c.js(f"{q(CARD)}.closest('[data-testid=local-hosts-group]').dataset.source")
    out["first_group"] = c.js(f"{qa('[data-testid=local-hosts-group]')}[0].dataset.source")
    out["log_line"] = c.js(f"{q(CARD + ' [data-testid=local-host-log]')}?.textContent || ''")
    out["why"] = c.js(f"{q(CARD + ' [data-testid=local-control-why]')}?.textContent || ''")
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


def logs(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=logs&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'logs'", 40)
    host = q("[data-testid=local-logs-host]")
    c.wait(f"!!{host}", 30)
    set_field(c, host, "pc", "change")
    status = q("[data-testid=local-logs-status-line]")
    out = {"status": c.wait(f"{status} && {status}.textContent.includes('via host') && {status}.textContent", 30)}
    lines = qa("[data-testid=local-logs-line]")
    out["lines"] = c.wait(f"{lines}.length >= 3 && {lines}.map((x) => x.textContent)", 30)
    out["groups"] = c.js(f"[...new Set({lines}.map((x) => x.dataset.group))]")
    return out


class HostsHostDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.providers import ollama_panel as OP
        from tests.helpers.host_rig import HostRig
        saved = (OP.probe_version, OP.fetch_ps)  # the shell's capability catalog probes every configured Ollama host:
        OP.probe_version = OP.fetch_ps = lambda *_a, **_k: None  # pc is a placeholder, so it reads as not reachable
        with HostRig() as rig:
            rig.start()
            rig.pair()
            srv, url = serve(rig.peer, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "rig": rig}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (hosts, logs))
            finally:
                self.out["blocked"] = [str(a) for a in rig.blocked]
                srv.shutdown()
                srv.server_close()
                OP.probe_version, OP.fetch_ps = saved


if __name__ == "__main__":
    sys.exit(HostsHostDriver(sys.argv[1:]).main())
