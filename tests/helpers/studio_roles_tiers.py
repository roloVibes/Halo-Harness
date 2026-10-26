"""tests.helpers.studio_roles_tiers -- tiers on the Roles canvas (Halo 3.1.6.0
R1; the owner: "how do I create custom tiers ... a media tier ... trigger that
whole tier ... much easier to add in the canvas"), real clicks, drags and keys
in headless Chrome through the driver base. tests/test_studio_roles_tiers.py
runs it:

    python -m tests.helpers.studio_roles_tiers tiers

Over a scratch home with a seeded catalog and `tier-lab` active (the
halo-dev-cycle lineup, no tiers declared: one tier, fanned out under main):
the edge labels on the fan (main selected, then nothing selected), Add tier
on the bar (tier 0 = main alone, the new box empty with "Drag cards here"), a
card dragged in, a double-click rename, a reload; the box menu's Model,
Trigger and Max parallel (tier_menu.py: each read back from the file on
disk), a second tier and the labels on that three-tier lineup, Delete, and
Ctrl+Z. No model is called. The last stdout line is the JSON of what it saw
(exit 2: no Chrome)."""
from __future__ import annotations

import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

LINEUP = "tier-lab"
LABELS = """(() => { const els = [...document.querySelectorAll('[data-testid="roles-edge-label"]')], r = els.map((e) => e.getBoundingClientRect());
  let o = 0; for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) { const a = r[i], b = r[j];
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) o++; }
  return {shown: r.length, overlaps: o, texts: els.map((e) => e.textContent)}; })()"""
BOXES = """(() => { const r = [...document.querySelectorAll('[data-testid="roles-tier"]')].map((e) => e.getBoundingClientRect());
  return r.some((a, i) => r.some((b, j) => j > i && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom)); })()"""


def tier(name: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-tier\"][data-tier=\"{name}\"]')"


def card(agent: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-card\"][data-agent=\"{agent}\"]')"


def on_disk(state: Path) -> list:
    path = state / "teams" / f"{LINEUP}.yaml"
    for _ in range(40):  # Windows: a read during the save's os.replace raises PermissionError for a few ms
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            break
        except (PermissionError, OSError, ValueError):
            time.sleep(0.05)
    else:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(raw.get("tiers") or [])


def members(state: Path) -> dict:
    return {t["name"]: list(t.get("members") or []) for t in on_disk(state)}


def until(fn, timeout: float = 10):
    """`fn()` once it is truthy (or its last value when the time is up)."""
    end = time.time() + timeout
    got = fn()
    while not got and time.time() < end:
        time.sleep(0.1)
        got = fn()
    return got


def settle(c, expr: str) -> list:
    """The element's rect once it stopped moving (the canvas lays itself out and fits)."""
    last, end = None, time.time() + 5
    while time.time() < end:
        r = [round(v) for v in c.rect(expr)]
        if r == last:
            return r
        last = r
        time.sleep(0.25)
    return last or c.rect(expr)


def dblclick(c, expr: str) -> None:
    x, y, w, h = c.rect(expr)
    x, y = x + w / 2, y + h / 2
    c.mouse("mouseMoved", x, y)
    for n in (1, 2):
        for kind in ("mousePressed", "mouseReleased"):
            c.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", buttons=1 if kind == "mousePressed" else 0, clickCount=n)


def empty_spot(c) -> None:
    sx, sy, sw, sh = c.rect("document.querySelector('.rc-scroll')")
    c.click(sx + sw - 12, sy + sh - 12)  # the canvas's empty corner: no card selected


def fan_labels(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    out["cards"] = c.wait(f"document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 7 && {card('orchestrator')} && "
                          "document.querySelectorAll('[data-testid=\"roles-card\"]').length", 30)
    out["fan_tiers"] = c.js("document.querySelectorAll('[data-testid=\"roles-tier\"]').length")
    settle(c, card("orchestrator"))
    c.click_on(card("orchestrator"), 0.5, 0.25)
    out["fan_selected"] = c.wait(f"{card('orchestrator')}.dataset.selected && {LABELS}", 10)
    empty_spot(c)
    time.sleep(0.4)
    out["fan_plain"] = c.js(LABELS)
    return out


def add_drag_rename(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.click_on("document.querySelector('[data-testid=\"roles-tier-add\"]')")
    c.wait("document.activeElement?.dataset.testid === 'roles-tier-new-name'", 10)
    c.type_text("media")
    c.key("Enter")
    out["added"] = until(lambda: members(state) if "media" in members(state) else None)
    out["drop_hint"] = c.wait(f"{tier('media')}?.querySelector('[data-testid=\"roles-tier-drop\"]')?.textContent", 10)
    out["drop_brackets"] = c.js(f"{tier('media')}.classList.contains('holo-frame') && !!{tier('media')}.querySelector('.holo-corners')")
    out["bar_closed"] = c.wait("!document.querySelector('[data-testid=\"roles-tier-new-name\"]')", 5)
    settle(c, tier("media"))
    out["boxes_overlap_after_add"] = c.js(BOXES)
    x, y, w, h = settle(c, card("implementer"))
    bx, by, bw, bh = c.rect(f"{tier('media')}.querySelector('[data-testid=\"roles-tier-drop\"]')")
    c.drag(x + w / 2, y + h / 2, bx + bw / 2, by + bh / 2)
    out["dragged"] = until(lambda: members(state).get("media") == ["worker"] and members(state))
    out["in_box"] = c.wait(f"""(() => {{ const r = {card('implementer')}.getBoundingClientRect(), b = {tier('media')}.getBoundingClientRect();
      return r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1; }})()""", 10)
    label = f"{tier('media')}.querySelector('[data-testid=\"roles-tier-name\"]')"
    for _ in range(3):  # the box may still be settling from the save: a double-click on a moving label is two clicks
        settle(c, label)
        dblclick(c, label)
        if until(lambda: c.js("document.activeElement?.dataset.testid === 'roles-tier-rename'"), 3):
            break
    c.wait("document.activeElement?.dataset.testid === 'roles-tier-rename'", 5)
    c.js("document.activeElement.select(); 1")
    c.type_text("studio-media")
    c.key("Enter")
    out["renamed"] = until(lambda: "studio-media" in members(state) and members(state))
    c.go("about:blank")
    c.go(url)
    out["reloaded"] = c.wait(f"!!{tier('studio-media')} && !!{card('implementer')} && (() => {{ const r = {card('implementer')}.getBoundingClientRect(), "
                             f"b = {tier('studio-media')}.getBoundingClientRect(); return r.left >= b.left - 1 && r.right <= b.right + 1 && 'in'; }})()", 30)
    out["after_reload"] = members(state)
    return out


class TiersDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_roles import seed_catalog
        from capture_studio import seeded_home, serve
        from halo_harness.teams_yaml import load_team_template_raw
        from halo_harness.theme import set_config_value
        from tests.helpers.studio_roles_tier_menu import STEPS
        state = seeded_home()
        seed_catalog(state)
        set_config_value("model", "or:deepseek/deepseek-chat")  # the session's model (every shipped bio says default)
        raw = {k: v for k, v in (load_team_template_raw("halo-dev-cycle", state_dir=state) or {}).items() if not str(k).startswith("_")}
        raw.update(name=LINEUP, description="halo-dev-cycle with no tiers yet: one box, fanned out under main")
        (state / "teams" / f"{LINEUP}.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        set_config_value("team", LINEUP)
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace")
        try:
            yield ((fan_labels, (c, url, state)), (add_drag_rename, (c, url, state))) + tuple((fn, (c, url, state)) for fn in STEPS)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(TiersDriver(sys.argv[1:]).main())
