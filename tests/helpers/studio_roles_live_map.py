"""tests.helpers.studio_roles_live_map -- Roles Live (Halo 3.3.11.0 R2, the owner: "the roles tab kept up with what's
happening during sessions") in headless Chrome on the driver base, over tests/helpers/studio_fleet_rig.py (the
halo-dev-cycle lineup open, its real session: main, an implementer and a researcher) plus three agents an Auto-mode
main spawned (tests/helpers/studio_live_rig.py `Live`: the rows GET fleet lists and their `agent_state` frames) whose
lineup is `auto` and whose roles no card of the open lineup has -- so the Plan canvas glows none of them.
tests/test_studio_roles_live_map.py runs it:

    python -m tests.helpers.studio_roles_live_map livemap   Alt+3 then L opens Live; all three spawned agents are
                                                            nodes with an edge from main and their pick's reason;
                                                            the main card's faint group is behind main and none of
                                                            the three sits in a group; zoom in / Fit; a click puts
                                                            the agent in the Inspector's Live tab; L goes back to
                                                            Plan; `?view=live` opens on it; the Session Map
                                                            thumbnail's "Open in Roles Live" lands on Roles Live

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

MAP = "document.querySelector('[data-testid=\"roles-live-map\"]')"
WORLD = "document.querySelector('[data-testid=\"roles-live-world\"]')"
SPAWNED = (
    ("w1r4n6l0", "wrangler", "data-wrangler", "or:mock/cheap-coder", "Clean the basket fixtures",
     "the bio asks for tools, the best tools model within 3x the cheapest ($0.05/$0.20 per 1M)"),
    ("t2r1a6e0", "triage", "triager", "or:mock/cheap-fast", "Sort the failing cases",
     "a short task, the cheapest model that takes tools ($0.02/$0.08 per 1M)"),
    ("s3c2r1b0", "scribe", "scribe", "or:mock/glm-5-coder", "Write up the basket change",
     "a writing task, the cheapest model with a long window ($0.10/$0.40 per 1M)"),
)


def node(aid: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-live-node\"][data-agent=\"{aid}\"]')"


def l_key(c) -> None:
    """L: Plan | Live (the Roles canvas)."""
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key="l", code="KeyL", windowsVirtualKeyCode=76, modifiers=0,
               **({"text": "l"} if kind == "keyDown" else {}))


def spawned(lv) -> None:
    for aid, name, role, model, task, why in SPAWNED:
        lv.spawn(aid, name, role, model, task)
        lv.state(name, lineup="auto", bio=role, model_reason=why, kind="member")


def open_live(c, rig) -> dict:
    """Roles by Alt+3, then L: the Live canvas on this harness's session, every agent on it."""
    from tests.helpers.studio_live_rig import Live
    from tests.helpers.studio_session import alt
    lv = rig.live_map = Live(rig, extra=())
    spawned(lv)
    c.go(rig.url("session"))
    c.wait("document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"roles-live-node\"]').length >= 6 && 'session'", 40)
    alt(c, 2)  # 3.3.16.0 R1: Agents, on Cast
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0 && 'plan'", 40)
    out = {"plan_glows": c.wait("[...document.querySelectorAll('[data-testid=\"roles-card\"][data-live]')].map((n) => n.dataset.agent).sort().join(',') || null", 15)}
    l_key(c)
    c.wait(f"!!{MAP}", 30)  # 3.3.16.0 R2: with a member paired Live opens on the fleet; this halo is one click
    c.click_on("document.querySelector('[data-testid=\"live-scope-here\"]')")
    out["sid"] = c.wait(f"{MAP} && +{MAP}.dataset.nodes >= 6 && {MAP}.dataset.session", 30)
    out["rig_sid"] = rig.act.session_id
    return out


