"""tests.helpers.studio_agents -- Agents, one section (Halo 3.3.16.0 R1) in headless Chrome on the driver base, over a
scratch home and a temp git repo (tests/helpers/orchestra_fixtures.py) holding a live Orchestra run whose workers wait
on a gate (tests/helpers/orchestra_studio_rig.py `fake_runner`): the lead split it into five lanes and each lane's
`lane:<n>` placeholder holds its claims. tests/test_studio_agents.py runs it:

    python -m tests.helpers.studio_agents agents   Alt+2 opens Agents on 1 · Agents (3.6.0.0 R1) with nothing else open; six section
                                                   tabs; the doors (?mode=roles, roles&view=live, orchestra,
                                                   agents&view=runs|live) land on their views (3.4.0.0 D: Runs' on
                                                   Live); ?mode=team lands on Live with Team's line once; C / R / L / W
                                                   switch (R lands on Live); Live draws the run's lead and its lanes
                                                   in the run's block, each with its number, worktree and owns row; a
                                                   lane's click is its summary, its Claims page lists the claims

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called (HALO_START_FAKE=1)."""
from __future__ import annotations

import json
import os
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
TABS = "document.querySelectorAll('[data-testid=\"section-tab\"]').length"
ON = "document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.dataset.tabId"
NOTE = "document.querySelector('[data-testid=\"agents-team-note\"]')"


def key(c, ch: str, alt: bool = False) -> None:
    """One key press: a letter (C, R, L) or, with `alt`, Alt+<digit>."""
    code = f"Digit{ch}" if ch.isdigit() else f"Key{ch.upper()}"
    vk = ord(ch.upper())
    for kind in ("keyDown", "keyUp"):
        extra = {"text": ch} if kind == "keyDown" and not alt else {}
        c.call("Input.dispatchKeyEvent", type=kind, key=ch, code=code, windowsVirtualKeyCode=vk, modifiers=1 if alt else 0, **extra)


def open_page(c, page, query: str) -> None:
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(page(query))
    c.wait(f"{TABS} > 0 && !!document.querySelector('.section-view')", 40)


def cast_first(c, page) -> dict:
    """From Session, Alt+2: Agents on Live (3.3.18.0: what runs now; here, the live run's lanes), the inspector closed,
    no dialog, no help."""
    open_page(c, page, "mode=session")
    c.js("document.activeElement?.blur()")
    key(c, "2", alt=True)
    out = {"alt2": c.wait(f"{ON} === 'agents' && {VIEW}", 20)}
    out["tabs"] = c.js(TABS)
    out["tab_ids"] = c.js("[...document.querySelectorAll('[data-testid=\"section-tab\"]')].map((t) => t.dataset.tabId + ':' + (t.dataset.kbd || ''))")
    out["quiet"] = c.js("({inspector: document.querySelector('.app').dataset.inspector, dialogs: document.querySelectorAll('[role=dialog]').length,"
                        " help: !!document.querySelector('[data-testid=\"section-help\"]'), live_on: document.querySelector("
                        "'[data-testid=\"agents-view-crew\"]')?.getAttribute('aria-pressed')})")
    # 3.6.0.0 R1: Alt+2 opens the Agents tab (routes/crew/), drawn in its own room
    out["cast_body"] = c.wait("document.querySelector('[data-part=\"crew\"]:not([hidden]) [data-testid=\"crew-form-panel\"]') ? 'crew' : ''", 30)
    return out


def doors(c, page) -> dict:
    out = {}
    for q in ("mode=roles", "mode=roles&view=live", "mode=orchestra", "mode=agents&view=runs", "mode=agents&view=live", "mode=agents",
              "mode=agents&view=workflows", "mode=agents&view=crew"):  # 3.3.16.0 R3: the fourth view; 3.6.0.0 R1: the Agents tab
        open_page(c, page, q)
        out[q] = c.wait(f"{ON} === 'agents' && {VIEW}", 30)
    return out


def team_note(c, page) -> dict:
    out = {}
    open_page(c, page, "mode=team")
    out["first"] = c.wait(f"{VIEW} === 'live' && [{VIEW}, {NOTE}?.textContent || '']", 30)
    open_page(c, page, "mode=team")
    c.wait(f"{VIEW} === 'live' && !!document.querySelector('[data-testid=\"roles-live-map\"]')", 30)
    out["again"] = [c.js(VIEW), c.js(f"!!{NOTE}")]
    return out


def view_keys(c, page) -> dict:
    open_page(c, page, "mode=agents")
    c.wait(f"{VIEW} === 'live'", 30)  # 3.3.18.0: a bare door opens on Live
    c.js("document.activeElement?.blur()")
    out = {}
    for ch, want in (("r", "live"), ("w", "workflows"), ("l", "live"), ("c", "cast"), ("1", "crew")):  # 3.3.16.0 R3: W; 3.4.0.0 D: R lands on Live; 3.6.0.0 R1: 1
        key(c, ch)
        out[ch] = c.wait(f"{VIEW} === '{want}' && {VIEW}", 10)
    return out


