"""tests.helpers.studio_live -- the Studio live checks (Halo 3.0.5.0 round R3) driven through real clicks and keys in
headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over tests/helpers/studio_session_rig.py (this
harness's real session with three agents mid-work). tests/test_studio_ui.py runs it as a subprocess with a scrubbed
environment:

    python -m tests.helpers.studio_live map     # Agents -> Live: the nodes, the tree's order, select + tail, J/K, steer, stop
    python -m tests.helpers.studio_live roles   # Live Roles on the React canvas: the glow, the Live tab's text and tool rows, J, the pin
    python -m tests.helpers.studio_live panels  # R4: timeline, replay, record and take over (studio_live_panels.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

DETAIL = "document.querySelector('[data-testid=\"fleet-agent-detail\"]')"
NODE = "[data-testid=\"roles-live-node\"]"  # 3.3.16.0 R2: Live's node is the one agent node (the Fleet map's went)


def node(name: str) -> str:
    return f"[...document.querySelectorAll('{NODE}')].find((n) => n.querySelector('.rlm-name').textContent.startsWith('{name}'))"


MAP_SVG = "document.querySelector('[data-testid=\"roles-live-map\"]')"
NODES_SEEN = f"[...document.querySelectorAll('{NODE}')].map((n) => (n.querySelector('.rlm-name')?.textContent || '?') + ':' + n.dataset.state)"


def wait_node(c, name: str, cond: str = "true", timeout: float = 60):
    """3.1.5.0 R3 follow-up: the map has drawn (its `data-nodes` mark), then the node named `name` with `cond`
    true on it (`n` in JS); returns its state. On a timeout the error names every node and state it saw."""
    import time
    end = time.time() + timeout
    try:
        c.wait(f"+({MAP_SVG}?.dataset.nodes || 0) > 0", timeout)
        return c.wait(f"(() => {{ const n = {node(name)}; return !!n && ({cond}) && (n.dataset.state || 'drawn'); }})()", max(1.0, end - time.time()))
    except TimeoutError:
        raise TimeoutError(f"waited {timeout:g}s for the node {name!r} with {cond}; the map's data-nodes={c.js(f'{MAP_SVG}?.dataset.nodes')!r},"
                           f" it showed {c.js(NODES_SEEN)}") from None


def expected_tree(view: dict, live_only: bool = True) -> list:
    """The tree's order: each session's agents depth first (as GET live has them)."""
    out = []
    for h in view.get("harnesses", []):
        for s in h.get("sessions") or []:
            rows = s.get("agents") or []
            ids = {a["agent_id"] for a in rows}

            up = lambda a: a.get("parent") if a.get("parent") in ids else None  # noqa: E731
            live = lambda a: not live_only or a.get("state") in ("queued", "running", "waiting", "paused") or any(up(k) == a["agent_id"] and live(k) for k in rows)  # noqa: E731

            def walk(parent, depth):  # 3.3.18.0: Live draws an agent while it (or one under it) works; a finished one is past
                for a in rows:
                    if up(a) == parent and live(a):
                        out.append(f"agent:{a['agent_id']}")
                        if depth < 8:
                            walk(a["agent_id"], depth + 1)
            walk(None, 0)
    return out


def select_node(c, name: str, key: str, tries: int = 3):
    """Click the node until the Agent detail shows its key: the GitHub Windows runner lost the click in
    two of four runs (the node can move between the rect read and the click, or be redrawn under the
    pointer), so up to `tries` clicks, 10 s each, before it counts as a failure."""
    for i in range(tries):
        c.click_on(node(name))
        try:
            return c.wait(f"{DETAIL}?.dataset.key === '{key}' && '{name}'", 10)
        except TimeoutError:
            if i == tries - 1:
                raise


def live_map(c, rig) -> dict:
    from tests.helpers.studio_session_rig import STEER_SEEN, wait_for
    out = {}
    c.go(rig.url("agents"))
    c.wait(f"document.querySelectorAll('{NODE}').length === 3", 30)
    out["nodes"] = c.js(f"document.querySelectorAll('{NODE}').length")
    out["states"] = c.js(f"[...document.querySelectorAll('{NODE}')].map((n) => n.dataset.state)")
    key_a, key_b = rig.key("Implement"), rig.key("Research")
    wait_node(c, "researcher")
    out["selected"] = select_node(c, "researcher", key_b)
    out["tail_text"] = c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].map((e) => e.textContent).find((t) => t.includes('pricing notes'))", 15)
    c.click_on("document.querySelector('[data-testid=\"fleet-tab-working\"]')")
    out["tool_rows"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-tool-row\"]').length", 10)
    out["tool_label"] = c.js("document.querySelector('.fa-tool-label')?.textContent")
    c.click_on("document.querySelector('[data-testid=\"fleet-tab-thinking\"]')")
    x, y, w, h = c.rect("document.querySelector('.rlm-scroll')")
    c.click(x + w - 30, y + h - 30)  # the canvas's empty corner (it clears the pick; J / K hop from the agent watched)
    c.key("j")
    out["after_j"] = c.wait(f"{DETAIL}?.dataset.key !== '{key_b}' && {DETAIL}.dataset.key", 30)
    c.key("k")
    out["after_k"] = c.wait(f"{DETAIL}?.dataset.key === '{key_b}' && 'researcher'", 30)
    c.js("document.querySelector('[data-testid=\"fleet-steer-send\"]').scrollIntoView({block: 'center'}); 1")  # R6: Agent sits under Capabilities
    c.click_on("document.querySelector('[data-testid=\"fleet-steer\"]')")
    c.type_text(STEER_SEEN)
    c.click_on("document.querySelector('[data-testid=\"fleet-steer-send\"]')")
    out["echo"] = c.wait("document.querySelector('[data-testid=\"fleet-steer-echo\"]')?.textContent", 10)
    out["steer_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Steered') && 'steered'", 15)
    out["steer_cleared"] = c.js("document.querySelector('[data-testid=\"fleet-steer\"]').value === ''")
    rig.release("b")
    out["steer_reached_b"] = bool(wait_for(lambda: any(STEER_SEEN in json.dumps(b) for b in rig.seen["b3"]), 30))
    out["steer_not_a"] = not any(STEER_SEEN in json.dumps(b) for b in rig.seen["a"])
    wait_node(c, "implementer")
    c.click_on(node("implementer"))
    c.wait(f"{DETAIL}?.dataset.key === '{key_a}'", 30)
    c.click_on("document.querySelector('[data-testid=\"fleet-stop\"]')")
    out["asked"] = c.wait("document.querySelector('[data-testid=\"fleet-confirm\"] .dialog-title')?.textContent", 10)
    out["state_while_asked"] = rig.agent("Implement").get("state")
    c.click_on("document.querySelector('[data-testid=\"fleet-confirm-yes\"]')")
    c.wait("!document.querySelector('[data-testid=\"fleet-confirm\"]')", 10)
    # the dialog closes at once; the stop lands when its POST answers (the toast): only then does A's model call return
    out["stop_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('stopping') && 'stopping'", 15)
    rig.release("a")
    out["stopped"] = wait_for(lambda: rig.agent("Implement").get("state") == "stopped" and "stopped", 30)
    try:
        out["node_stopped"] = wait_node(c, "implementer", "n.dataset.state === 'stopped'", 60)  # a loaded runner took > 20 s
    except TimeoutError as e:
        # the Linux runner once kept the node `running` for 60 s after the tree said stopped (5afe0cd): record what
        # the tree, Studio's event bridge and the page hold at that moment, so the test's own check prints them
        out["node_stopped"] = False
        out["node_stopped_diag"] = {"error": str(e)[:200], "tree": {(a.get("task") or "")[:9]: a.get("state") for a in rig.agents()},
                                    "bridge_listeners": rig.server.events.listeners(),
                                    "nodes": c.js(f"[...document.querySelectorAll('{NODE}')].map((n) => n.dataset.key.slice(-8) + ':' + n.dataset.state)"),
                                    "detail": c.js(f"[{DETAIL}?.dataset.key, {DETAIL}?.dataset.state]"),
                                    "feed_open": c.js("typeof window.__haloFeedState === 'string' ? window.__haloFeedState : 'n/a'")}
    # Live's tree in its DOM order
    out["panels"] = c.js("['roles-live-map', 'fleet-agent-detail', 'live-inspector'].map((k) => document.querySelectorAll(`[data-testid=\"${k}\"]`).length)")
    out["rail"] = c.js(f"[...document.querySelectorAll('{NODE}')].map((n) => 'agent:' + n.dataset.agent)")
    view = rig.api("GET", "live")[1]  # 3.3.18.0: Live keeps a finished agent ten seconds: its order is the API's, its set the live ones and more
    out["api_tree"] = [x for x in expected_tree(view, live_only=False) if not x.startswith("agent:") or x in out["rail"]]
    out["api_live"] = expected_tree(view)
    return out


CANVAS = "document.querySelector('[data-testid=\"roles-canvas\"]')"


def card(name: str) -> str:
    """The React Roles canvas's card for agent bio `name` (3.0.7.0 R2: no framed page)."""
    return f"[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === '{name}')"


