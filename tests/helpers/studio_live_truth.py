"""tests.helpers.studio_live_truth -- Agents -> Live, truth first (Halo 3.3.18.0 "The living canvas", the owner: "I always
see like unused older version of orchestrations that aren't even happening ... I'd love to see what is actually
happening") in headless Chrome on the driver base. tests/test_studio_live_truth.py runs both scenes:

    python -m tests.helpers.studio_live_truth past   a scratch home with an ended session (studio_fleet_parts.seed_past)
                                                     and a finished Orchestra run of Studio's repo, nothing live: a
                                                     bare ?mode=agents lands on Live's one empty sentence and its two
                                                     actions, no node, no run; History lists both (newest first); a
                                                     row opens a replay (banner, muted nodes), Back to now clears it;
                                                     the empty state's two actions; Cast's plan line, no live chip
    python -m tests.helpers.studio_live_truth now    the fleet rig (one live session): Alt+2 opens Agents on Live; a
                                                     named door still wins; Cast's plan line and its "N live" chip; the
                                                     rail badge counts live only; an agent that finishes leaves after
                                                     its stated ten seconds and its group with it; a failed one stays
                                                     until dismissed; a failure from before the page is not drawn

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_live_truth_now import NOW_STEPS  # noqa: E402

Q = "document.querySelector"
QA = "document.querySelectorAll"
VIEW = f"{Q}('[data-testid=\"agents\"]')?.dataset.view"
MAP = f"{Q}('[data-testid=\"roles-live-map\"]')"
EMPTY = f"{Q}('[data-testid=\"roles-live-empty\"]')"
BANNER = f"{Q}('[data-testid=\"live-replay-banner\"]')"
DRAWER = f"{Q}('[data-testid=\"live-history-drawer\"]')"
ROWS = f"[...{QA}('[data-testid=\"live-history-row\"]')]"
NODES = f"{QA}('[data-testid=\"roles-live-node\"]').length"


def open_page(c, page, query: str) -> None:
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(page(query))
    c.wait(f"{QA}('[data-testid=\"section-tab\"]').length > 0 && !!{Q}('.section-view')", 40)


def empty(c, page) -> dict:
    open_page(c, page, "mode=agents")
    out = {"view": c.wait(f"{VIEW} === 'live' && {VIEW}", 30)}
    out["line"] = c.wait(f"{EMPTY} && {Q}('[data-testid=\"live-empty-line\"]').textContent", 30)
    out["actions"] = c.wait(f"!{Q}('[data-testid=\"live-empty-replay\"]').disabled && [...{EMPTY}.querySelectorAll('button')].map((b) => b.textContent)", 20)
    out["nodes"] = c.js(NODES)
    out["leads"] = c.js(f"{QA}('[data-testid=\"agents-live-lead\"], [data-testid=\"agents-live-lane\"]').length")
    out["drawer_on_load"] = c.js(f"!!{DRAWER}")
    out["rail_count"] = c.js(f"{Q}('[data-testid=\"rail-fleet-count\"]')?.dataset.count || '0'")
    return out


def history(c, page) -> dict:
    btn = f"{Q}('[data-testid=\"live-history\"]')"
    out = {"count": c.wait(f"+{btn}?.dataset.count >= 2 && +{btn}.dataset.count", 20)}
    c.click_on(btn)
    out["rows"] = c.wait(f"{DRAWER} && {ROWS}.length >= 2 && {ROWS}.map((r) => [r.dataset.kind, r.dataset.id, r.querySelector('.lh-facts').textContent])", 20)
    return out


def replay(c, page, kind: str) -> dict:
    if not c.js(f"!!{DRAWER}"):
        c.click_on(f"{Q}('[data-testid=\"live-history\"]')")
        c.wait(f"{ROWS}.length >= 2", 20)
    c.click_on(f"{ROWS}.find((r) => r.dataset.kind === '{kind}')")
    sel = "[data-testid=\"roles-live-node\"]" if kind == "session" else "[data-testid=\"agents-live-lead\"], [data-testid=\"agents-live-lane\"]"
    out = {"banner": c.wait(f"{BANNER}?.dataset.kind === '{kind}' && {MAP}?.dataset.replay === 'true' && {QA}('{sel}').length > 0 && {BANNER}.textContent", 20)}
    out["drawn"] = c.js(f"[...{QA}('{sel}')].map((n) => [n.dataset.agent || n.dataset.lane || n.dataset.run, n.dataset.state || '', n.dataset.glow || '', getComputedStyle(n).filter])")
    out["drawer_closed"] = c.js(f"!{DRAWER}")
    c.click_on(f"{Q}('[data-testid=\"live-replay-back\"]')")
    out["back"] = c.wait(f"!{BANNER} && !{MAP}?.dataset.replay && !!{EMPTY} && {NODES} === 0 && 'now'", 15)
    return {f"replay_{kind}": out}


def empty_actions(c, page) -> dict:
    c.click_on(f"{Q}('[data-testid=\"live-empty-replay\"]')")
    out = {"replay_last": c.wait(f"{BANNER}?.dataset.kind === 'session' && {BANNER}.dataset.id", 20)}
    c.click_on(f"{Q}('[data-testid=\"live-replay-back\"]')")
    c.wait(f"!{BANNER} && !!{EMPTY}", 15)
    c.click_on(f"{Q}('[data-testid=\"live-empty-plan\"]')")
    out["plan"] = c.wait(f"{VIEW} === 'cast' && {VIEW}", 15)
    out["plan_line"] = c.wait(f"{Q}('[data-testid=\"cast-plan-line\"]')?.textContent", 30)
    out["live_chip"] = c.js(f"!!{Q}('[data-testid=\"cast-live-chip\"]')")
    return out


class LiveTruthDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        if "now" in self.argv:
            from tests.helpers.studio_fleet_rig import StudioFleetRig
            with StudioFleetRig() as rig:
                yield tuple((fn, (c, rig)) for fn in NOW_STEPS)
            return
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.orchestra_studio_rig import cleanup, finished_run
        from tests.helpers.studio_fleet_parts import PAST_SID, seed_past
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        repo, run_dir = finished_run()
        seed_past(state, repo)
        self.out["run"], self.out["past_sid"] = run_dir.name, PAST_SID
        srv, _url = serve(state, proj=repo)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off#t=")
        try:
            a = (c, page)
            yield ((empty, a), (history, a), (replay, (c, page, "session")), (replay, (c, page, "run")), (empty_actions, a))
        finally:
            srv.shutdown()
            srv.server_close()
            cleanup(repo)


if __name__ == "__main__":
    sys.exit(LiveTruthDriver(sys.argv[1:]).main())
