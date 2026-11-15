"""tests.helpers.studio_edit -- Studio as the one editor of agents, workflows and maps (Halo 3.1.1.0 R3; 3.6.0.0 R5: the
three tabs), driven in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver).
tests/test_studio_edit_route.py runs it as a subprocess with a scrubbed environment:

    python -m tests.helpers.studio_edit url     `?edit=agent:coder` opens Agents -> 1 · Agents on coder's form, nothing
                                                over it
    python -m tests.helpers.studio_edit focus   a page is open; `open_edit` (what `halo studio --edit` runs) on the
                                                running Studio focuses it: map:ship-it opens the Map on ship-it,
                                                workflow:code the Workflows tab on code, an old bio:reviewer 1 · Agents
                                                with the old files' line; no browser tab is opened

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

VIEW = "document.querySelector('[data-testid=\"agents\"]')?.dataset.view"


def q(testid: str) -> str:
    return f"document.querySelector('[data-testid=\"{testid}\"]')"


def section_tab(c) -> str:
    return c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")


def url(c, page: str, state: Path) -> dict:
    c.go(page)
    out = {"form": c.wait(f"{VIEW} === 'crew' && document.querySelector('[data-part=crew] [data-testid=crew-form]')?.dataset.name", 30)}
    out["section"] = section_tab(c)
    out["overlays"] = c.js("document.querySelectorAll('[role=dialog], [data-testid=start-here]').length")
    return out


def focus(c, page: str, state: Path, srv) -> dict:
    from halo_harness.studio import launch
    from halo_harness.studio.edit_open import open_edit
    from halo_harness.studio.edit_target import parse
    from halo_harness.studio.events import bridge_for
    out: dict = {}
    opened: list = []
    launch._open = lambda u: opened.append(u) or True  # a focused page needs no new tab; record any
    c.go(page)
    c.wait("document.querySelectorAll('[data-testid=\"section-tab\"]').length === 6", 30)
    end = time.time() + 15
    while time.time() < end and bridge_for(srv).listeners() < 1:
        time.sleep(0.1)
    out["listeners"] = bridge_for(srv).listeners()
    cwd = state.parent / "project"
    r = open_edit(parse("map:ship-it")[0], cwd=cwd, state_dir=state)
    out["map_how"], out["map_pages"] = r["how"], r["pages"]
    out["map"] = c.wait(f"{VIEW} === 'map' && {q('map-switcher')}?.value === 'ship-it' && {q('map-switcher')}.value", 20)
    r = open_edit(parse("workflow:code")[0], cwd=cwd, state_dir=state)
    out["flow"] = c.wait(f"{VIEW} === 'workflows' && document.querySelector('[data-part=workflows] [data-testid=flow-form]')?.dataset.name", 20)
    r = open_edit(parse("bio:reviewer")[0], cwd=cwd, state_dir=state)
    out["old_how"] = r["how"]
    out["old_view"] = c.wait(f"{VIEW} === 'crew' && {VIEW}", 20)
    out["old_line"] = c.wait("[...document.querySelectorAll('.toasts *')].map((t) => t.textContent).find((t) => t.includes('no longer read')) || ''", 10)
    out["tabs_opened"] = len(opened)
    out["url"] = r["url"].split("#")[0]
    return out


class EditDriver(Driver):
    """`url`: a page opened with `?edit=agent:coder`; `focus`: a running Studio focused by open_edit."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home
        from halo_harness.privateio import write_private_atomic
        from halo_harness.studio.server import start_server, studio_info_path, url_for
        state = seeded_home()
        proj = state.parent / "project"
        proj.mkdir(exist_ok=True)
        srv = start_server(port=0, cwd=proj, state_dir=state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        write_private_atomic(studio_info_path(state), json.dumps({"pid": 0, "port": srv.server_address[1], "token": srv.token, "owner_salt": srv.owner_salt}))
        try:
            if self.argv[:1] == ["focus"]:
                yield ((focus, (c, url_for(srv, "agents").replace("?mode=agents", "?mode=agents&tour=off"), state, srv)),)
            else:
                yield ((url, (c, url_for(srv, None, "agent:coder").replace("#t=", "&tour=off#t="), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(EditDriver(sys.argv[1:]).main())