def card_click(c, expr: str) -> None:
    """Click a card once the canvas stopped moving (it fits itself after its first draw)."""
    import time
    last, end = None, time.time() + 5
    while time.time() < end:
        r = [round(v) for v in c.rect(expr)]
        if r == last:
            break
        last = r
        time.sleep(0.25)
    c.click_on(expr, 0.5, 0.25)


SELECTED = "document.querySelector('[data-testid=\"roles-card\"][data-selected]')?.dataset.agent"
LIVE_AGENT = "document.querySelector('[data-testid=\"roles-live-agent\"]')?.dataset.key"
LIVE_CARDS = "document.querySelectorAll('[data-testid=\"roles-card\"][data-live]')"


def roles(c, rig) -> dict:
    out = {}
    c.go(rig.url("roles"))
    out["live_cards"] = c.wait(f"{LIVE_CARDS}.length >= 3 && [...{LIVE_CARDS}].map((g) => g.dataset.agent + '=' + g.dataset.live)", 30)
    out["main_badge"] = c.js(f"{card('orchestrator')}?.querySelector('[data-testid=\"roles-live-badge\"]')?.textContent")
    card_click(c, card("implementer"))
    out["clicked"] = c.wait(SELECTED, 10)
    out["live_tab"] = c.wait("document.querySelector('[data-testid=\"roles-live-tab\"]')?.getAttribute('aria-selected') === 'true' && 'on'", 10)
    out["live_text"] = c.wait("[...document.querySelectorAll('[data-testid=\"roles-live\"] [data-testid=\"fleet-text\"]')].map((e) => e.textContent).find((t) => t.includes('basket'))", 15)
    work = "document.querySelector('[data-testid=\"roles-live\"] [data-testid=\"fleet-tab-working\"]')"  # 3.3.16.0 R2: the one agent inspector
    c.js(f"{work}.scrollIntoView({{block: 'center'}}); 1")  # 3.1.4.0 R4: below the MODEL strip
    c.click_on(work)
    out["live_tools"] = c.wait("document.querySelectorAll('[data-testid=\"roles-live\"] [data-testid=\"fleet-tool-row\"]').length", 10)
    out["live_tool"] = c.js("document.querySelector('[data-testid=\"roles-live\"] .fa-tool-label')?.textContent")
    out["watched"] = c.js(LIVE_AGENT)
    c.key("j")
    out["hop"] = c.wait(f"{LIVE_AGENT} !== '{out['watched']}' && {LIVE_AGENT}", 10)
    out["hop_card"] = c.js(SELECTED)
    out["hop_tools"] = c.wait("[...document.querySelectorAll('[data-testid=\"roles-live\"] .fa-tool-label')].map((e) => e.textContent).find((t) => t.startsWith('Bash: git grep'))", 15)
    c.key(" ")
    out["pinned"] = c.wait("document.querySelector('[data-testid=\"fleet-pip\"] .pip-name')?.textContent", 10)
    c.key("Escape")
    out["unpinned"] = c.wait("!document.querySelector('[data-testid=\"fleet-pip\"]')", 10)
    return out


class LiveDriver(Driver):
    """`map`, `roles`, `panels` over tests/helpers/studio_session_rig.py (it scopes its own home)."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session_rig import StudioSessionRig
        which = self.argv[:1]
        with StudioSessionRig() as rig:
            if which == ["panels"]:
                from tests.helpers.studio_live_panels import panels as step
            else:
                step = live_map if which == ["map"] else roles
            yield ((step, (c, rig)),)


def main(argv: list) -> int:
    return LiveDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
