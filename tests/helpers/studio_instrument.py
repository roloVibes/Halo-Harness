"""tests.helpers.studio_instrument -- the Instrument look (Halo 3.3.15.0 L1, docs/design/studio-instrument/) in headless
Chrome on the driver base; no provider request, no model call. tests/test_studio_instrument.py runs it:

    python -m tests.helpers.studio_instrument fresh      capture_studio's seeded home on a dark system: the page's theme
                                                         (`instrument`, its colours), the rail (52 px, 176 px on its
                                                         chevron, kept across a reload), a panel's and the palette's
                                                         corner ticks, and nothing animating on any section's load (an
                                                         `animationstart` listener installed before each page's scripts)
    python -m tests.helpers.studio_instrument rig        the Studio fleet rig plus three agents an Auto main spawned on
                                                         `or:mock/...` models: the Session Map's nodes and Roles Live's
                                                         show the model without its prefix, the Inspector's Live tab the
                                                         full id; Roles' Apply asks with DOES / COSTS / WRITES; with
                                                         prefers-reduced-motion no animation runs after a state change
                                                         (and without it the working agents' do)
    python -m tests.helpers.studio_instrument shots DIR  the hand-back's captures (tests/helpers/studio_instrument_shots.py) into DIR
                                                         (each core section at 1440 x 900 and 1280 x 800, Roles Live, the +
                                                         menu, Focus, Session at 390)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, alt, q, qa  # noqa: E402

APP = q(".app")
VAR = "getComputedStyle(document.documentElement).getPropertyValue('{}').trim()"
RAIL_W = f"Math.round({q('.rail')}.getBoundingClientRect().width)"
CORE = [("session", "Session"), ("agents", "Agents"), ("fleet", "Fleet"), ("packs", "Packs"), ("setup", "Setup"),
        ("settings", "Settings"), ("local", "Local")]  # 3.3.16.0 R1: Agents took in Team, Roles and Orchestra
# every animation that starts with a duration, from before the page's own scripts (a zero-length swap is not motion)
LISTEN = ("window.__anims = []; document.addEventListener('animationstart', (e) => { const d = getComputedStyle(e.target).animationDuration;"
          " if (d.split(',').some((x) => parseFloat(x) > 0)) window.__anims.push(e.animationName); }, true);")
class _Ticks:
    """`TICKS.format(expr)`: [the number of linear-gradient layers, the background-size] of that element."""
    @staticmethod
    def format(expr: str) -> str:
        return ("(() => { const s = getComputedStyle(" + expr + ");"
                " return [(s.backgroundImage.match(/linear-gradient/g) || []).length, s.backgroundSize]; })()")


TICKS = _Ticks()
RUNNING = "document.getAnimations().filter((a) => a.playState === 'running').map((a) => a.animationName || a.constructor.name)"
SPAWNED = (("w1r4n6l0", "wrangler", "data-wrangler", "or:mock/cheap-coder", "Clean the basket fixtures"),
           ("t2r1a6e0", "triage", "triager", "or:mock/cheap-fast", "Sort the failing cases"),
           ("s3c2r1b0", "scribe", "scribe", "or:mock/glm-5-coder", "Write up the basket change"))


def media(c, dark: bool = True, reduce: bool = False) -> None:
    c.call("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"},
                                                             {"name": "prefers-reduced-motion", "value": "reduce" if reduce else "no-preference"}])


def load(c, ctx, query: str, title: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(f"{ctx['base']}?{query}&feed=off&tour=off#{ctx['frag']}")
    c.wait(f"{CUR}.startsWith('{title}') && !!{q('[data-testid=rail-toggle]')}", 40)


def theme(c, url, ctx) -> dict:
    media(c)
    load(c, ctx, "mode=roles", "Agents")
    return {"theme": c.js("document.documentElement.dataset.theme"), "bg": c.js(VAR.format("--bg")), "surface": c.js(VAR.format("--surface")),
            "accent": c.js(VAR.format("--accent")), "body_bg": c.js("getComputedStyle(document.body).backgroundColor")}


def rail(c, url, ctx) -> dict:
    load(c, ctx, "mode=roles", "Agents")
    out = {"rail_w": c.js(RAIL_W)}
    c.click_on(q("[data-testid=rail-toggle]"))
    c.wait(f"{APP}.dataset.rail === 'open'", 5)
    time.sleep(0.3)
    out["rail_open_w"] = c.js(RAIL_W)
    load(c, ctx, "mode=roles", "Agents")
    out["rail_reload"] = [c.js(f"{APP}.dataset.rail"), c.js(RAIL_W), c.js("localStorage.getItem('halo.studio.rail')")]
    c.click_on(q("[data-testid=rail-toggle]"))
    out["rail_back"] = c.wait(f"{APP}.dataset.rail === 'icons' && {RAIL_W}", 5)
    return out


def ticks(c, url, ctx) -> dict:
    load(c, ctx, "mode=roles", "Agents")
    c.wait(f"!!{q('.panel.glass')}", 30)
    out = {"panel_ticks": c.js(TICKS.format(q(".panel.glass"))),
           "selected_ticks": c.js(f"getComputedStyle({q('.panel.focused > .hud-brackets')}).backgroundImage.split('linear-gradient').length - 1")}
    c.click_on(q(".palette-btn"))
    c.wait(f"!!{q('.palette-surface')}", 10)
    out["palette_ticks"] = c.js(TICKS.format(q(".palette-surface")))
    out["palette_shadow"] = c.js(f"getComputedStyle({q('.palette-surface')}).boxShadow")
    c.key("Escape")
    return out


def quiet_load(c, url, ctx) -> dict:
    """Each core section loaded on its own page, the listener in before the page's scripts: no animation starts."""
    c.call("Page.enable")
    c.call("Page.addScriptToEvaluateOnNewDocument", source=LISTEN)
    out: dict = {}
    for sid, title in CORE:
        load(c, ctx, f"mode={sid}", title)
        time.sleep(1.5)
        out[sid] = c.js("window.__anims || null")
    by_key: dict = {}
    for n, (sid, title) in enumerate(CORE, 1):
        c.js("document.activeElement?.blur?.(); window.__anims = []; 1")
        alt(c, n)
        c.wait(f"{CUR}.startsWith('{title}')", 15)
        time.sleep(1.2)
        by_key[sid] = c.js("window.__anims")
    c.js("window.__anims = []; const d = document.createElement('i'); d.style.animation = 'm-blink 1s 1'; document.body.appendChild(d); 1")
    time.sleep(0.3)  # the control: the listener does see an animation that starts
    return {"load_anims": out, "key_anims": by_key, "listener_control": c.js("window.__anims")}


