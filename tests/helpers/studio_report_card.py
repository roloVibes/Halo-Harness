"""tests.helpers.studio_report_card -- the run report card (Halo 3.4.1.0 R3 "Time") and Session's mode word in headless
Chrome on the driver base, over a scratch home with two ended sessions and a finished goal run in Studio's folder
(tests/helpers/card_seed.py), nothing live until the last step. tests/test_studio_report_card.py reads it:

    python -m tests.helpers.studio_report_card

`card`: the goal run's card on its own page (its door `&run=<id>`; 3.6.0.3 B: History and a past session's card left
Studio): the nine figures, the story, every section, its file, what the record cannot show, Copy on; the card is the
report page's FIRST block, before the plan and its lanes, and the report's doors are kept.
`mode`: a real Controller behind its control socket, registered in auto mode: Session's bar says "auto" with its meaning
on hover; set to plan (the session and its registry row) while its feed is held from Studio (3.4.1.0 R6), the
page's first word after a reload is "plan".
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
from tests.helpers.studio_replay_time import Q, QA, open_page  # noqa: E402

CARD = f"{Q}('[data-testid=\"report-card\"]')"
MODE = f"{Q}('[data-testid=\"session-mode\"]')"


def _read(c) -> dict:
    """What the card on the page shows."""
    return {"figures": c.js(f"[...{QA}('[data-testid=\"report-card-figure\"]')].map((f) => [f.dataset.key, f.querySelector('dd').textContent])"),
            "story": c.js(f"[...{QA}('[data-testid=\"report-card-step\"]')].map((s) => s.textContent)"),
            "sections": c.js(f"[...{QA}('[data-testid=\"report-card-section\"]')].map((s) => s.dataset.key)"),
            "arts": c.js(f"[...{QA}('[data-testid=\"report-card-art\"]')].map((a) => a.dataset.rel)"),
            "cannot": c.js(f"[...{QA}('[data-testid=\"report-card-cannot\"]')].map((a) => a.textContent)"),
            "copy_on": c.js(f"!{Q}('[data-testid=\"report-card-copy\"]').disabled")}


def card(c, page, run: str) -> dict:
    """The goal run's card from its own page (Z11: the card opens from the run's page; History's door left)."""
    open_page(c, page, f"mode=agents&run={run}")
    c.wait(f"{Q}('[data-testid=\"history-report\"]')?.dataset.run === '{run}' && {CARD}?.dataset.state === 'ready'", 30)
    out = {"a": _read(c), "run_ref": c.js(f"{CARD}.dataset.ref")}
    out["run_first"] = c.js(f"""(() => {{ const r = {Q}('[data-testid="history-report"]');
      const blocks = [...r.querySelectorAll('[data-testid="report-card"], [data-testid^="history-report-"].rr-block')];
      return blocks.length ? blocks[0].dataset.testid : ''; }})()""")
    out["run_story"] = c.js(f"[...{QA}('[data-testid=\"report-card-step\"]')].map((s) => s.textContent)")
    out["run_kept"] = c.js(f"['history-report-back', 'history-report-replay', 'history-report-again', 'history-report-lanes']"
                           f".every((t) => !!{Q}(`[data-testid=\"${{t}}\"]`))")
    return out


DRAWER = f"{Q}('[data-testid=\"map-drawer\"]')"
REPORT = f"{Q}('[data-testid=\"history-report\"]')"
TITLE = f"{Q}('[data-testid=\"map-drawer-panel\"] [data-testid=\"panel-title\"]')?.textContent"
SHUT = (f"!{Q}('[data-testid=\"map-drawer-panel\"]') && !{DRAWER}"  # a closed drawer is not drawn; its view bar button stays
        f" && !!{Q}('[data-testid=\"viewbar-btn\"][data-panel=\"map-drawer\"]')")
RECT = ("(() => { const r = document.querySelector('[data-testid=\"viewbar-btn\"][data-panel=\"map-drawer\"]')?.getBoundingClientRect();"
        " return r ? [r.x, r.y, r.width, r.height] : null; })()")


