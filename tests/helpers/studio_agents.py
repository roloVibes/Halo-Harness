"""tests.helpers.studio_agents -- Agents, one section (Halo 3.3.16.0 R1) in headless Chrome on the driver base, over a
scratch home and a temp git repo (tests/helpers/orchestra_fixtures.py) holding a live Orchestra run whose workers wait
on a gate (tests/helpers/orchestra_studio_rig.py `fake_runner`): the lead split it into five lanes and each lane's
`lane:<n>` placeholder holds its claims. tests/test_studio_agents.py runs it:

    python -m tests.helpers.studio_agents agents   Alt+2 opens Agents on Cast with nothing else open; seven section
                                                   tabs; the doors (?mode=roles, roles&view=live, orchestra,
                                                   agents&view=runs|live) land on their views; ?mode=team lands on
                                                   Runs with Team's line once; C / R / L switch; each lane in Runs
                                                   says what it owns and a focused lane lists its claims (holder,
                                                   state); Live draws the run's lead and a lane node under it with
                                                   its number and worktree; Test this lineup is disabled on Auto with
                                                   the Auto line, enabled with a lineup of your own, its card first

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
TEST_BTN = "document.querySelector('[data-testid=\"agents-test-lineup\"]')"


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
    """From Session, Alt+2: Agents on Cast, the inspector closed, no dialog, no help."""
    open_page(c, page, "mode=session")
    c.js("document.activeElement?.blur()")
    key(c, "2", alt=True)
    out = {"alt2": c.wait(f"{ON} === 'agents' && {VIEW}", 20)}
    out["tabs"] = c.js(TABS)
    out["tab_ids"] = c.js("[...document.querySelectorAll('[data-testid=\"section-tab\"]')].map((t) => t.dataset.tabId + ':' + (t.dataset.kbd || ''))")
    out["quiet"] = c.js("({inspector: document.querySelector('.app').dataset.inspector, dialogs: document.querySelectorAll('[role=dialog]').length,"
                        " help: !!document.querySelector('[data-testid=\"section-help\"]'), cast_on: document.querySelector("
                        "'[data-testid=\"agents-view-cast\"]')?.getAttribute('aria-pressed')})")
    out["cast_body"] = c.wait("document.querySelector('[data-part=\"roles\"]:not([hidden]) [data-testid=\"roles-start\"],"
                              " [data-part=\"roles\"]:not([hidden]) [data-testid=\"roles-canvas\"]') ? 'roles' : ''", 30)
    return out


def doors(c, page) -> dict:
    out = {}
    for q in ("mode=roles", "mode=roles&view=live", "mode=orchestra", "mode=agents&view=runs", "mode=agents&view=live", "mode=agents",
              "mode=agents&view=workflows"):  # 3.3.16.0 R3: the fourth view
        open_page(c, page, q)
        out[q] = c.wait(f"{ON} === 'agents' && {VIEW}", 30)
    return out


def team_note(c, page) -> dict:
    out = {}
    open_page(c, page, "mode=team")
    out["first"] = c.wait(f"{VIEW} === 'runs' && [{VIEW}, {NOTE}?.textContent || '']", 30)
    open_page(c, page, "mode=team")
    c.wait(f"{VIEW} === 'runs'", 30)
    time.sleep(0.5)
    out["again"] = [c.js(VIEW), c.js(f"!!{NOTE}")]
    return out


def view_keys(c, page) -> dict:
    open_page(c, page, "mode=agents")
    c.wait(f"{VIEW} === 'cast'", 30)
    c.js("document.activeElement?.blur()")
    out = {}
    for ch, want in (("r", "runs"), ("l", "live"), ("w", "workflows"), ("c", "cast")):  # 3.3.16.0 R3: W the board
        key(c, ch)
        out[ch] = c.wait(f"{VIEW} === '{want}' && {VIEW}", 10)
    return out


def owns(c, page) -> dict:
    """Runs on the live run (its Lanes panel open: `open=lanes`): every lane's owns line, then a focused lane's claims."""
    open_page(c, page, "mode=agents&view=runs&open=lanes")
    lane = "document.querySelector('[data-testid=\"lane\"][data-lane=\"1\"]')"
    out = {"owns": c.wait("(() => { const o = [...document.querySelectorAll('[data-testid=\"lane-owns\"]')];"
                          " return o.length >= 5 && o.every((x) => +x.dataset.count > 0) && o.map((x) => x.textContent); })()", 40)}
    c.click_on(f"{lane}.querySelector('.og-lane-head')")
    out["claims"] = c.wait(f"(() => {{ const r = [...{lane}.querySelectorAll('[data-testid=\"lane-claim\"]')];"
                           " return r.length && r.map((x) => [x.dataset.holder, x.dataset.state, x.textContent]); })()", 15)
    return out


def live_lanes(c, page) -> dict:
    open_page(c, page, "mode=agents&view=live")
    lead = "document.querySelector('[data-testid=\"agents-live-lead\"]')"
    out = {"lanes": c.wait("(() => { const l = [...document.querySelectorAll('[data-testid=\"agents-live-lane\"]')];"
                           " return l.length >= 5 && l.map((x) => [+x.dataset.lane, x.dataset.lc, x.dataset.worktree || '']); })()", 40)}
    out["lead"] = c.js(f"{lead}?.dataset.run || ''")
    out["edges"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-live-edge\"]')].map((e) => [e.dataset.from, e.dataset.to])"
                        ".filter(([, t]) => t.includes(':lane:')).length")
    out["under_lead"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-live-edge\"]')].filter((e) => e.dataset.to.includes(':lane:'))"
                             ".every((e) => e.dataset.from.startsWith('run:'))")
    return out


def test_lineup(c, page, seed_lineup) -> dict:
    """Auto: disabled with the line. A lineup of your own: enabled; its dialog shows the card first."""
    open_page(c, page, "mode=agents&view=runs")
    out = {"auto": c.wait(f"{TEST_BTN} && document.querySelector('[data-testid=\"agents-test-auto\"]') && [{TEST_BTN}.disabled,"
                          " document.querySelector('[data-testid=\"agents-test-auto\"]').textContent]", 30)}
    seed_lineup()
    open_page(c, page, "mode=agents&view=runs")
    out["enabled"] = c.wait(f"{TEST_BTN} && !{TEST_BTN}.disabled && !document.querySelector('[data-testid=\"agents-test-auto\"]') && 'enabled'", 30)
    c.click_on(TEST_BTN)
    dlg = "document.querySelector('[data-testid=\"agents-test\"]')"
    card = f"{dlg}?.querySelector('[data-testid=\"agents-test-card\"]')"
    out["card"] = c.wait(f"{card} && !{card}.textContent.startsWith('reading') && {card}.textContent", 20)
    out["card_first"] = c.js(f"(() => {{ const run = {dlg}.querySelector('[data-testid=\"agents-test-run\"]');"
                             f" return !!run && !run.disabled && !!({card}.compareDocumentPosition(run) & Node.DOCUMENT_POSITION_FOLLOWING); }})()")
    c.key("Escape")
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

        def seed_lineup() -> None:
            from halo_harness.teams_yaml import ensure_builtin_team_templates
            from halo_harness.theme import set_config_value
            ensure_builtin_team_templates(state_dir=state)
            set_config_value("team", "halo-dev-cycle")
            set_config_value("roles.enabled", True)
        try:
            self.start_run(srv, repo)
            yield ((cast_first, (c, page)), (doors, (c, page)), (team_note, (c, page)), (view_keys, (c, page)),
                   (owns, (c, page)), (live_lanes, (c, page)), (test_lineup, (c, page, seed_lineup)))
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
