"""tests.helpers.studio_roles_auto -- the Auto lineup in Studio (Halo 3.1.9.0
R2) in headless Chrome on the driver base, over tests/helpers/
studio_fleet_rig.py with its `team:` cleared (so the default `auto` lineup is
the one in use) and scripted agent rows (tests/helpers/studio_live_rig.py
`Live`: the rows a GET fleet lists and the `agent_state` frames a live
session sends). tests/test_studio_roles_auto.py runs it:

    python -m tests.helpers.studio_roles_auto auto   Roles names the default (the Start view's "In use now", Open
                                                     auto) and opens the pool with "active (default)"; an idle pool
                                                     card's pill reads auto; a live coder's pill names the model it
                                                     was picked for, the reason on hover; the Inspector's Live tab
                                                     prints "auto: <model> -- <reason>"; the Session Live column's
                                                     spawn line carries the reason; a lineup without auto shows no
                                                     pick even for an agent whose row has a reason

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

CODER_WHY = "the bio asks for tools, the best tools model within 3x the cheapest ($0.05/$0.20 per 1M)"
MEDIA_WHY = "an image in the task, the cheapest vision model ($0.30/$1.20 per 1M)"
LINES = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"


def card(agent: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-card\"][data-agent=\"{agent}\"]')"


def pill(agent: str) -> str:
    return f"{card(agent)}?.querySelector('[data-testid=\"roles-model-pill\"]')"


def row(aid: str, name: str, role: str, bio: str, lineup: str, model: str, why: str, task: str) -> dict:
    return {"agent_id": aid, "parent": "main", "name": name, "role": role, "bio": bio, "lineup": lineup, "model": model,
            "model_reason": why, "kind": "member", "task": task, "since": time.time(), "state": "running", "turns": 1,
            "cost_usd": 0.0, "current": "thinking", "last_text": "", "transcript": None}


def auto(c, rig) -> dict:
    from halo_harness.theme import unset_config_value
    from tests.helpers.studio_fleet import card_click
    from tests.helpers.studio_live_rig import Live
    unset_config_value("team")  # nothing names a lineup: the default auto lineup is in use
    lv = Live(rig, extra=())
    out: dict = {"state": rig.api("GET", "state")[1]}
    c.go(rig.url("roles"))
    c.wait("!!document.querySelector('[data-testid=\"roles-start\"]') || document.querySelectorAll('[data-testid=\"roles-card\"]').length > 0", 40)
    out["start_in_use"] = c.js("document.querySelector('[data-testid=\"roles-start-in-use\"]')?.textContent || ''")
    if c.js("!!document.querySelector('[data-testid=\"roles-start-open-default\"]')"):
        c.click_on("document.querySelector('[data-testid=\"roles-start-open-default\"]')")
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 8", 30)
    time.sleep(1.2)  # the canvas fits itself after its first draw
    out["cards"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-card\"]')].map((n) => n.dataset.agent)")
    out["chip"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-active\"]')].map((x) => [x.textContent, x.dataset.default || ''])")
    out["idle_pill"] = c.js(f"[{pill('auto-planner')}.textContent, {pill('auto-planner')}.title, {pill('auto-planner')}.dataset.picked || '']")
    lv.rows["c0d3a001"] = row("c0d3a001", "coder", "coder", "auto-coder", "auto", "or:mock/cheap-coder", CODER_WHY,
                              "Fix the basket total")
    lv.state("coder")
    out["live_pill"] = c.wait(f"{pill('auto-coder')}?.dataset.picked && [{pill('auto-coder')}.textContent, "
                              f"{pill('auto-coder')}.title, {pill('auto-coder')}.dataset.picked]", 15)
    card_click(c, card("auto-coder"))
    out["live_tab"] = c.wait("document.querySelector('[data-testid=\"roles-live-reason\"]')?.textContent", 15)
    out.update(spawn_line(c, rig, lv))
    out.update(without_auto(c, rig, lv))
    return out


def spawn_line(c, rig, lv) -> dict:
    """A member spawned while the Session section shows: its line says what it runs on and why."""
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 3", 40)
    time.sleep(1.0)  # the first look at the tree is silent
    lv.rows["m3d1a001"] = row("m3d1a001", "media", "media", "auto-media", "auto", "or:mock/vision-eyes", MEDIA_WHY,
                              "Describe shot.png")
    lv.state("media")
    got = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'spawn' && l.querySelector('.slv-name').textContent === 'media')"
                 ".map((l) => l.textContent).pop()", 15)
    return {"spawn_line": got}


def without_auto(c, rig, lv) -> dict:
    """halo-dev-cycle has no auto card: a reason on an agent's row changes nothing on its card."""
    lv.rows["v3r1a001"] = row("v3r1a001", "verifier", "verify", "verifier", "halo-dev-cycle", "or:mock/qwen3-coder",
                              "a reason a pinned card ignores", "Verify the suite")
    lv.state("verifier")
    # the panels with nothing applied open on the lineup in use: the default auto
    c.go(rig.url("roles", "&again=1&view=workspace"))
    out = {"workspace_opens": c.wait("document.querySelector('[data-testid=\"roles-canvas\"]')?.dataset.lineup", 30)}
    from halo_harness.theme import set_config_value
    set_config_value("team", "halo-dev-cycle")  # a lineup applied: the panels open on it
    c.go(rig.url("roles", "&again=2"))
    c.wait("document.querySelector('[data-testid=\"roles-canvas\"]')?.dataset.lineup === 'halo-dev-cycle'", 30)
    c.wait(f"{card('verifier')}?.dataset.live", 20)
    out["chip_applied"] = c.js("[...document.querySelectorAll('[data-testid=\"roles-active\"]')].map((x) => [x.textContent, x.dataset.default || ''])")
    out["plain"] = c.js(f"[{pill('verifier')}.textContent, {pill('verifier')}.title, "
                        "[...document.querySelectorAll('[data-testid=\"roles-model-pill\"]')].filter((p) => p.dataset.picked).length]")
    return out


class AutoDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((auto, (c, rig)),)


if __name__ == "__main__":
    sys.exit(AutoDriver(sys.argv[1:]).main())
