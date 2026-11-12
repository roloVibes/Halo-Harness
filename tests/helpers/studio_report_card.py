"""tests.helpers.studio_report_card -- the run report card (Halo 3.4.1.0 R3 "Time") and Session's mode word in headless
Chrome on the driver base, over a scratch home with two ended sessions and a finished goal run in Studio's folder
(tests/helpers/card_seed.py), nothing live until the last step. tests/test_studio_report_card.py reads it:

    python -m tests.helpers.studio_report_card

`ended`: Agents -> Live with nothing running: no drawer, no card on load; the row for the session that ended last
(a row, not a pop-up) opens its card as a page of History: the nine figures (its unpriced cost "$0.0120+"), the story.
`doors`: History's rows each have a Report door (session, run); session A's card: nine story steps, every section, the
fixer's file, what the record cannot show, Copy on; Back; the goal run's Report: its report page with the card as its
FIRST block, before the plan and its lanes.
`mode`: a real Controller behind its control socket, registered in auto mode: Session's bar says "auto" with its meaning
on hover; set to plan (the session and its registry row), the page says "plan".
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_replay_time import Q, QA, history, open_page  # noqa: E402

CARD = f"{Q}('[data-testid=\"report-card\"]')"
DOOR = f"{Q}('[data-testid=\"live-history-card\"][data-kind=\"{{}}\"][data-id=\"{{}}\"]')"
MODE = f"{Q}('[data-testid=\"session-mode\"]')"


def _read(c) -> dict:
    """What the card on the page shows."""
    return {"figures": c.js(f"[...{QA}('[data-testid=\"report-card-figure\"]')].map((f) => [f.dataset.key, f.querySelector('dd').textContent])"),
            "story": c.js(f"[...{QA}('[data-testid=\"report-card-step\"]')].map((s) => s.textContent)"),
            "sections": c.js(f"[...{QA}('[data-testid=\"report-card-section\"]')].map((s) => s.dataset.key)"),
            "arts": c.js(f"[...{QA}('[data-testid=\"report-card-art\"]')].map((a) => a.dataset.rel)"),
            "cannot": c.js(f"[...{QA}('[data-testid=\"report-card-cannot\"]')].map((a) => a.textContent)"),
            "copy_on": c.js(f"!{Q}('[data-testid=\"report-card-copy\"]').disabled")}


def ended(c, page, sid_b: str) -> dict:
    open_page(c, page, "mode=agents")
    row = f"{Q}('[data-testid=\"live-empty-card\"]')"
    out = {"row": c.wait(f"{row}?.dataset.id", 30)}
    out["quiet"] = c.js(f"!{Q}('[data-testid=\"live-history-drawer\"]') && !{CARD}")
    out["row_text"] = c.js(f"{row}.textContent")
    c.click_on(row)
    c.wait(f"{CARD}?.dataset.state === 'ready' && {CARD}.dataset.ref === 'session:{sid_b}'", 30)
    out["page"] = c.js(f"{Q}('[data-testid=\"history-page\"]')?.dataset.kind")
    out["b"] = _read(c)
    c.click_on(f"{Q}('[data-testid=\"report-card-back\"]')")
    c.wait(f"!{CARD} && {QA}('[data-testid=\"live-history-row\"]').length >= 3", 15)
    return out


def doors(c, sid: str, run: str) -> dict:
    history(c)
    out = {"doors": c.js(f"[...{QA}('[data-testid=\"live-history-card\"]')].map((d) => d.dataset.kind + ':' + d.dataset.id)")}
    c.click_on(DOOR.format("session", sid))
    c.wait(f"{CARD}?.dataset.state === 'ready' && {CARD}.dataset.ref === 'session:{sid}'", 30)
    out["a"] = _read(c)
    c.click_on(f"{Q}('[data-testid=\"report-card-back\"]')")
    c.wait(f"!{CARD}", 15)
    c.click_on(DOOR.format("run", run))
    c.wait(f"{Q}('[data-testid=\"history-report\"]')?.dataset.run === '{run}' && {CARD}?.dataset.state === 'ready'", 30)
    out["run_ref"] = c.js(f"{CARD}.dataset.ref")
    out["run_first"] = c.js(f"""(() => {{ const r = {Q}('[data-testid="history-report"]');
      const blocks = [...r.querySelectorAll('[data-testid="report-card"], [data-testid^="history-report-"].rr-block')];
      return blocks.length ? blocks[0].dataset.testid : ''; }})()""")
    out["run_story"] = c.js(f"[...{QA}('[data-testid=\"report-card-step\"]')].map((s) => s.textContent)")
    out["run_kept"] = c.js(f"['history-report-back', 'history-report-replay', 'history-report-again', 'history-report-lanes']"
                           f".every((t) => !!{Q}(`[data-testid=\"${{t}}\"]`))")
    return out


class _Session:
    """A real Controller behind its control socket, registered in `home`'s sessions in `mode` (no model call)."""

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def __enter__(self) -> "_Session":
        from halo_harness.controller import Controller
        from halo_harness.remote.control_socket import ControlServer
        from halo_harness.remote.handle import ControllerHandle
        from halo_harness.remote.registry import make_entry, register
        from tests.helpers.mock_openai import MockUpstream
        from tests.helpers.turn_session import new_session
        keep = os.environ.get("BRIDGE_TEST_HOME")
        self.mock = MockUpstream().start()
        session = new_session(mock=self.mock, model="or:mock/card", mode=self.mode)
        os.environ["BRIDGE_TEST_HOME"] = keep or ""  # new_session scoped a home of its own: Studio's stays this one
        self.controller = Controller(session=session, cwd=session.cwd)
        self.controller.start()
        self.handle = ControllerHandle(self.controller)
        self.handle.attach()
        self.server = ControlServer(self.handle).start()
        register(make_entry(session_id=self.handle.session_id, cwd=session.cwd, endpoint=self.server.endpoint, token=self.server.token,
                            mode=self.mode, title="the mode word"))
        return self

    def __exit__(self, *exc) -> None:
        for fn in (self.server.close, self.handle.detach, self.controller.quit, self.mock.stop):
            try:
                fn()
            except Exception:
                pass


def mode(c, page) -> dict:
    from halo_harness.remote.registry import update
    with _Session("auto") as s:
        open_page(c, page, "mode=session")
        out = {"word": c.wait(f"{MODE}?.dataset.mode", 40), "title": c.js(f"{MODE}.title"), "text": c.js(f"{MODE}.textContent")}
        s.handle.set_mode("plan")  # the session's own mode (its status frames say it) and the registry's (runtime.py's tap)
        update(s.handle.session_id, mode="plan")
        open_page(c, page, "mode=session")
        out["after"] = c.wait(f"{MODE}?.dataset.mode === 'plan' && {MODE}.textContent", 40)
    return out


class ReportCardDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.card_seed import RUN, SID, SID_B, seed_all
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        repo = seed_all(state)
        srv, _url = serve(state, proj=repo)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid#t=")
        try:
            yield ((ended, (c, page, SID_B)), (doors, (c, SID, RUN)), (mode, (c, page)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(ReportCardDriver(sys.argv[1:]).main())
