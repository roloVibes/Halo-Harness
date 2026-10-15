"""tests.helpers.studio_fleet -- the Studio Fleet checks (Halo 3.0.5.0 round
R3) driven through real clicks and keys in headless Chrome over the DevTools
protocol (tests/helpers/cdp.py), over tests/helpers/studio_fleet_rig.py (this
harness's real session with three agents mid-work, a member harness with
two). tests/test_studio_ui.py runs it as a subprocess with a scrubbed
environment:

    python -m tests.helpers.studio_fleet map     # boxes, nodes, the rail, select + tail, J/K, steer, stop
    python -m tests.helpers.studio_fleet roles   # Live Roles: the glow, the Live tab's text and tool rows, J, the pin
    python -m tests.helpers.studio_fleet panels  # R4: attention, timeline, digest, replay, conflict (studio_fleet_panels.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

FRAME = "document.querySelector('.section-view[data-section=\"roles\"] iframe.legacy-frame')"
DOC = f"{FRAME}.contentDocument"
DETAIL = "document.querySelector('[data-testid=\"fleet-agent-detail\"]')"


def node(name: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"fleet-node\"]')].find((n) => n.querySelector('.fm-name').textContent.startsWith('{name}'))"


def expected_tree(view: dict) -> list:
    """The rail's order: harness, then each session and its agents depth first (as GET fleet has them)."""
    out = []
    for h in view.get("harnesses", []):
        out.append(f"harness:{h['id']}")
        for s in h.get("sessions") or []:
            out.append(f"session:{s['session_id']}")
            rows = s.get("agents") or []
            ids = {a["agent_id"] for a in rows}

            def walk(parent, depth):
                for a in rows:
                    if (a.get("parent") if a.get("parent") in ids else None) == parent:
                        out.append(f"agent:{a['agent_id']}")
                        if depth < 8:
                            walk(a["agent_id"], depth + 1)
            walk(None, 0)
    return out


