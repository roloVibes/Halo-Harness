"""tools/capture_settings.py -- the Settings capture for tools/capture_studio.py --mode settings (Halo 3.3.3.0 R2:
the modes banner's ninth tile), through headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the
scratch home capture_studio seeds (no model call, no network, no probe: BRIDGE_TEST_NO_BACKGROUND_NET):

    docs/media/studio-settings.png   Settings on its Fleet page as `halo settings fleet` opens it
                                     (`?mode=settings&group=fleet`): the group rail on the left (the keys set per
                                     group), the Fleet rows on the right (fleet.name is the placeholder you@studio,
                                     a share of full, two tags, the hub port), each with its help line, its control,
                                     the default marker on the rest, Reset and its halo config set line

With --dom the page is counted by data-testid (the last stdout line is the JSON). Never two Chromes at once; every
page is guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "settings-rail", "settings-rail-group", "settings-group-page", "settings-row", "settings-default",
       "settings-cli", "section-help", "start-here")


def seed() -> dict:
    """A few Fleet keys set (the rest show their defaults), a default model, the network flag off."""
    from halo_harness.theme import set_config_value
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_NO_BACKGROUND_NET",)}
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    set_config_value("model", "or:demo/atlas-pro")
    set_config_value("fleet.share", "full")
    set_config_value("fleet.tags", ["gpu", "studio"])
    set_config_value("fleet.hub.port", 7431)
    set_config_value("permission_mode", "acceptEdits")
    return saved


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    c.go(url)
    c.wait("(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '').startsWith('Settings')", 40)
    c.wait("document.querySelector('[data-testid=settings-group-page]')?.dataset.group === 'fleet'", 30)
    c.wait("document.querySelectorAll('[data-testid=settings-row]').length >= 10", 20)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    saved = seed()
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=settings&group=fleet&tour=off&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "settings")
        if as_dom:
            print(json.dumps({"settings": counts(c)}))
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
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
