"""tests.helpers.studio_ui_order -- the tab order in a real browser (Halo 3.1.6.0 R6, the owner's order of
2026-10-20: "session, team, roles, fleet, design", Orchestra last), for tests/test_studio_ui.py. One
headless Chrome run on the driver base over Studio on a scratch home with NO live session:

    python -m tests.helpers.studio_ui_order

  landing   nothing saved, nothing live, a default model set: Studio still opens on Roles (its Start view), not on
            the first tab (3.3.0.0 R3: with no provider at all it opens on Setup, tests/test_studio_setup.py)
  tabs      the tab strip in order: each tab's label and its key chip
  keys      Alt+1 .. Alt+9 each select the tab the strip shows for that key; Alt+1 (Session, nothing live)
            shows the Session Start view
  help      `?` on Session: How Session works lists Alt+1 first
  hint      the status bar's key hint runs from the first tab's key to the last one's
  palette   the palette's groups: Go to, Help, the sections in tab order; Go to lists the tabs in order

The last stdout line is the JSON of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest  # noqa: E402

SEL = "document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.querySelector('.tab-label')?.textContent || ''"
# 3.3.2.0 R1: the sections are the icon rail's rows (no printed key: the title is the tooltip and the name);
# the keys are the palette's Go to hints
TABS = ("[...document.querySelectorAll('[data-testid=\"section-tab\"]')].map((t) => "
        "[t.querySelector('.tab-label')?.textContent || '', t.title, t.querySelectorAll('.kbd').length])")
ORDER = [("Session", "Alt 1"), ("Team", "Alt 2"), ("Roles", "Alt 3"), ("Fleet", "Alt 4"), ("Design", "Alt 5"), ("Orchestra", "Alt 6"),
         ("Packs", "Alt 7"), ("Setup", "Alt 8"), ("Settings", "Alt 9")]  # Packs: 3.2.0.0 R6; Setup: 3.3.0.0 R1; Settings: 3.3.3.0 R2


def maybe(c, expr: str, timeout: float):
    """`c.wait`, or None when it times out (the next check names what it saw)."""
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def alt(c, n: int) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=str(n), code=f"Digit{n}", windowsVirtualKeyCode=48 + n, modifiers=1)


def landing(c, url: str) -> dict:
    from halo_harness.theme import set_config_value
    set_config_value("model", "ol:ui-order:1b")  # 3.3.0.0 R3: a provider-less home opens on Setup instead
    c.go(url)
    c.wait("document.querySelectorAll('[data-testid=\"section-tab\"]').length === 9", 40)  # 3.3.3.0 R2: + Settings
    if maybe(c, "!!document.querySelector('[data-testid=\"start-here-dismiss\"]')", 8):  # a fresh home's Start here overlay
        c.click_on("document.querySelector('[data-testid=\"start-here-dismiss\"]')")
        c.wait("!document.querySelector('[data-testid=\"start-here\"]')", 10)
    return {"landing": c.js(SEL), "landing_live": c.js("document.documentElement.dataset.liveSession || ''"),
            "landing_roles_start": maybe(c, "document.querySelectorAll('[data-testid=\"roles-start\"]').length", 20) or 0}


def tabs(c) -> dict:
    return {"tabs": c.js(TABS)}


def keys(c) -> dict:
    out: dict = {"pressed": []}
    for n in (2, 3, 4, 5, 6, 7, 8, 9, 1):
        want = ORDER[n - 1][0]
        alt(c, n)
        out["pressed"].append([n, maybe(c, f"{SEL} === '{want}' && {SEL}", 15) or c.js(SEL)])
    out["session_start"] = maybe(c, "document.querySelectorAll('[data-section=\"session\"] [data-testid=\"session-start\"]').length", 20) or 0
    return out


def help_keys(c) -> dict:
    c.click_on("document.querySelector('[data-testid=\"session-start\"] .fl-start-head')")  # off any panel: `?` is the section's
    c.key("?")
    c.wait("!!document.querySelector('[data-testid=\"section-help\"] .section-help-keys li')", 15)
    first = c.js("(() => { const li = document.querySelector('[data-testid=\"section-help\"] .section-help-keys li');"
                 " return li ? [li.querySelector('.kbd-group')?.getAttribute('aria-label') || '', li.querySelector('.muted')?.textContent || ''] : null })()")
    title = c.js("document.querySelector('[data-testid=\"section-help\"]')?.textContent?.includes('How Session works')")
    c.click_on("document.querySelector('[data-testid=\"section-help-ok\"]')")
    c.wait("!document.querySelector('[data-testid=\"section-help\"]')", 10)
    return {"help_first_key": first, "help_is_session": title}


def hint(c) -> dict:
    return {"hint_keys": c.js("[...document.querySelectorAll('.hud-keys .kbd-group')].map((k) => k.getAttribute('aria-label'))")}


def palette(c) -> dict:
    c.click_on("document.querySelector('.palette-btn')")
    c.wait("document.querySelectorAll('.palette-group-name').length > 3", 15)
    out = {"palette_groups": c.js("[...document.querySelectorAll('.palette-group')].map((g) => g.getAttribute('aria-label'))"),
           "palette_goto": c.js("[...document.querySelectorAll('.palette-group[aria-label=\"Go to\"] .palette-label')].map((l) => l.textContent)"),
           "palette_goto_keys": c.js("[...document.querySelectorAll('.palette-group[aria-label=\"Go to\"] .palette-item')]"
                                     ".map((i) => [i.querySelector('.palette-label')?.textContent || '', i.querySelector('.kbd-group')?.getAttribute('aria-label') || ''])")}
    c.key("Escape")
    return out


class OrderDriver(Driver):
    """Studio over the scoped scratch home (no session registered there: nothing is live)."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        srv, _ = serve(state)
        url = f"http://127.0.0.1:{srv.server_address[1]}/?tour=off#t={srv.token}"
        try:
            yield ((landing, (c, url)), (tabs, (c,)), (keys, (c,)), (help_keys, (c,)), (hint, (c,)), (palette, (c,)))
        finally:
            srv.shutdown()
            srv.server_close()


