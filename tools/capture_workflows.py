"""tools/capture_workflows.py -- the Workflows capture for tools/capture_studio.py --mode workflows (Halo 3.3.16.1 docs;
3.3.16.3 part 2: the composed board), through headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the
scratch home capture_studio seeds. The scene is the board the owner asked for: the auto lineup on Agents -> Cast with its
tiers and three square blocks -- `media-team` (the media template: a reader, a researcher, a writer) wired for pdf and
audio, `thinking` (the thinking template: three reasoning agents) always first, and the shipped `review` for the words
review and audit -- each line from main labelled with its when, and the library open with its three kinds. No model is
called and no session runs:

    docs/media/studio-workflows.png   Agents -> Cast composed (`?mode=agents&view=cast`): the tiers, the blocks with their
                                      agents inside, main's lines and their when labels, the library (Workflows, Blocks
                                      you can start from, Agents)

1500 x 900 CSS px at scale 2. With --dom the page is counted by data-testid (the last stdout line is the JSON). The page
is guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

ENABLED = ["media-team", "thinking", "review"]
WHEN = {"media-team": {"needs": ["pdf", "audio"]}, "thinking": {"mode": "always"}, "review": {"words": ["review", "audit"]}}
IDS = ("section-tab", "agents", "roles-canvas", "roles-tier", "block", "block-agent", "block-edge", "block-when", "wf-library",
       "wf-row", "lib-template", "lib-bio")
BLOCKS = "document.querySelectorAll('[data-testid=\"block\"]')"


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    """Cast on the auto lineup, the three blocks with their labels, the library open, the canvas fitted."""
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(url)
    start = "document.querySelector('[data-testid=\"roles-start-open-default\"]')"
    c.wait(f"!!{start} || document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0", 40)
    if c.js(f"!!{start}"):
        c.click_on(start)
    c.wait(f"{BLOCKS}.length === {len(ENABLED)} && document.querySelectorAll('[data-testid=\"block-when\"]').length === {len(ENABLED)}", 40)
    if not c.js("!!document.querySelector('[data-testid=\"wf-library\"]')"):
        c.click_on("document.querySelector('[data-testid=\"wf-library-plus\"]')")
    c.wait("document.querySelectorAll('[data-testid=\"lib-template\"]').length === 4", 15)
    c.click_on("document.querySelector('[data-testid=\"wf-search\"]')")  # one word: all three kinds in view
    c.call("Input.insertText", text="media")
    c.wait("document.querySelector('[data-testid=\"wf-search\"]').value === 'media' && document.querySelectorAll('[data-testid=\"lib-template\"]').length === 1", 10)
    c.js("document.querySelector('.rc-scroll').focus(); 1")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="f", code="KeyF", text="f", windowsVirtualKeyCode=70)
    c.call("Input.dispatchKeyEvent", type="keyUp", key="f", code="KeyF", windowsVirtualKeyCode=70)
    c.js("document.activeElement?.blur(); document.querySelector('.rc-scroll').scrollTo(0, 0); 1")
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def seed(state: Path) -> None:
    from halo_harness.theme import set_config_value
    from halo_harness.workflows import blocks
    set_config_value("team", "auto")  # the auto lineup reads workflows.enabled and workflows.when
    for name in ("media", "thinking"):
        blocks.add(name, None, "auto", state_dir=state)
    set_config_value("workflows.enabled", ENABLED)
    set_config_value("workflows.when", WHEN)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    seed(state)
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=agents&view=cast&tour=off&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        print("no Chrome found")
        return 2
    try:
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=2, mobile=False)
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
