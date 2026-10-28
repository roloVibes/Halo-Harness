"""tools/capture_local.py -- the Local capture for tools/capture_studio.py --mode local (Halo 3.3.5.0 R1: the modes
banner's tenth tile), through headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the scratch home
capture_studio seeds with tests/helpers/local_seed.py's fixture (the Ollama panel's hosts, ledger, cards and catalogs
on 192.0.2.x placeholders, and `box`, a fake Ollama on 127.0.0.1:0); the sampler reads the fixture's nvidia-smi and
/proc answers; no model call, no probe (BRIDGE_TEST_NO_BACKGROUND_NET):

    docs/media/studio-local.png   Local on its Resources page as `halo local resources` opens it
                                  (`?mode=local&page=resources`): the page rail on the left, a live strip per host
                                  (VRAM and who holds it, the GPU line, RAM, CPU, the temperature) and the traffic
                                  view under them (the sparklines per host, the calls newest at the foot)

With --dom the page is counted by data-testid (the last stdout line is the JSON). Never two Chromes at once; every
page is guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "local-rail-page", "local-page", "local-resources-host", "local-traffic-row", "local-traffic-spark",
       "local-traffic-event", "section-help", "start-here")


def seed(state: Path):
    """The Local fixture, a minute of samples already kept, the network flag on."""
    from halo_harness.ollama_steward import resources as R
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers import local_seed as L
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_NO_BACKGROUND_NET",)}
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    mock = L.start_box()
    L.seed(state, mock)
    V.reset_cache()
    V.READERS.update(L.readers(mock))
    seams = L.sampler_seams(mock)
    R.SAMPLER_SEAMS.update(seams)
    t = [time.time() - 60]
    s = R.Sampler(state, clock=lambda: t[0], **seams)
    for _ in range(60):
        s.sample_once()
        t[0] += 1.0
    return saved, mock


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    c.go(url)
    c.wait("(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '').startsWith('Local')", 40)
    c.wait("document.querySelectorAll('[data-testid=local-resources-host]').length >= 2", 30)
    c.wait("document.querySelectorAll('[data-testid=local-traffic-row]').length >= 10", 20)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from halo_harness.ollama_steward import resources as R
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    saved, mock = seed(state)
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=local&page=resources&tour=off&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        mock.stop()
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "local")
        if as_dom:
            print(json.dumps({"local": counts(c)}))
            return 0
        png = Path(out).resolve()
        size = c.shot(png)
        ok = size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {png} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.go("about:blank")
        c.close()
        srv.shutdown()
        srv.server_close()
        mock.stop()
        R.stop_all()
        R.SAMPLER_SEAMS.clear()
        R.STORE.clear()
        V.READERS.clear()
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
