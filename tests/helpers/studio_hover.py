"""tests.helpers.studio_hover -- the hover cards (Halo 3.3.16.1, the owner: "hovering over gives a solid summary, if we
click one we get that other panel with all the detail") in headless Chrome on the driver base, over
tests/helpers/studio_fleet_rig.py (halo-dev-cycle active, this harness's real session, the member kali@lab) plus three
extra agents (tests/helpers/studio_live_rig.py) and the `media` square enabled. tests/test_studio_hover.py runs it:

    python -m tests.helpers.studio_hover hover   no card after Cast, Live and Workflows load; resting the real pointer on
                                                 a Cast card, a Live agent (its NOW follows a seeded tool frame), a
                                                 session and a machine (fleet), a square on the board and a library row
                                                 shows one card of that kind; leaving removes it; a press removes it and
                                                 the inspector opens as before; Tab to a node shows its card; the
                                                 right-most and bottom-most nodes of a narrow window keep their card
                                                 inside it and off their box; `studio.hover_cards` off: no card, the
                                                 titles back, a square's hover shows the inspector again

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_hover_read import CARD, away, gone, hover_card, none_for, rest, tab  # noqa: E402

Q = "document.querySelector"
MAP = f"{Q}('[data-testid=\"roles-live-map\"]')"


def node(aid: str) -> str:
    return f"{Q}('[data-testid=\"roles-live-node\"][data-agent=\"{aid}\"]')"


def go(c, rig, extra: str, ready: str) -> None:
    c.go("about:blank")
    c.go(rig.url("agents", extra))
    c.wait(ready, 40)


def quiet(c, rig) -> dict:
    out = {}
    for name, extra, ready in (("cast", "&view=cast", f"!!{Q}('[data-testid=\"roles-card\"]')"),
                               ("live", "&view=live&scope=here", f"{MAP} && +{MAP}.dataset.nodes >= 6"),
                               ("workflows", "&view=workflows", f"!!{Q}('[data-testid=\"wf-card\"]')")):
        go(c, rig, extra, ready)
        out[f"quiet_{name}"] = none_for(c, 1.0)
    return out


def cast(c, rig) -> dict:
    box = "[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((e) => e.dataset.role !== 'main')"
    go(c, rig, "&view=cast", f"!!({box})")
    out = {"cast_title_attr": c.js(f"{box}.getAttribute('title')"),
           "cast": hover_card(c, box, "cast", "", 0.5, 0.12)}
    away(c)
    out["cast_left"] = gone(c)
    return out


def agent(c, rig) -> dict:
    lv = rig.hover_live
    go(c, rig, "&view=live&scope=here", f"{MAP} && +{MAP}.dataset.nodes >= 6 && !!{node(lv.aid('tester'))}")
    tester = node(lv.aid("tester"))
    out = {"agent": hover_card(c, tester, "agent", lv.key("tester"), 0.3, 0.55)}
    lv.tool("tester", "Bash", "hv-1", current="pytest -q tests/test_basket.py")
    out["agent_now"] = c.wait(f"(() => {{ const n = {Q}('[data-testid=\"hover-card-now\"]'); return n && n.textContent.includes('Bash') && n.textContent; }})()", 15)
    x, y, w, h = c.rect(tester)
    c.mouse("mousePressed", x + w * 0.3, y + h * 0.55)  # a press: the card goes, the inspector opens as before
    c.mouse("mouseReleased", x + w * 0.3, y + h * 0.55)
    out["press_gone"] = gone(c)
    out["press_inspector"] = c.wait(f"{Q}('[data-testid=\"live-inspector\"]')?.dataset.pick === 'agent' && "
                                    f"{Q}('[data-testid=\"roles-live-agent\"]')?.dataset.key", 15)
    out["press_stays_gone"] = none_for(c, 1.0)
    away(c)
    c.js(f"{Q}('.rlm-scroll').focus(); 1")
    tab(c)
    out["tab"] = c.wait(f"(() => {{ const c = {CARD}; return c && c.dataset.by === 'focus' && c.style.visibility !== 'hidden' ? "
                        f"[c.dataset.kind, c.dataset.for, document.activeElement?.dataset.testid] : null; }})()", 10)
    c.key("Escape")
    out["esc_gone"] = gone(c)
    return out


def fleet(c, rig) -> dict:
    go(c, rig, "&view=live&scope=fleet", f"!!{Q}('[data-testid=\"live-machine\"]') && !!{Q}('[data-testid=\"fleet-session\"]')")
    sid = rig.act.session_id
    sess = f"{Q}('[data-testid=\"fleet-session\"][data-sid=\"{sid}\"]')"
    out = {"session": hover_card(c, sess, "session", "", 0.25, 0.5)}
    away(c)
    gone(c)
    mach = f"{Q}('[data-testid=\"live-machine\"][data-local]')"
    out["machine"] = hover_card(c, mach, "machine", "", 0.25, 0.3)
    out["machine_title_attr"] = c.js(f"{mach}.getAttribute('title')")
    away(c)
    gone(c)
    return out


EDGE = """(() => {{ const v = [...document.querySelectorAll('[data-testid="roles-live-node"], [data-testid="fleet-session"], [data-testid="live-machine"]')]
  .filter((e) => {{ const r = e.getBoundingClientRect(); return r.width > 0 && r.right <= innerWidth && r.bottom <= innerHeight && r.left >= 0 && r.top >= 0; }});
  v.sort((a, b) => b.getBoundingClientRect().{k} - a.getBoundingClientRect().{k}); v[0]?.setAttribute('data-hv-edge', '{k}'); return v.length; }})()"""


def edges(c, rig) -> dict:
    """A narrow window: the right-most and the bottom-most node keep their card inside it, off their box."""
    c.call("Emulation.setDeviceMetricsOverride", width=980, height=620, deviceScaleFactor=1, mobile=False)
    out = {}
    try:
        go(c, rig, "&view=live&scope=fleet", f"!!{Q}('[data-testid=\"live-machine\"]')")
        time.sleep(0.6)
        for k in ("right", "bottom"):
            c.js(EDGE.format(k=k))
            box = f"{Q}('[data-hv-edge=\"{k}\"]')"
            kind = c.js(f"({{'roles-live-node': 'agent', 'fleet-session': 'session', 'live-machine': 'machine'}})[{box}.dataset.testid]")
            out[f"edge_{k}"] = hover_card(c, box, kind, "", 0.25, 0.3)
            away(c, 2, 2)
            gone(c)
    finally:
        c.call("Emulation.clearDeviceMetricsOverride")
    return out


def squares(c, rig) -> dict:
    go(c, rig, "&view=workflows", f"!!{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')")
    card = f"{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')"
    out = {"square": hover_card(c, card, "square", "media", 0.3, 0.6)}
    out["square_no_inspector"] = c.js(f"!{Q}('[data-testid=\"wf-inspector\"]')")
    c.click_on(card, 0.3, 0.6)
    out["square_click"] = c.wait(f"!{CARD} && {Q}('[data-testid=\"wf-inspector\"]')?.dataset.ref", 10)
    c.key("Escape")
    away(c)
    c.click_on(f"{Q}('[data-testid=\"wf-library-plus\"]')")
    row = f"{Q}('[data-testid=\"wf-row\"][data-ref=\"media\"]')"
    out["row"] = hover_card(c, row, "square", "library:media", 0.3, 0.5)
    away(c)
    gone(c)
    return out


def off(c, rig) -> dict:
    from halo_harness.theme import set_config_value
    set_config_value("studio.hover_cards", False)
    lv = rig.hover_live
    go(c, rig, "&view=live&scope=here", f"{MAP} && +{MAP}.dataset.nodes >= 6 && !!{node(lv.aid('tester'))}")
    tester = node(lv.aid("tester"))
    out = {"off_titles": c.wait(f"{tester}.querySelector('.rlm-title')?.getAttribute('title')", 15)}
    rest(c, tester, 0.3, 0.55)
    out["off_none"] = none_for(c, 1.5)
    go(c, rig, "&view=workflows", f"!!{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')")
    # the page reads the setting after it loads ("wait" until then: no card, no hover inspector); a pointer that came
    # to rest before that sees nothing until it moves, so the driver comes back onto the square until the page answers
    # (red on the Linux runner at 69988ed6, green here and in WSL)
    card, seen = f"{Q}('[data-testid=\"wf-card\"][data-ref=\"media\"]')", None
    for _ in range(8):
        rest(c, card, 0.3, 0.6)
        try:
            seen = c.wait(f"{Q}('[data-testid=\"wf-inspector\"]')?.dataset.hover && 'hover'", 2)
            break
        except TimeoutError:
            away(c)
    out["off_square_inspector"] = seen
    out["off_square_none"] = none_for(c, 0.6)
    set_config_value("studio.hover_cards", True)
    return out


class HoverDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.chrome_driver import emulate_motion
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        from tests.helpers.studio_live_rig import Live
        from halo_harness.theme import set_config_value
        emulate_motion(c, "reduce")  # no fade: the card is read where it lands
        with StudioFleetRig() as rig:
            rig.full = False  # the page as the owner sees it (nothing opened by the driver)
            set_config_value("workflows.enabled", ["media"])
            st, body = rig.api("POST", "workflows/enable", {"ref": "media"})  # halo-dev-cycle lists its own squares
            self.out["enable"] = [st, body.get("line") or body.get("error")]
            rig.hover_live = Live(rig)
            args = (c, rig)
            yield ((quiet, args), (cast, args), (agent, args), (fleet, args), (edges, args), (squares, args), (off, args))


if __name__ == "__main__":
    sys.exit(HoverDriver(sys.argv[1:]).main())