def the_tree(c, rig) -> dict:
    out: dict = {}
    out["nodes"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-live-node\"]')].map((n) => n.dataset.agent)")
    out["edges"] = {aid: c.js(f"[...document.querySelectorAll('[data-testid=\"roles-live-edge\"][data-to=\"{aid}\"]')].map((e) => e.dataset.from)")
                    for aid, *_ in SPAWNED}
    # 3.3.16.1: the line's whole text (its title went with the hover card; CSS cuts what does not fit)
    out["picks"] = {aid: c.js(f"{node(aid)}?.querySelector('[data-testid=\"roles-live-pick\"]')?.textContent || ''") for aid, *_ in SPAWNED}
    out["spawned_cards"] = [c.js(f"{node(aid)}?.dataset.card || ''") for aid, *_ in SPAWNED]
    main_card = c.js(f"{node('main')}?.dataset.card || ''")
    out["main_card"] = main_card
    g = f"document.querySelector('[data-testid=\"roles-live-group\"][data-card=\"{main_card}\"]')"
    out["main_group"] = c.js(f"(() => {{ const g = {g}, n = {node('main')}; if (!g || !n) return null; const a = g.getBoundingClientRect(), b = n.getBoundingClientRect();"
                             " return {behind: a.left <= b.left && a.top <= b.top && a.right >= b.right && a.bottom >= b.bottom,"
                             " first: g.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING ? true : false,"
                             " faint: getComputedStyle(g).borderStyle, label: g.textContent}; })()")
    return out


FITS = ("(() => { const s = document.querySelector('.rlm-scroll'), w = document.querySelector('.rlm .rc-world');"
        " return !!s && !!w && w.offsetWidth <= s.clientWidth + 1 && w.offsetHeight <= s.clientHeight + 1; })()")


def zoom_fit(c, rig) -> dict:
    """The first draw fits a tree wider than the page; + zooms in past it; Fit brings it back."""
    out = {"first_fit": c.wait(f"{FITS} && +{WORLD}.dataset.zoom < 1 && +{WORLD}.dataset.zoom", 10)}
    z0 = out["first_fit"]
    c.click_on("document.querySelector('[data-testid=\"roles-live-zoom-in\"]')")
    z1 = c.wait(f"+{WORLD}.dataset.zoom > {z0} && +{WORLD}.dataset.zoom", 5)
    c.click_on("document.querySelector('[data-testid=\"roles-live-fit\"]')")
    z2 = c.wait(f"+{WORLD}.dataset.zoom < {z1} && +{WORLD}.dataset.zoom", 5)
    out.update(zoom=[z0, z1, z2], fits=c.js(FITS))
    return out


def click_node(c, rig) -> dict:
    from tests.helpers.studio_fleet import card_click
    aid, name = SPAWNED[1][0], SPAWNED[1][1]
    card_click(c, node(aid))
    agent = "document.querySelector('[data-testid=\"roles-live\"][data-view=\"live\"] [data-testid=\"roles-live-agent\"]')"
    got = c.wait(f"{agent} && [{agent}.dataset.key, {agent}.querySelector('.fa-name')?.textContent, "
                 f"{agent}.querySelector('[data-testid=\"roles-live-reason\"]')?.textContent || '']", 15)
    return {"inspector": got, "selected": c.js(f"{node(aid)}?.dataset.selected || ''"), "want_name": name}


def back_to_plan(c, rig) -> dict:
    c.js("document.activeElement?.blur()")
    l_key(c)
    plan = c.wait("!document.querySelector('[data-testid=\"roles-live-map\"]') && document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0 && 'plan'", 10)
    c.go(rig.url("roles", "&view=live"))
    by_url = c.wait(f"{MAP} && +{MAP}.dataset.nodes >= 6 && 'live'", 30)
    return {"l_back": plan, "by_url": by_url}


def thumb(c, rig) -> dict:
    """Session's Map is the thumbnail; its "Open in Roles Live" opens the same tree on Roles."""
    c.go(rig.url("session"))
    btn = "document.querySelector('[data-testid=\"session-map-expand\"]')"
    c.wait(f"!!{btn} && !{btn}.disabled && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"roles-live-node\"]').length >= 6", 40)
    out = {"thumb_nodes": c.js("document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"roles-live-node\"]').length")}
    c.click_on(btn)
    out["expanded"] = c.wait(f"{MAP} && +{MAP}.dataset.nodes >= 6 && [{MAP}.dataset.session, +{MAP}.dataset.nodes, "
                             "document.querySelector('[data-testid=\"roles-view-live\"]')?.getAttribute('aria-pressed')]", 30)
    out["live_nodes"] = c.js(f"+{MAP}.dataset.nodes")
    return out


class LiveMapDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            args = (c, rig)
            yield ((open_live, args), (the_tree, args), (zoom_fit, args), (click_node, args), (back_to_plan, args), (thumb, args))


if __name__ == "__main__":
    sys.exit(LiveMapDriver(sys.argv[1:]).main())
