"""tools/capture_workflows.py -- the Workflows capture for tools/capture_studio.py --mode workflows (Halo 3.3.16.1 docs),
through headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the scratch home capture_studio seeds. The
scene is the board tests/helpers/studio_workflows.py drives: the auto lineup with three shipped squares enabled (`media`,
`plan`, `review`), the library open beside them and the media square selected, its contract in the inspector. No model
is called and no session runs:

    docs/media/studio-workflows.png   Agents -> Workflows (`?mode=agents&view=workflows`): the three squares as cards
                                      (DOES / TAKES / GIVES / COSTS and a limits chip), main's lines to them, the library
                                      with its three groups, the media square's summary in the inspector

1500 x 900 CSS px at scale 2. With --dom the page is counted by data-testid (the last stdout line is the JSON). The page
is guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

ENABLED = ["media", "plan", "review"]
IDS = ("section-tab", "agents", "wf-board", "wf-card", "wf-card-limits", "wf-library", "wf-row", "wf-inspector", "wf-summary", "wf-edge")
CARDS = "document.querySelectorAll('[data-testid=\"wf-card\"]')"


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    """The board with three squares, the library open, media selected."""
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(url)
    c.wait(f"{CARDS}.length === {len(ENABLED)}", 40)
    if not c.js("!!document.querySelector('[data-testid=\"wf-library\"]')"):
        c.click_on("document.querySelector('[data-testid=\"wf-library-plus\"]')")
    c.wait("!!document.querySelector('[data-testid=\"wf-library\"]')", 10)
    c.click_on("document.querySelector('[data-testid=\"wf-card\"][data-ref=\"media\"]')", 0.5, 0.8)
    c.wait("!!document.querySelector('[data-testid=\"wf-summary\"]')", 10)
    c.js("document.activeElement?.blur()")
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from halo_harness.theme import set_config_value
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    set_config_value("team", "auto")  # the auto lineup reads workflows.enabled
    set_config_value("workflows.enabled", ENABLED)
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=agents&view=workflows&tour=off&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "workflows")
        if as_dom:
            print(json.dumps({"workflows": counts(c)}))
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
