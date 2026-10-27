"""tools/capture_roles.py -- the Roles captures for tools/capture_studio.py
--mode roles (Halo 3.0.7.0 round R2: Roles is a React section of the shell,
no framed classic page), through headless Chrome over the DevTools protocol
(tests/helpers/cdp.py).

    docs/media/studio-roles.png   a seeded lineup with two declared tiers (the main agent alone in tier 0,
                                  the leads in tier 1, the rest in the implicit last tier), a catalog with
                                  prices, and a live card: the real session of tests/helpers/studio_fleet_rig.py
                                  (its implementer mid-work glows; its Live tab open in the Inspector)

With --dom the section is read twice -- its Start view first (only the
shipped lineups, none active), then the seeded tiers lineup with a bio open
in the form -- and the data-testid values are counted (the last stdout line
is the JSON: {"start": {...}, "roles": {...}}). Never two Chromes at once.
3.1.7.0 R2: every Studio draws you@studio (tools/capture_identity.py) and every
page is guarded before it is counted or shot.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "roles-start", "roles-canvas", "roles-card", "roles-tier", "roles-edge", "roles-problem", "bio-form", "model-row",
       "roles-lineup", "roles-bio", "panel-title", "roles-live-badge", "model-test", "legacy-frame")

# the catalog the pills, the picker table and the dead-id check read (OpenRouter's cache shape; per-token prices as strings)
CATALOG = {"anthropic/claude-fable-5.1": (15, 75, 400000), "anthropic/claude-opus-5.5": (12, 60, 400000), "anthropic/claude-sonnet-5": (3, 15, 400000),
           "anthropic/claude-haiku-4.5": (1, 5, 200000), "qwen/qwen3-coder": (0.4, 1.6, 262000), "deepseek/deepseek-chat": (0.27, 1.1, 128000),
           "google/gemini-3-flash": (0.3, 2.5, 1000000)}
TIERS = [{"name": "top", "members": ["boss"]}, {"name": "leads", "members": ["worker", "research"], "max_parallel": 2}]


def seed_catalog(state: Path) -> None:
    from halo_harness.theme import set_config_value
    rows = {k: {"context_length": c, "pricing": {"prompt": f"{i / 1e6:.10f}", "completion": f"{o / 1e6:.10f}"}} for k, (i, o, c) in CATALOG.items()}
    (state / "models.json").write_text(json.dumps(rows), encoding="utf-8")
    set_config_value("providers.openrouter.enabled", True)  # the catalog lists OpenRouter's rows only while it is enabled


def seed_tiers(state: Path, name: str = "studio-tiers", *, dead: bool = False, active: bool = True) -> dict:
    """A user lineup from halo-dev-cycle with two declared tiers (and, with `dead`, a card on a bio whose model is not in the catalog)."""
    import yaml
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import load_team_template_raw
    from halo_harness.theme import set_config_value
    raw = {k: v for k, v in (load_team_template_raw("halo-dev-cycle", state_dir=state) or {}).items() if not str(k).startswith("_")}
    raw.update(name=name, description="The dev cycle, stacked: the boss, its two leads, everyone else under them.", tiers=TIERS)
    raw.setdefault("delegation", {})["max_depth"] = 2
    if dead:
        save_agent_bio("dead-bio", {"description": "names a model the catalog does not have", "kind": "subagent", "models": {"preference": "or:vendor/gone"}}, state_dir=state)
        raw["agents"] = list(raw["agents"]) + [{"agent": "dead-bio", "role": "custom", "as": "ghost"}]
    teams = state / "teams"
    teams.mkdir(parents=True, exist_ok=True)
    (teams / f"{name}.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    if active:
        set_config_value("team", name)
        set_config_value("roles.enabled", True)
    return raw


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def dom(c, url: str, state: Path) -> dict:
    from halo_harness.theme import set_config_value
    set_config_value("team", "")  # only the shipped lineups, none active: the Start view
    c.go(url)
    c.wait("!!document.querySelector('[data-testid=\"roles-start\"]')", 30)
    guard_page(c, "roles start")
    start = counts(c)
    seed_catalog(state)
    seed_tiers(state, dead=True)
    c.go("about:blank")
    c.go(url)
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 8", 30)
    c.wait("document.querySelectorAll('[data-testid=\"roles-problem\"]').length >= 1", 15)
    bio = "document.querySelector('[data-testid=\"roles-bio\"][data-name=\"implementer\"]')"
    c.js(f"{bio}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(bio)
    more = "document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"model-select-more\"]')"  # 3.1.4.0 R4: the table is folded
    c.wait(f"!!{more}", 20)
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    c.wait("!!document.querySelector('[data-testid=\"bio-form\"]') && document.querySelectorAll('[data-testid=\"model-row\"]').length > 0", 20)
    guard_page(c, "roles")
    return {"start": start, "roles": counts(c)}


def shoot(c, png: Path) -> int:
    """The tiers lineup in the fleet rig's real session: the implementer glows; its Live tab open."""
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    placeholder()
    with StudioFleetRig() as rig:
        rig.full = False  # 3.3.2.0 R3: the pictures show the quiet arrangement (each names the panels it opens)
        placeholder(rig.state)  # the rig's own home: you@studio
        seed_catalog(rig.state)
        seed_tiers(rig.state, name="halo-dev-cycle")  # your copy of the active lineup, stacked: the live agents still match it
        c.go(rig.url("roles", "&open=roles-inspector,roles-problems"))  # 3.3.2.0 R3: the canvas, the Inspector and Problems beside it
        c.wait("document.querySelectorAll('[data-testid=\"roles-card\"][data-live]').length >= 2", 30)
        c.click_on("[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === 'implementer')", 0.5, 0.3)
        c.wait("[...document.querySelectorAll('[data-testid=\"roles-live\"] [data-testid=\"fleet-text\"]')].some((e) => e.textContent.length > 10)", 15)
        c.wait("!document.querySelector('.toast')", 10)
        time.sleep(1.5)
        guard_page(c, png.stem)
        return c.shot(png)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    placeholder(state)
    c = open_chrome()  # the driver base: HALO_CHROME first, one headless Chrome at a time
    if c is None:
        print("no Chrome found")
        return 2
    srv = None
    try:
        if as_dom:
            srv, url = serve(state, True)
            from tests.helpers.studio_full import full  # 3.3.2.0 R3: the counts read every panel, so every panel is open
            print(json.dumps(dom(c, full(url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off")), state)))
            return 0
        png = Path(out).resolve()
        size = shoot(c, png)
        ok = size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {png} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.close()
        if srv is not None:
            srv.shutdown()
            srv.server_close()
