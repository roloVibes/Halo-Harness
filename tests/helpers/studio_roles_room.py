"""tests.helpers.studio_roles_room -- the Roles canvas makes room (Halo 3.2.2.0
R5; the owner: "When I move the parts in halo studio over another block like
in roles, they disappear"), real drags and clicks in headless Chrome through
the driver base. tests/test_studio_roles_tiers.py runs it:

    python -m tests.helpers.studio_roles_room room

Over a scratch home with a seeded catalog and studio-tiers active (tiers top:
boss; leads: worker, research; the implicit rest: scout -- a tester card added
second in the list --, verify, review, release, watchdog): a card dropped onto another card in its tier (both stay visible,
no two cards overlap, the dropped one is on top), a card dropped onto a card
in another tier (the tier move, beside that card), a card dropped on a
collapsed tier's strip (not hidden, the toast, the tiers on disk unchanged),
a card held over that strip (the tier opens), and a card removed and saved
(scout: every other card keeps its id and its spot in the layout file). The last stdout line is
the JSON of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_roles import card, tid, tier, tiers_on_disk  # noqa: E402
from tests.helpers.studio_roles_tiers import settle, until  # noqa: E402

LINEUP = "studio-tiers"
# every pair of drawn cards that overlap (by agent), on screen
CARD_OVERLAPS = f"""(() => {{ const cs = [...{tid('roles-card')}].map((e) => [e.dataset.agent, e.getBoundingClientRect()]), out = [];
  for (const [a, r] of cs) for (const [b, q] of cs) if (a < b && r.left < q.right - 1 && q.left < r.right - 1 && r.top < q.bottom - 1 && q.top < r.bottom - 1) out.push(a + '/' + b);
  return out; }})()"""


def shown(c, agent: str) -> bool:
    return bool(c.js(f"(() => {{ const e = {card(agent)}; if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }})()"))


def layout_file(state: Path) -> dict:
    p = state / "studio" / "layouts" / f"{LINEUP}.json"
    for _ in range(20):
        try:
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("nodes") or {}
        except (OSError, ValueError):
            time.sleep(0.05)
    return {}


def settled_layout(state: Path, ok, timeout: float = 12.0) -> dict:
    """The layout file once `ok(nodes)` holds AND two reads 0.7 s apart agree: the page saves 500 ms after a move,
    and a clamp or a nudge after a re-render can save once more (the Windows runner caught a snapshot in between)."""
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        now = layout_file(state)
        if ok(now) and now and now == last:
            return now
        last = now
        time.sleep(0.7)
    return last or {}


def agents_on_disk(state: Path) -> list:
    import yaml
    try:
        raw = yaml.safe_load((state / "teams" / f"{LINEUP}.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return []
    return [str(a.get("agent")) for a in raw.get("agents") or [] if isinstance(a, dict)]


def toast_with(c, text: str, timeout: float = 8):
    return c.wait(f"[...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => t.includes({json.dumps(text)}))", timeout)


def grab(c, agent: str) -> tuple:
    x, y, w, h = settle(c, card(agent))
    return x + w / 2, y + h * 0.2  # the card's head: its name, not the model pill


def drop_on_card(c, agent: str, onto: str) -> None:
    x0, y0 = grab(c, agent)
    x1, y1 = grab(c, onto)
    c.drag(x0, y0, x1, y1, steps=12)


def same_tier(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"{tid('roles-card')}.length >= 7 && !!{card('reviewer')}", 30)
    time.sleep(1.0)  # the first draw fits the canvas
    out["start_overlaps"] = c.js(CARD_OVERLAPS)
    drop_on_card(c, "verifier", "reviewer")
    time.sleep(0.8)
    out["same_both_shown"] = shown(c, "verifier") and shown(c, "reviewer")
    out["same_overlaps"] = c.js(CARD_OVERLAPS)
    out["same_top"] = c.js(f"{card('verifier')}.dataset.top === 'true' && getComputedStyle({card('verifier')}).zIndex")
    return out


def other_tier(c, url: str, state: Path) -> dict:
    out: dict = {}
    drop_on_card(c, "release-manager", "implementer")
    out["moved_tiers"] = until(lambda: "release" in tiers_on_disk(state).get("leads", []) and tiers_on_disk(state), 10)
    time.sleep(0.8)
    out["other_both_shown"] = shown(c, "release-manager") and shown(c, "implementer")
    out["other_overlaps"] = c.js(CARD_OVERLAPS)
    out["other_in_leads"] = c.wait(f"""(() => {{ const r = {card('release-manager')}.getBoundingClientRect(), b = {tier('leads')}.getBoundingClientRect();
      return r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1 && 'in'; }})()""", 10)
    return out


def collapsed_tier(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.click_on(f"{tier('leads')}.querySelector('[data-testid=\"roles-tier-toggle\"]')")
    out["leads_collapsed"] = c.wait(f"{tier('leads')}.dataset.collapsed === 'true' && 'collapsed'", 5)
    before = tiers_on_disk(state)
    x0, y0 = grab(c, "watchdog")
    bx, by, bw, bh = settle(c, tier("leads"))
    c.drag(x0, y0, bx + bw / 2, by + bh / 2, steps=6)  # a quick drop on the strip
    out["shut_toast"] = toast_with(c, "is collapsed; it stays where it was")
    time.sleep(0.6)
    out["shut_shown"] = shown(c, "watchdog")
    out["shut_unchanged"] = tiers_on_disk(state) == before
    out["shut_still_collapsed"] = c.js(f"{tier('leads')}.dataset.collapsed === 'true'")
    # held over the strip: the tier opens, and the drop then joins it
    x0, y0 = grab(c, "watchdog")
    bx, by, bw, bh = settle(c, tier("leads"))
    tx, ty = bx + bw / 2, by + bh / 2
    c.mouse("mouseMoved", x0, y0)
    c.mouse("mousePressed", x0, y0)
    for i in range(1, 9):
        c.mouse("mouseMoved", x0 + (tx - x0) * i / 8, y0 + (ty - y0) * i / 8)
    time.sleep(1.0)
    out["held_opened"] = c.js(f"!{tier('leads')}.dataset.collapsed")
    c.mouse("mouseMoved", tx + 1, ty + 1)
    c.mouse("mouseReleased", tx + 1, ty + 1)
    out["held_joined"] = until(lambda: "watchdog" in tiers_on_disk(state).get("leads", []) and tiers_on_disk(state), 10)
    time.sleep(0.8)
    out["held_shown"] = shown(c, "watchdog")
    out["held_overlaps"] = c.js(CARD_OVERLAPS)
    # 3.3.0.0 R1: the joined card lands inside the leads tier box (its column), never at the raw drop point beside it
    out["held_in_box"] = c.js(f"(() => {{ const a = {card('watchdog')}.getBoundingClientRect(), b = {tier('leads')}.getBoundingClientRect(); "
                              "return a.left >= b.left - 1 && a.right <= b.right + 1 && a.top >= b.top - 1 && a.bottom <= b.bottom + 1; })()")
    out["held_rects"] = c.js(f"[{card('watchdog')}, {tier('leads')}].map((e) => {{ const r = e.getBoundingClientRect(); "
                             "return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })")
    return out


def remove_keeps(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.js("document.querySelector('.rc-scroll').focus(); 1")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", text="a", windowsVirtualKeyCode=65)
    c.call("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", windowsVirtualKeyCode=65)  # A: every card laid out and saved
    ids = c.js(f"[...{tid('roles-card')}].map((e) => e.dataset.id)")
    before = settled_layout(state, lambda f: set(ids) <= set(f))
    out["layout_before"] = before
    gone = c.js(f"{card('tester')}.dataset.id")  # scout: the second card of eight, nothing routes to it
    out["removed_id"] = gone
    c.click_on(card("tester"), 0.5, 0.2)
    c.wait(f"{card('tester')}.dataset.selected", 5)
    rm = "document.querySelector('[data-testid=\"roles-remove-card\"]')"
    c.js(f"{rm}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(rm)
    yes = "document.querySelector('[data-testid=\"roles-delete-card-yes\"]')"
    c.wait(f"!!{yes}", 5)
    c.click_on(yes)
    c.wait(f"!{card('tester')}", 10)
    c.click_on(f"{tid('roles-save')}[0]")
    out["saved_agents"] = until(lambda: (lambda a: a if a and "tester" not in a else None)(agents_on_disk(state)), 10)
    after = settled_layout(state, lambda f: bool(f) and gone not in f)
    out["layout_after"] = after
    out["kept"] = sorted(k for k in before if k != gone and after.get(k) == before[k])
    out["others"] = sorted(k for k in before if k != gone)
    out["after_overlaps"] = c.js(CARD_OVERLAPS)
    return out


class RoomDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_roles import seed_catalog, seed_tiers
        from capture_studio import seeded_home, serve
        state = seeded_home()
        seed_catalog(state)
        raw = seed_tiers(state)
        raw["agents"].insert(1, {"agent": "tester", "role": "custom", "as": "scout"})  # a card early in the list that nothing routes to
        import yaml
        (state / "teams" / f"{LINEUP}.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        url = url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace")
        try:
            yield tuple((fn, (c, url, state)) for fn in (same_tier, other_tier, collapsed_tier, remove_keeps))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(RoomDriver(sys.argv[1:]).main())