def owns(c, page) -> dict:
    """3.4.0.0 D: Live on the live run: every lane box's OWNS row, then lane 1's summary and its Claims page."""
    open_page(c, page, "mode=agents&view=live&plan=off")
    lane = "document.querySelector('[data-testid=\"agents-live-lane\"][data-lane=\"1\"]')"
    out = {"owns": c.wait("(() => { const o = [...document.querySelectorAll('[data-testid=\"lane-owns\"]')];"
                          " return o.length >= 5 && o.every((x) => x.textContent.includes('basket.py#')) && o.map((x) => x.textContent); })()", 40)}
    c.click_on(lane)
    c.wait("document.querySelector('[data-testid=\"run-inspector\"]')?.dataset.lane === '1'", 15)
    c.click_on("document.querySelector('[data-testid=\"run-open-claims\"]')")
    out["claims"] = c.wait("(() => { const r = [...document.querySelectorAll('[data-testid=\"run-page\"] [data-testid=\"lane-claim\"]')];"
                           " return r.length && r.map((x) => [x.dataset.holder, x.dataset.state, x.textContent]); })()", 15)
    return out


def live_lanes(c, page) -> dict:
    open_page(c, page, "mode=agents&view=live&plan=off")  # the tree (3.3.18.0's plan under it off): the run's block under its lead
    lead = "document.querySelector('[data-testid=\"agents-live-lead\"]')"
    out = {"lanes": c.wait("(() => { const l = [...document.querySelectorAll('[data-testid=\"agents-live-lane\"]')];"
                           " return l.length >= 5 && l.map((x) => [+x.dataset.lane, x.dataset.lc, x.dataset.worktree || '']); })()", 40)}
    out["lead"] = c.js(f"{lead}?.dataset.run || ''")
    box = "document.querySelector('[data-testid=\"live-group\"][data-kind=\"run\"]')"
    out["block"] = c.js(f"{box} ? [{box}.dataset.group, {box}.querySelectorAll('[data-testid=\"agents-live-lane\"]').length"
                        f" || document.querySelectorAll('[data-testid=\"agents-live-lane\"]').length] : null")
    return out


class AgentsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio import orchestra_api, orchestra_live
        from halo_harness.studio.server import url_for
        from tests.helpers import orchestra_fixtures as F
        from tests.helpers.orchestra_studio_rig import cleanup, fake_runner
        os.environ["HALO_START_FAKE"] = "1"  # the driver env scrubs HALO_*: the card names the fakes, nothing is called
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        repo = F.make_repo("agents-")
        gate = threading.Event()
        saved, orchestra_api.RUNNER = orchestra_api.RUNNER, fake_runner(gate)
        srv, _url = serve(state, proj=repo)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")

        try:
            self.start_run(srv, repo)
            yield ((cast_first, (c, page)), (doors, (c, page)), (team_note, (c, page)), (view_keys, (c, page)),
                   (owns, (c, page)), (live_lanes, (c, page)))  # 3.4.0.0 B: Test this lineup is the first-run pack's
        finally:
            gate.set()
            orchestra_live.wait(30)  # the run ends before its repo goes
            orchestra_api.RUNNER = saved
            srv.shutdown()
            srv.server_close()
            cleanup(repo)

    def start_run(self, srv, repo: Path) -> None:
        """POST orchestra/run, then wait until the five lanes hold their claims (the workers wait on the gate)."""
        import urllib.request
        from halo_harness.studio.owner_proof import HEADER, header_for
        port = srv.server_address[1]

        def call(method: str, path: str, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/{path}", method=method,
                                         data=json.dumps(body).encode("utf-8") if body is not None else None)
            req.add_header("Authorization", "Bearer " + srv.token)
            req.add_header(HEADER, header_for(srv))
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read() or b"{}")
        goal = {"what": "write the five basket functions", "done_when": "the tests pass", "stop_when": "two returns",
                "workers": 5, "return_cap": 2, "test": "", "files": ["basket.py"], "lineup": "", "lead": "", "worker": "", "force": True}
        run_id = call("POST", "orchestra/run", goal)["run_id"]
        end = time.time() + 40
        while time.time() < end:
            data = call("GET", f"orchestra/{run_id}")
            if data.get("live") and len(data.get("lanes") or []) >= 5 and len(data.get("claims") or []) >= 5:
                self.out["run"] = run_id
                return
            time.sleep(0.2)
        raise TimeoutError(f"run {run_id}: the lanes never held their claims")


if __name__ == "__main__":
    sys.exit(AgentsDriver(sys.argv[1:]).main())