def _on_report(c, run: str) -> dict:
    """The drawer on the run's own report page: what it shows."""
    c.wait(f"{DRAWER}?.dataset.page === 'report:{run}' && {REPORT}?.dataset.run === '{run}' && {CARD}?.dataset.state === 'ready'", 30)
    return {"page": c.js(f"{DRAWER}.dataset.page"), "title": c.js(TITLE), "rect": c.js(RECT),
            "history_open": c.js(f"!!{Q}('[data-testid=\"live-history-drawer\"]') || !!{Q}('[data-testid=\"history-page\"]')"),
            "back_title": c.js(f"{Q}('[data-testid=\"history-report-back\"]').title"),
            "kept": c.js(f"['history-report-back', 'history-report-replay', 'history-report-again', 'history-report-lanes']"
                         f".every((t) => !!{Q}(`[data-testid=\"${{t}}\"]`))"),
            "first": c.js(f"""(() => {{ const blocks = [...{REPORT}.querySelectorAll('[data-testid="report-card"], [data-testid^="history-report-"].rr-block')];
              return blocks.length ? blocks[0].dataset.testid : ''; }})()""")}


def run_page(c, page, run: str) -> dict:
    """3.6.0.3 B batch 1: a finished goal run's report is its own drawer page `report:<id>`, "Goal run", from its doors
    (`&run=<id>`, the palette's "Goal run <id>"); Back (no run page sent him) closes the drawer; the view bar's drawer
    button keeps one rect on every drawer page (report, goal; History's page left in batch 3)."""
    open_page(c, page, f"mode=agents&run={run}")
    out = {"url": _on_report(c, run)}
    c.click_on(f"{Q}('[data-testid=\"history-report-back\"]')")
    out["back_shut"] = c.wait(f"{SHUT} && 'shut'", 15)
    c.click_on(f"{Q}('.palette-btn')")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text(f"Goal run {run}")
    rows = "[...document.querySelectorAll('[data-testid=palette] .palette-item')]"
    out["palette_first"] = c.wait(f"{rows}[0]?.querySelector('.palette-label')?.textContent", 15)
    c.key("Enter")
    out["palette"] = _on_report(c, run)
    c.click_on(f"{Q}('[data-testid=\"map-run-goal\"]')")
    c.wait(f"{DRAWER}?.dataset.page === 'goal' && !!{Q}('[data-testid=\"run-goal-drawer\"]')", 15)
    out["goal"] = {"title": c.js(TITLE), "rect": c.js(RECT)}
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
    """3.4.1.0 R6: the session's feed is held (Studio's bridge attaches it only after the page has read its new word),
    the order the Windows runner showed: the mode moves before any frame of the session reaches Studio, so the page
    has GET fleet alone, and GET fleet must say the registry's word at once (it answered a snapshot from before)."""
    import threading
    from halo_harness.studio import events
    gate, real = threading.Event(), events.EventBridge._pump

    def held(bridge, entry, stop):
        gate.wait(90)
        return real(bridge, entry, stop)
    events.EventBridge._pump = held
    try:
        return _mode(c, page, gate)
    finally:
        gate.set()
        events.EventBridge._pump = real


def _mode(c, page, gate) -> dict:
    from halo_harness.remote.registry import update
    with _Session("auto") as s:
        open_page(c, page, "mode=session")
        out = {"word": c.wait(f"{MODE}?.dataset.mode", 40), "title": c.js(f"{MODE}.title"), "text": c.js(f"{MODE}.textContent")}
        s.handle.set_mode("plan")  # the session's own mode (its status frames say it) and the registry's (runtime.py's tap)
        update(s.handle.session_id, mode="plan")
        open_page(c, page, "mode=session")
        out["first_after"] = c.wait(f"{MODE}?.dataset.mode", 40)  # the first word the new page shows
        gate.set()
        try:
            out["after"] = c.wait(f"{MODE}?.dataset.mode === 'plan' && {MODE}.textContent", 40)
        except TimeoutError as e:  # 3.4.1.0 R6: say what the page and the registry held, not only that it waited
            from halo_harness.remote.registry import list_live
            rows = [(r.get("session_id") == s.handle.session_id, r.get("mode")) for r in list_live()]
            raise TimeoutError(f"{e} -- the page's word: {c.js(f'{MODE}?.dataset.mode || null')!r}, the registry's live rows "
                               f"(ours, mode): {rows}") from None
    return out


class ReportCardDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.card_seed import RUN, seed_all
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        repo = seed_all(state)
        srv, _url = serve(state, proj=repo)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid#t=")
        try:
            yield ((card, (c, page, RUN)), (run_page, (c, page, RUN)), (mode, (c, page)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(ReportCardDriver(sys.argv[1:]).main())
