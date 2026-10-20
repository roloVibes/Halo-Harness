"""tests.helpers.studio_roles_glow -- the Roles card glow explained and timed
(Halo 3.1.5.0 R3) in headless Chrome on the driver base, over
tests/helpers/studio_fleet_rig.py (the halo-dev-cycle lineup active, its
agents mid-work) plus extra agents on the verifier and reviewer cards
(tests/helpers/studio_live_rig.py). tests/test_studio_roles_glow.py runs it:

    python -m tests.helpers.studio_roles_glow glow   the legend on hovering a card's glyph and its badge (four states,
                                                     the card's own marked), a done glow fading out ten seconds later,
                                                     a failed glow staying until its card is clicked (motion pinned to
                                                     no-preference; then under reduce a done card has no fade), the
                                                     one-tier fan under main, and an empty lineup's bracketed invite

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

LEGEND = "document.querySelector('[data-testid=\"roles-glow-legend\"]')"


def card(agent: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-card\"][data-agent=\"{agent}\"]')"


def legend(c) -> list:
    return c.js(f"{LEGEND} ? [{LEGEND}.dataset.state, [...{LEGEND}.querySelectorAll('[data-testid=\"roles-glow-legend-row\"]')].map((r) => "
                "[r.dataset.holoState, !!r.dataset.on, r.querySelector('.rc-legend-color').textContent])] : null")


def hover(c, expr: str) -> None:
    x, y, w, h = c.rect(expr)
    c.mouse("mouseMoved", x + w / 2, y + h / 2)


def glow(c, rig) -> dict:
    from tests.helpers.studio_fleet import card_click
    from tests.helpers.studio_live_rig import Live
    lv = Live(rig, extra=())
    out: dict = {}
    from tests.helpers.chrome_driver import emulate_motion
    emulate_motion(c, "no-preference")  # the fade is an animation: the same media on every runner
    c.go(rig.url("roles"))
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"][data-live]').length >= 3", 40)
    time.sleep(1.2)  # the canvas fits itself after its first draw
    out["fan"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-card\"]')].map((n) => [n.dataset.agent, n.dataset.role, parseFloat(n.style.left), parseFloat(n.style.top)])")
    out["tiers"] = c.js("document.querySelectorAll('[data-testid=\"roles-tier\"]').length")
    out["tier_brackets"] = c.js("document.querySelector('[data-testid=\"roles-tier\"]')?.classList.contains('holo-frame') && !!document.querySelector('[data-testid=\"roles-tier\"] .holo-corners')")
    impl = card("implementer")
    out["impl_glow"] = c.wait(f"{impl}?.dataset.glow", 10)
    hover(c, f"{impl}.querySelector('[data-testid=\"roles-card-glyph\"]')")
    out["legend_glyph"] = c.wait(f"!!{LEGEND} && 1", 5) and legend(c)
    c.mouse("mouseMoved", 4, 4)
    out["legend_gone"] = c.wait(f"!{LEGEND} && 'gone'", 5) or False
    hover(c, f"{impl}.querySelector('[data-testid=\"roles-live-badge\"]')")
    out["legend_badge"] = c.wait(f"!!{LEGEND} && 1", 5) and legend(c)
    c.mouse("mouseMoved", 4, 4)
    lv.spawn("v3r1f1e7", "verifier", "verifier", "or:mock/qwen3-coder", "Verify: the basket suite")
    lv.spawn("r3v1e2w7", "reviewer", "reviewer", "or:mock/kimi-k3-research", "Review: the basket diff")
    ver, rev = card("verifier"), card("reviewer")
    out["working"] = [c.wait(f"{ver}?.dataset.glow", 10), c.wait(f"{rev}?.dataset.glow", 10)]
    out["edge_working"] = c.js(f"[...document.querySelectorAll('[data-testid=\"roles-edge\"][data-to=\"' + {ver}.dataset.id + '\"]')].map((e) => e.dataset.state)")
    lv.state("verifier", state="done", last_text="the suite passes")
    lv.state("reviewer", state="failed", last_text="the diff did not apply")
    out["done"] = [c.wait(f"{ver}?.dataset.live === 'done' && {ver}.dataset.glow", 10), c.js(f"getComputedStyle({ver}).animationName")]
    out["red"] = c.wait(f"{rev}?.dataset.glow === 'failed' && 'failed'", 10)
    t0 = time.time()
    out["done_mid"] = c.js(f"{ver}?.dataset.glow")
    time.sleep(max(0.0, 10.6 - (time.time() - t0)))
    out["done_after"] = c.wait(f"!{ver}.dataset.live && 'off'", 5) or c.js(f"{ver}.dataset.live")
    out["failed_after"] = c.js(f"{rev}?.dataset.glow")
    card_click(c, rev)
    out["failed_clicked"] = c.wait(f"{rev}.dataset.glow !== 'failed' && ({rev}.dataset.glow || 'off')", 5) or c.js(f"{rev}.dataset.glow")
    out.update(reduced(c, lv))
    out.update(empty(c, rig))
    return out


def reduced(c, lv) -> dict:
    """Under prefers-reduced-motion: reduce a done card is still green, with no fade animation (the product rule)."""
    from tests.helpers.chrome_driver import emulate_motion
    emulate_motion(c, "reduce")
    rel = card("release-manager")
    lv.spawn("r3l3a5e7", "release-manager", "release-manager", "or:mock/qwen3-coder", "Release: tag the basket fix")
    c.wait(f"{rel}?.dataset.glow === 'working'", 10)
    lv.state("release-manager", state="done", last_text="tagged")
    got = [c.wait(f"{rel}?.dataset.live === 'done' && {rel}.dataset.glow", 10), c.js(f"getComputedStyle({rel}).animationName"),
           c.js("matchMedia('(prefers-reduced-motion: reduce)').matches")]
    emulate_motion(c, "no-preference")
    return {"reduced_done": got}


def empty(c, rig) -> dict:
    """A lineup with no cards yet: the canvas invites, in brackets, with New lineup."""
    teams = rig.state / "teams"
    teams.mkdir(parents=True, exist_ok=True)
    (teams / "blank-slate.yaml").write_text("name: blank-slate\ndescription: nothing on it yet\nagents: []\n", encoding="utf-8")
    c.go(rig.url("roles", "&again=1"))
    row = "document.querySelector('[data-testid=\"roles-lineup\"][data-name=\"blank-slate\"]')"
    c.wait(f"!!({row})", 30)
    c.click_on(row)
    inv = "document.querySelector('[data-testid=\"roles-canvas-invite\"]')"
    got = c.wait(f"{inv} && [{inv}.querySelector('.rc-invite-title').textContent, {inv}.classList.contains('holo-frame'), !!{inv}.querySelector('.holo-corners'), "
                 f"!!{inv}.querySelector('[data-testid=\"roles-invite-new\"]')]", 15)
    return {"invite": got, "invite_lineup": c.js("document.querySelector('[data-testid=\"roles-canvas\"]')?.dataset.lineup || ''")}


class GlowDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((glow, (c, rig)),)


if __name__ == "__main__":
    sys.exit(GlowDriver(sys.argv[1:]).main())
