"""tools/capture_ollama.py -- the Ollama panel capture for `tools/capture_studio.py --mode fleet --panel ollama` (Halo
3.3.4.0 R5), through headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the scratch home
capture_studio seeds plus the steward fixture of tests/helpers/ollama_panel_seed.py (two 192.0.2.x hosts, a local
server on loopback, the ledger, a note, review mode; the cards and the catalog through
studio/ollama_hosts_view.READERS: no model call, no network, no probe):

    docs/media/studio-fleet-ollama.png   Fleet with its Ollama panel added through the header's "+": pc's card line
                                         (ComfyUI holding memory), the models with this hour's trims and cuts, the
                                         traffic sparkline, the steward's note and findings (Apply / Dismiss in
                                         review mode) and the fit plan with its Copy line

With --dom the page is counted by data-testid (the last stdout line is the JSON). Never two Chromes at once; every
page is guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("fleet-ollama-detail", "ollama-host", "ollama-card", "ollama-model-row", "ollama-vision", "ollama-timeline",
       "ollama-mark", "ollama-finding", "ollama-apply", "ollama-dismiss", "ollama-plan", "ollama-copy-hint",
       "section-help", "start-here")


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    c.go(url)
    c.wait("(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '').startsWith('Fleet')", 40)
    c.wait("!!document.querySelector('[data-testid=panels-add]')", 30)
    c.click_on("document.querySelector('[data-testid=panels-add]')")
    row = "document.querySelector('[data-testid=panels-menu-item][data-panel=fleet-ollama]')"
    c.wait(f"!!{row}", 10)
    c.click_on(row)
    c.wait("document.querySelectorAll('[data-testid=ollama-model-row]').length >= 2", 30)
    c.wait("!!document.querySelector('[data-testid=ollama-timeline]') && !!document.querySelector('[data-testid=ollama-plan]')", 20)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers import ollama_panel_seed as S
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_NO_BACKGROUND_NET",)}
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    S.seed(state)
    V.reset_cache()
    V.READERS.update(S.readers())
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=fleet&view=workspace&tour=off&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "fleet ollama")
        if as_dom:
            print(json.dumps({"ollama": counts(c)}))
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
        V.READERS.clear()
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