def rig_load(c, rig, sid: str, title: str, extra: str = "") -> None:
    """A section of the rig on a page of its own, the live feed on (the map draws from it)."""
    c.go("about:blank")
    c.go(rig.url(sid, extra))
    c.wait(f"{CUR}.startsWith('{title}') && !!{q('[data-testid=rail-toggle]')}", 40)


def labels(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    from tests.helpers.studio_roles_live_map import l_key
    lv = rig.live_map = Live(rig, extra=())
    for aid, name, role, model, task in SPAWNED:
        lv.spawn(aid, name, role, model, task)
        lv.state(name, lineup="auto", bio=role, kind="member")
    media(c)
    c.go(rig.url("session"))
    node = "document.querySelector('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"][data-key$=\"|{}\"]')"
    c.wait(f"document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6 && !!{node.format(SPAWNED[0][0])}", 40)
    out = {"map_labels": [c.js(f"{node.format(a)}?.querySelector('[data-testid=fleet-node-model] text')?.textContent || ''") for a, *_ in SPAWNED],
           "map_titles": [c.js(f"{node.format(a)}?.querySelector('title')?.textContent || ''") for a, *_ in SPAWNED]}
    alt(c, 2)  # 3.3.16.0 R1: Agents, on Cast
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0", 40)
    l_key(c)
    live = "document.querySelector('[data-testid=\"roles-live-node\"][data-agent=\"{}\"] [data-testid=\"roles-live-model\"]')"
    c.wait(f"!!{live.format(SPAWNED[1][0])}", 30)
    out["live_labels"] = [c.js(f"{live.format(a)}?.textContent || ''") for a, *_ in SPAWNED]
    from tests.helpers.studio_fleet import card_click
    card_click(c, f"document.querySelector('[data-testid=\"roles-live-node\"][data-agent=\"{SPAWNED[1][0]}\"]')")
    agent = "document.querySelector('[data-testid=\"roles-live\"][data-view=\"live\"] [data-testid=\"roles-live-agent\"]')"
    out["inspector_meta"] = c.wait(f"{agent} && {agent}.querySelector('.rl-meta')?.textContent", 15)
    c.js("document.activeElement?.blur()")
    l_key(c)
    return out


def dialog(c, rig) -> dict:
    btn = q("[data-testid=roles-apply]")
    c.wait(f"!!{btn} && !{btn}.disabled", 30)
    c.click_on(btn)
    box = q("[data-testid=roles-apply-dialog] [data-testid=dialog-cost]")
    c.wait(f"!!{box}", 10)
    out = {"cost_keys": c.js(f"{qa('[data-testid=roles-apply-dialog] [data-testid=dialog-cost] dt')}.map((d) => d.textContent)"),
           "cost_lines": c.js(f"{qa('[data-testid=roles-apply-dialog] [data-testid=dialog-cost] dd')}.map((d) => d.textContent)"),
           "cost_font": c.js(f"getComputedStyle({box}).fontFamily"),
           "dialog_ticks": c.js(TICKS.format(q("[data-testid=roles-apply-dialog] .dialog-surface")))}
    c.key("Escape")
    c.wait(f"!{q('[data-testid=roles-apply-dialog]')}", 5)
    return out


def reduced(c, rig) -> dict:
    """The working agents animate (the control); under prefers-reduced-motion a state change leaves nothing running."""
    lv = rig.live_map
    media(c)
    c.go("about:blank")
    c.go(rig.url("session"))
    c.wait("document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6", 40)
    time.sleep(0.6)
    out = {"motion_running": c.js(f"{RUNNING}.length")}
    media(c, reduce=True)
    c.go("about:blank")
    c.go(rig.url("session"))
    c.wait("document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6", 40)
    triage, scribe = q('[data-testid=fleet-node][data-key$="|t2r1a6e0"]'), q('[data-testid=fleet-node][data-key$="|s3c2r1b0"]')
    lv.state("triage", state="waiting", current="waits on you")
    c.wait(f"{triage}?.dataset.state === 'waiting'", 20)
    lv.state("scribe", state="done", current="")
    c.wait(f"{scribe}?.dataset.state === 'done'", 20)
    time.sleep(0.4)
    out["reduced_running"] = c.js(RUNNING)
    media(c)
    return out


class InstrumentDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        which = (self.argv or ["fresh"])[0]
        if which == "fresh":
            from capture_studio import seeded_home, serve
            state = seeded_home()
            srv, url = serve(state, True)
            ctx = {"state": state, "base": url.split("?", 1)[0], "frag": url.split("#", 1)[1]}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (theme, rail, ticks, quiet_load))
            finally:
                srv.shutdown()
                srv.server_close()
                shutil.rmtree(state.parent, ignore_errors=True)
            return
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            if which == "shots":
                from tests.helpers.studio_live_rig import Live
                lv = Live(rig, extra=())
                for aid, name, role, model, task in SPAWNED:
                    lv.spawn(aid, name, role, model, task)
                from tests.helpers.studio_instrument_shots import shots
                yield ((shots, (c, rig, self.argv[1])),)
            else:
                yield ((labels, (c, rig)), (dialog, (c, rig)), (reduced, (c, rig)))


if __name__ == "__main__":
    sys.exit(InstrumentDriver(sys.argv[1:]).main())
