"""tests.helpers.studio_workflows -- Agents -> Workflows, the board of squares (Halo 3.3.16.0 R3), in headless Chrome on
the driver base over a scratch home (config `workflows.enabled: []`, the auto lineup). tests/test_studio_workflows.py
runs it:

    python -m tests.helpers.studio_workflows board   the empty board is one sentence and a Library button, nothing
                                                     open; the library's three groups; `/` focuses its search; a
                                                     drag of media raises the confirm card (what / cost / time /
                                                     writes), Enable puts the card on the board (240 x 140, the four
                                                     lines and the chip, on the 12 px grid, never overlapping) with
                                                     its one line; select shows the summary inspector, Enable and
                                                     Budget are pages; `x` takes a card off with its line; the keys
                                                     (arrows, Enter, Delete asks in the inspector); a session row
                                                     whose square agent runs makes exactly one square glow and one
                                                     edge move; every bar >= 36 px, every row >= 40 px

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
from tests.helpers.studio_agents import open_page  # noqa: E402

Q = "document.querySelector"
CARDS = "[...document.querySelectorAll('[data-testid=\"wf-card\"]')]"
DRAG = """(() => {{ const dt = new DataTransfer(); const row = {Q}('[data-testid="wf-row"][data-ref="{ref}"]');
  row.dispatchEvent(new DragEvent('dragstart', {{bubbles: true, dataTransfer: dt}}));
  const b = {Q}('[data-testid="wf-board"]');
  b.dispatchEvent(new DragEvent('dragover', {{bubbles: true, cancelable: true, dataTransfer: dt}}));
  b.dispatchEvent(new DragEvent('drop', {{bubbles: true, cancelable: true, dataTransfer: dt}})); return true; }})()"""


def press(c, key: str, code: str, vk: int, text: str = "") -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=code, windowsVirtualKeyCode=vk, modifiers=0,
               **({"text": text} if kind == "keyDown" and text else {}))


def tap(c, expr: str, until: str, timeout: float = 10, fx: float = 0.5, fy: float = 0.5):
    """Click `expr` and wait for `until`; a click on a board still laying out is tried again (three times)."""
    for attempt in range(3):
        c.wait(f"!!({expr})", timeout)
        c.click_on(expr, fx, fy)
        try:
            return c.wait(until, timeout if attempt == 2 else 3)
        except TimeoutError:
            if attempt == 2:
                raise
    return None


def text(testid: str) -> str:
    return f"({Q}('[data-testid=\"{testid}\"]')?.textContent || '')"


def empty(c, page) -> dict:
    open_page(c, page, "mode=agents&view=workflows")
    out = {"empty": c.wait(f"{text('wf-empty')}", 30)}
    out["quiet"] = c.js(f"({{library: !!{Q}('[data-testid=\"wf-library\"]'), inspector: !!{Q}('[data-testid=\"wf-inspector\"]'),"
                        f" confirm: !!{Q}('[data-testid=\"wf-confirm\"]'), dialogs: document.querySelectorAll('[role=dialog]').length,"
                        f" view: {Q}('[data-testid=\"agents\"]')?.dataset.view, button: !!{Q}('[data-testid=\"wf-library-open\"]')}})")
    return out


def library(c, page) -> dict:
    c.click_on(f"{Q}('[data-testid=\"wf-library-open\"]')")
    out = {"groups": c.wait(f"{Q}('[data-testid=\"wf-library\"]') && [...document.querySelectorAll('.wf-group')].map((g) => "
                            "g.dataset.group + ':' + g.querySelectorAll('[data-testid=\"wf-row\"]').length)", 15)}
    out["shipped_rows"] = c.js("[...document.querySelectorAll('[data-group=\"shipped\"] [data-testid=\"wf-row\"]')].map((r) => r.dataset.ref)")
    c.js("document.activeElement?.blur()")
    press(c, "/", "Slash", 191, "/")
    out["slash"] = c.wait(f"document.activeElement?.dataset.testid === 'wf-search' && 'search'", 10)
    c.js("document.activeElement?.blur()")
    return out


def drop(c, page) -> dict:
    c.js(DRAG.format(Q=Q, ref="media"))
    out = {"confirm": c.wait(f"{Q}('[data-testid=\"wf-confirm\"]') && [...{Q}('[data-testid=\"wf-confirm\"]').querySelectorAll('dt')]"
                             ".map((d) => d.textContent)", 10)}
    out["confirm_text"] = c.js(text("wf-confirm"))
    out["cards_before_ok"] = c.js(f"{CARDS}.length")
    c.click_on(f"{Q}('[data-testid=\"wf-confirm-enable\"]')")
    out["note_on"] = c.wait(f"{CARDS}.length === 1 && {text('wf-note')}", 15)
    out["card"] = c.js(f"(() => {{ const el = {CARDS}[0]; const r = el.getBoundingClientRect(); return {{w: r.width, h: r.height,"
                       " left: el.offsetLeft, top: el.offsetTop, labels: [...el.querySelectorAll('dt')].map((d) => d.textContent),"
                       " chip: el.querySelector('[data-testid=\"wf-card-limits\"]')?.textContent, name: el.dataset.ref,"
                       " kids: el.children.length}; })()")
    c.js(DRAG.format(Q=Q, ref="plan"))
    c.wait(f"!!{Q}('[data-testid=\"wf-confirm\"][data-ref=\"plan\"]')", 10)
    c.click_on(f"{Q}('[data-testid=\"wf-confirm-enable\"]')")
    out["two"] = c.wait(f"{CARDS}.length === 2 && {CARDS}.map((el) => [el.dataset.ref, el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight])", 15)
    out["edges"] = c.js("document.querySelectorAll('.wf-edge').length")
    out["moving_at_rest"] = c.js("document.querySelectorAll('.wf-edge[data-live]').length")
    return out


def inspect(c, page) -> dict:
    c.click_on(f"{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')", 0.5, 0.8)
    out = {"summary": c.wait(f"{Q}('[data-testid=\"wf-inspector\"][data-ref=\"media\"] [data-testid=\"wf-summary\"]') && "
                             f"[...{Q}('[data-testid=\"wf-summary\"]').querySelectorAll('dt')].map((d) => d.textContent)", 10)}
    out["edit_rows"] = c.js("[...document.querySelectorAll('[data-testid^=\"wf-block-\"]')].map((b) => b.dataset.testid)")
    c.click_on(f"{Q}('[data-testid=\"wf-edit-enable\"]')")
    out["enable_page"] = c.wait(f"{Q}('[data-testid=\"wf-page-enable\"]') && {text('wf-page-enable')}", 10)
    c.click_on(f"{Q}('[data-testid=\"wf-page-back\"]')")
    c.wait(f"!!{Q}('[data-testid=\"wf-summary\"]')", 10)
    c.click_on(f"{Q}('[data-testid=\"wf-edit-budget\"]')")
    out["budget_page"] = c.wait(f"{Q}('[data-testid=\"wf-page-budget\"]') && {text('wf-read-only')}", 10)
    out["budget_disabled"] = c.js(f"{Q}('[data-testid=\"wf-field-band\"]')?.disabled")
    c.click_on(f"{Q}('[data-testid=\"wf-page-back\"]')")
    return out


def keys(c, page) -> dict:
    c.js("document.activeElement?.blur()")
    c.key("Escape")
    out = {"esc": c.wait(f"!{Q}('[data-testid=\"wf-inspector\"]') && 'closed'", 10)}
    press(c, "ArrowRight", "ArrowRight", 39)
    out["arrow"] = c.wait(f"{Q}('[data-testid=\"wf-card\"][data-focus]')?.dataset.ref", 10)
    c.key("Enter")
    out["enter"] = c.wait(f"{Q}('[data-testid=\"wf-inspector\"]')?.dataset.ref", 10)
    press(c, "Delete", "Delete", 46)
    out["delete"] = c.wait(f"{Q}('[data-testid=\"wf-page-remove\"]') && {Q}('[data-testid=\"wf-inspector\"]').dataset.page", 10)
    out["delete_dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    c.key("Escape")
    return out


def remove(c, page) -> dict:
    c.click_on(f"{Q}('[data-testid=\"wf-card\"][data-ref=\"plan\"] [data-testid=\"wf-card-x\"]')")
    return {"note_off": c.wait(f"{CARDS}.length === 1 && {text('wf-note')}", 15)}


def density(c, page) -> dict:
    c.click_on(f"{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')", 0.5, 0.8)
    c.wait(f"!!{Q}('[data-testid=\"wf-summary\"]')", 10)
    if not c.js(f"!!{Q}('[data-testid=\"wf-library\"]')"):
        c.click_on(f"{Q}('[data-testid=\"wf-library-plus\"]')")
    c.wait(f"!!{Q}('[data-testid=\"wf-library\"]')", 10)
    return {"bars": c.js("[...document.querySelectorAll('[data-testid=\"agents\"] [data-density=\"bar\"]')].filter((e) => e.offsetParent)"
                         ".map((e) => [e.dataset.testid || e.className, Math.round(e.getBoundingClientRect().height)])"),
            "rows": c.js("[...document.querySelectorAll('[data-part=\"workflows\"] [data-density=\"row\"]')].filter((e) => e.offsetParent)"
                         ".map((e) => [e.dataset.testid || e.className, Math.round(e.getBoundingClientRect().height)])")}


def working(c, page, seed) -> dict:
    seed("running")
    open_page(c, page, "mode=agents&view=workflows")
    out = {}
    out["glow"] = c.wait(f"(() => {{ const g = {CARDS}.filter((el) => el.dataset.glow).map((el) => el.dataset.ref); return g.length ? g : null; }})()", 20)
    out["live_edges"] = c.js("[...document.querySelectorAll('.wf-edge[data-live]')].map((e) => e.dataset.ref)")
    out["working_cost"] = c.js(text("wf-working-cost"))
    open_page(c, page, "mode=agents&view=live")  # the same agent in Live: the square's name in mono, its engine, both costs
    out["live_square"] = c.wait(f"(() => {{ const n = {Q}('[data-testid=\"roles-live-square\"]'); const node = n?.closest('[data-testid=\"roles-live-node\"]');"
                                " return n && node ? [n.textContent, n.closest('[data-testid=\"roles-live-square-row\"]')?.dataset.engine, node.querySelector('[data-testid=\"roles-live-session-cost\"]')?.textContent] : null; })()", 20)
    return out


class WorkflowsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.fleet import local_view
        from halo_harness.studio.server import url_for
        from halo_harness.theme import set_config_value
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        set_config_value("workflows.enabled", [])
        srv, _url = serve(state)
        base = url_for(srv)
        orig = local_view.sessions

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")

        def seed(st: str) -> None:
            now = time.time()
            main = {"agent_id": "main", "parent": None, "name": "main", "role": "main", "state": "running", "since": now, "cost_usd": 0.1}
            sq = {"agent_id": "c1", "parent": "main", "name": "general-purpose", "kind": "subagent", "state": st, "since": now,
                  "cost_usd": 0.0123, "square": {"name": "media", "engine": "session"}}
            row = {"session_id": "sq-session", "title": "a PDF on a text-only model", "kind": "tui", "started": now, "cost_usd": 0.1123,
                   "model": "or:vendor/text-only", "agents": [main, sq]}
            local_view.sessions = lambda list_live=None: [row]
            local_view.forget()
        try:
            yield ((empty, (c, page)), (library, (c, page)), (drop, (c, page)), (inspect, (c, page)), (keys, (c, page)),
                   (remove, (c, page)), (density, (c, page)), (working, (c, page, seed)))
        finally:
            local_view.sessions = orig
            local_view.forget()
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(WorkflowsDriver(sys.argv[1:]).main())
