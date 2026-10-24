"""tools/capture_packs.py -- the Packs capture for tools/capture_studio.py
--mode packs (Halo 3.2.0.0 R7: the modes banner's seventh tile), through
headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over the
scratch home capture_studio seeds (no model call, no network):

    docs/media/studio-packs.png   the Pack Manager with the shipped Documentation Review pack installed by id and
                                  enabled with bash: Installed (its row, 1/3 granted), Details (the API and Halo
                                  ranges, the permissions with their toggles, what it contributes), Sources (the
                                  packs Halo ships), Settings (its form) and Templates (its workflow, lineup, bios)

With --dom the section is counted by data-testid (the last stdout line is the
JSON). Never two Chromes at once; every page is guarded before it is counted
or shot (tools/capture_identity.py: you@studio, no real path or name).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "pm-installed-row", "pm-details-body", "pm-perm", "pm-source-pack", "pm-workflow", "pm-template",
       "panel-about", "legacy-frame")
ROW = "document.querySelector('[data-testid=\"pm-installed-row\"][data-id=\"doc-review\"]')"


def seed(state: Path) -> None:
    """doc-review installed by id from the packs Halo ships, enabled with bash, a catalog model that calls tools.
    The shipped folder is copied beside the scratch home first, so Sources draws no path of this checkout."""
    import shutil
    from halo_harness.packs import bio_models
    from halo_harness.packs import sources as SRC
    from halo_harness.packs.grants import enable_id
    from halo_harness.packs.install import install
    from tests.helpers.workflow_rig import TOOLS_ROW
    shipped = state.parent / "templates" / "packs"
    shutil.copytree(SRC.shipped_dir(), shipped, ignore=shutil.ignore_patterns("__pycache__"))
    SRC.shipped_dir = lambda: shipped  # this process serves the page: the Sources panel reads it
    bio_models.ROWS = lambda _s, _c: [{**TOOLS_ROW, "context_tokens": 262144}]
    ok, lines = install("doc-review", state_dir=state)
    if not ok:
        raise SystemExit(f"capture_packs: install failed: {lines}")
    ok, lines = enable_id("doc-review", grant=["bash"], state_dir=state)
    if not ok:
        raise SystemExit(f"capture_packs: enable failed: {lines}")


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    c.go(url)
    c.wait(f"!!{ROW}", 40)
    c.click_on(f"{ROW}.querySelector('.pm-row-main')")
    c.wait("document.querySelector('[data-testid=\"pm-details-body\"]')?.dataset.id === 'doc-review'", 20)
    c.wait("document.querySelectorAll('[data-testid=\"pm-workflow\"]').length > 0", 20)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    seed(state)
    srv, url = serve(state)
    url = url.replace("mode=orchestra", "mode=packs").replace("#t=", "&tour=off&view=workspace#t=")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "packs")
        if as_dom:
            print(json.dumps({"packs": counts(c)}))
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
        from halo_harness.packs import bio_models
        bio_models.ROWS = None