ARGS = ("-m", "tests.helpers.studio_ui_order")


def register(test, json_of, chrome) -> None:
    @test
    def test_the_tabs_run_session_first_and_orchestra_last_with_their_keys(ctx: Ctx):
        """3.1.6.0 R6: the owner's order (Session, Team, Roles, Fleet, Design, then Orchestra) on the section rows
        (3.3.2.0 R1: the icon rail, no printed key; Alt+1 .. Alt+9 are the palette's Go to hints); each key selects its row; with nothing live Studio still opens on Roles
        and Alt+1 shows Session's Start view; How Session works lists Alt+1 first; the status bar's hint and the
        palette's groups follow the same order."""
        if not chrome():
            raise SkipTest("no Chrome found (the tab order test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        ctx.check(f"nothing live, nothing saved: Studio opens on Roles' Start view, got {got.get('landing')!r} "
                  f"{got.get('landing_live')!r} {got.get('landing_roles_start')}",
                  got.get("landing") == "Roles" and got.get("landing_live") == "" and got.get("landing_roles_start") == 1)
        ctx.check(f"3.3.2.0 R1: the rail's rows, in order, titled, no printed key, got {got.get('tabs')}",
                  [tuple(t) for t in got.get("tabs") or []] == [(t, t, 0) for t, _ in ORDER])
        ctx.check(f"the keys in the palette's Go to: Session / Alt+1 first ... Settings / Alt+9 last, got {got.get('palette_goto_keys')}",
                  [tuple(t) for t in got.get("palette_goto_keys") or []][:9] == ORDER)
        want = [[n, ORDER[n - 1][0]] for n in (2, 3, 4, 5, 6, 7, 8, 9, 1)]
        ctx.check(f"Alt+2 .. Alt+9 then Alt+1 select their tabs, got {got.get('pressed')}", got.get("pressed") == want)
        ctx.check(f"Alt+1 with nothing live: the Session Start view, got {got.get('session_start')}", got.get("session_start") == 1)
        ctx.check(f"How Session works: Alt+1 Session is its first key, got {got.get('help_first_key')} {got.get('help_is_session')}",
                  got.get("help_first_key") == ["Alt 1", "Session"] and got.get("help_is_session") is True)
        hk = got.get("hint_keys") or []
        ctx.check(f"the status bar's hint: Alt+1 to Alt+9 (3.3.3.0 R2: Settings last), got {hk}", "Alt 1" in hk and "Alt 9" in hk and hk.index("Alt 1") < hk.index("Alt 9"))
        groups = got.get("palette_groups") or []
        sections = [g for g in groups if g in {t for t, _ in ORDER}]
        ctx.check(f"the palette: Go to, Help, then the section groups in tab order, got {groups}",
                  groups[:2] == ["Go to", "Help"] and sections == [t for t, _ in ORDER if t in sections] and len(sections) >= 4)
        ctx.check(f"Go to lists the tabs in order, got {got.get('palette_goto')}", got.get("palette_goto") == [t for t, _ in ORDER])


if __name__ == "__main__":
    sys.exit(OrderDriver(sys.argv[1:]).main())