def fleet_map(c, rig) -> dict:
    from tests.helpers.studio_fleet_rig import STEER_SEEN, wait_for
    out = {}
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-box\"]').length === 2 && document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5", 30)
    out["boxes"] = c.js("document.querySelectorAll('[data-testid=\"fleet-box\"]').length")
    out["nodes"] = c.js("document.querySelectorAll('[data-testid=\"fleet-node\"]').length")
    out["labels"] = c.js("[...document.querySelectorAll('.fm-box-label')].map((t) => t.textContent)")
    out["states"] = c.js("[...document.querySelectorAll('[data-testid=\"fleet-node\"]')].map((n) => n.dataset.state)")
    out["panels"] = c.js("['fleet-map', 'fleet-agent', 'fleet-rail'].map((k) => document.querySelectorAll(`[data-testid=\"${k}\"]`).length)")
    out["rail"] = c.js("[...document.querySelectorAll('[data-testid=\"fleet-rail-node\"]')].map((n) => n.dataset.kind + ':' + n.dataset.id)")
    out["api_tree"] = expected_tree(rig.api("GET", "fleet")[1])
    key_a, key_b = rig.key("Implement"), rig.key("Research")
    c.click_on(node("researcher"))
    out["selected"] = c.wait(f"{DETAIL}?.dataset.key === '{key_b}' && 'researcher'", 10)
    out["tail_text"] = c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].map((e) => e.textContent).find((t) => t.includes('pricing notes'))", 15)
    c.click_on("document.querySelector('[data-testid=\"fleet-tab-working\"]')")
    out["tool_rows"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-tool-row\"]').length", 10)
    out["tool_label"] = c.js("document.querySelector('.fa-tool-label')?.textContent")
    c.click_on("document.querySelector('[data-testid=\"fleet-tab-thinking\"]')")
    x, y, w, h = c.rect("document.querySelector('.fm-scroll')")
    c.click(x + w - 30, y + h - 30)  # the map's empty corner: the panel takes the keys
    c.key("j")
    out["after_j"] = c.wait(f"{DETAIL}?.dataset.key !== '{key_b}' && {DETAIL}.dataset.key", 10)
    c.key("k")
    out["after_k"] = c.wait(f"{DETAIL}?.dataset.key === '{key_b}' && 'researcher'", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-steer\"]')")
    c.type_text(STEER_SEEN)
    c.click_on("document.querySelector('[data-testid=\"fleet-steer-send\"]')")
    out["echo"] = c.wait("document.querySelector('[data-testid=\"fleet-steer-echo\"]')?.textContent", 10)
    out["steer_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Steered') && 'steered'", 15)
    out["steer_cleared"] = c.js("document.querySelector('[data-testid=\"fleet-steer\"]').value === ''")
    rig.release("b")
    out["steer_reached_b"] = bool(wait_for(lambda: any(STEER_SEEN in json.dumps(b) for b in rig.seen["b3"]), 30))
    out["steer_not_a"] = not any(STEER_SEEN in json.dumps(b) for b in rig.seen["a"])
    c.click_on(node("implementer"))
    c.wait(f"{DETAIL}?.dataset.key === '{key_a}'", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-stop\"]')")
    out["asked"] = c.wait("document.querySelector('[data-testid=\"fleet-confirm\"] .dialog-title')?.textContent", 10)
    out["state_while_asked"] = rig.agent("Implement").get("state")
    c.click_on("document.querySelector('[data-testid=\"fleet-confirm-yes\"]')")
    c.wait("!document.querySelector('[data-testid=\"fleet-confirm\"]')", 10)
    # the dialog closes at once; the stop lands when its POST answers (the toast): only then does A's model call return
    out["stop_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('stopping') && 'stopping'", 15)
    rig.release("a")
    out["stopped"] = wait_for(lambda: rig.agent("Implement").get("state") == "stopped" and "stopped", 30)
    out["node_stopped"] = c.wait(f"{node('implementer')}?.dataset.state === 'stopped' && 'stopped'", 20)
    c.click_on(f"[...document.querySelectorAll('[data-testid=\"fleet-rail-node\"]')].find((n) => n.dataset.kind === 'agent' && n.dataset.id === 'main' && n.closest('.fr-harness').querySelector('.fr-h').dataset.id === '{rig.member_id}')")
    c.wait(f"{DETAIL}?.dataset.key?.startsWith('{rig.member_id}')", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-steer\"]')")
    c.type_text("answer the second question first")
    c.click_on("document.querySelector('[data-testid=\"fleet-steer-send\"]')")
    got = wait_for(lambda: [d for d in rig.member_cmds if d.get("cmd") == "agent_steer"], 15)
    out["member_steer"] = (got or [{}])[-1].get("fields", {}).get("text")
    out["member_tail"] = c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].map((e) => e.textContent).find((t) => t.includes('Two questions'))", 10)
    rig.member_spawn()  # D13: a new child on the member's tree, live from the feed: its node, and the edge lit for a few seconds
    out["spawned"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 6 && document.querySelectorAll('[data-testid=\"fleet-lit-edge\"]').length", 10)
    out["spawn_tool"] = c.js(f"{node('verifier')}?.querySelector('.fm-tool')?.dataset.tool")
    return out


def frame_click(c, expr: str) -> None:
    """Click an element of the framed page once it stops moving (the canvas lays its groups out and fits after it loads)."""
    import time
    fx, fy, _w, _h = c.rect(FRAME)
    last, end = None, time.time() + 5
    while time.time() < end:
        r = [round(v) for v in c.rect(expr)]
        if r == last:
            break
        last = r
        time.sleep(0.25)
    x, y, w, h = c.rect(expr)
    c.click(fx + x + w / 2, fy + y + min(h / 2, 30))


def card(name: str) -> str:
    return f"[...{DOC}.querySelectorAll('.node')].find((n) => n.querySelector('.agent')?.textContent === '{name}')"


def roles(c, rig) -> dict:
    out = {}
    c.go(rig.url("roles"))
    out["live_cards"] = c.wait(f"{DOC}?.querySelectorAll('[data-testid=\"live-card\"]').length >= 3 && [...{DOC}.querySelectorAll('[data-testid=\"live-card\"]')].map((g) => g.querySelector('.agent').textContent + '=' + g.dataset.live)", 30)
    out["main_badge"] = c.js(f"{card('orchestrator')}?.querySelector('.live-badge')?.textContent")
    frame_click(c, f"{card('implementer')}.querySelector('.card')")
    out["clicked"] = c.wait(f"{FRAME}.contentWindow.app.canvas.node({FRAME}.contentWindow.haloLive.card)?.agent", 10)
    out["live_tab"] = c.wait(f"{DOC}.querySelector('[data-testid=\"live-tab\"]')?.classList.contains('on') && 'on'", 10)
    out["live_text"] = c.wait(f"[...{DOC}.querySelectorAll('[data-testid=\"live-text\"]')].map((e) => e.textContent).find((t) => t.includes('basket'))", 15)
    frame_click(c, f"{DOC}.querySelector('[data-sub=\"working\"]')")
    out["live_tools"] = c.wait(f"{DOC}.querySelectorAll('[data-testid=\"live-tool-row\"]').length", 10)
    out["live_tool"] = c.js(f"{DOC}.querySelector('.live-tool-label')?.textContent")
    out["watched"] = c.js(f"{FRAME}.contentWindow.haloLive.watched")
    c.key("j")
    out["hop"] = c.wait(f"{FRAME}.contentWindow.haloLive.watched !== '{out['watched']}' && {FRAME}.contentWindow.haloLive.watched", 10)
    out["hop_card"] = c.js(f"{FRAME}.contentWindow.app.canvas.node({FRAME}.contentWindow.haloLive.card)?.agent")
    out["hop_tools"] = c.wait(f"[...{DOC}.querySelectorAll('.live-tool-label')].map((e) => e.textContent).find((t) => t.startsWith('Bash: git grep'))", 15)
    c.key(" ")
    out["pinned"] = c.wait("document.querySelector('[data-testid=\"fleet-pip\"] .pip-name')?.textContent", 10)
    c.key("Escape")
    out["unpinned"] = c.wait("!document.querySelector('[data-testid=\"fleet-pip\"]')", 10)
    return out


def main(argv: list) -> int:
    from capture_studio import find_chrome
    from tests.helpers.cdp import Chrome
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    exe = find_chrome()
    if not exe:
        print(json.dumps({"skip": "no Chrome found"}))
        return 2
    with StudioFleetRig() as rig:
        c = Chrome(exe)
        try:
            if argv[:1] == ["panels"]:
                from tests.helpers.studio_fleet_panels import panels
                got = panels(c, rig)
            else:
                got = fleet_map(c, rig) if argv[:1] == ["map"] else roles(c, rig)
            print(json.dumps(got))
            return 0
        finally:
            c.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
