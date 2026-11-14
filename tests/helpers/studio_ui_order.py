"""tests.helpers.studio_ui_order -- the tab order in a real browser (Halo 3.1.6.0 R6, the owner's order of
2026-10-20: "session, team, roles, fleet, design", Orchestra last; 3.3.13.0 R2: Design is the design pack's), for tests/test_studio_ui.py. One
headless Chrome run on the driver base over Studio on a scratch home with NO live session:

    python -m tests.helpers.studio_ui_order

  landing   nothing saved, nothing live, a default model set: Studio still opens on Agents (3.6.0.0 R1: its Agents tab), not on
            the first tab (3.3.0.0 R3: with no provider at all it opens on Setup, tests/test_studio_setup.py)
  tabs      the tab strip in order: each tab's label and its key chip
  keys      Alt+1 .. Alt+9 each select the tab the strip shows for that key; Alt+1 (Session, nothing live)
            shows the Session Start view
  help      `?` on Session: How Session works lists Alt+1 first
  hint      the status bar's key hint runs from the first tab's key to the last one's
  palette   the palette's groups: Go to, Help, the sections in tab order; Go to lists the tabs in order

The last stdout line is the JSON of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import json
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
ORDER = [("Session", "Alt 1"), ("Agents", "Alt 2"), ("Local", "Alt 3"), ("Packs", "Alt 4"), ("Setup", "Alt 5"),
         ("Settings", "Alt 6")]  # 3.3.13.0 R2: Design is the design pack's; 3.3.16.0 R1: Agents took in Team, Roles, Orchestra; R2: and Fleet


def maybe(c, expr: str, timeout: float):
    """`c.wait`, or None when it times out (the next check names what it saw)."""
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def alt(c, n: int) -> None:
    for kind in ("keyDown", "keyUp"):
        d = n % 10  # 3.3.5.0 R1: the tenth slot is Digit0
        c.call("Input.dispatchKeyEvent", type=kind, key=str(d), code=f"Digit{d}", windowsVirtualKeyCode=48 + d, modifiers=1)


def landing(c, url: str) -> dict:
    from halo_harness.theme import set_config_value
    set_config_value("model", "ol:ui-order:1b")  # 3.3.0.0 R3: a provider-less home opens on Setup instead
    c.go(url)
    c.wait("document.querySelectorAll('[data-testid=\"section-tab\"]').length === 6", 40)  # 3.3.3.0 R2: + Settings; 3.3.5.0 R1: + Local; 3.3.16.0 R2: - Fleet
    if maybe(c, "!!document.querySelector('[data-testid=\"start-here-dismiss\"]')", 8):  # a fresh home's Start here overlay
        c.click_on("document.querySelector('[data-testid=\"start-here-dismiss\"]')")
        c.wait("!document.querySelector('[data-testid=\"start-here\"]')", 10)
    return {"landing": c.js(SEL), "landing_live": c.js("document.documentElement.dataset.liveSession || ''"),
            "landing_view": maybe(c, "document.querySelector('[data-testid=\"agents\"]')?.dataset.view === 'crew' && !!document.querySelector('[data-testid=\"crew-empty\"]') && 'crew'", 20) or ""}  # 3.6.0.0 R1: nothing runs: the Agents tab


def tabs(c) -> dict:
    return {"tabs": c.js(TABS)}


def keys(c) -> dict:
    out: dict = {"pressed": []}
    for n in (2, 3, 4, 5, 6, 1):  # 3.3.16.0 R2: six sections
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
    # 3.3.16.0 R3: the palette renders its first 200 rows, then the rest a chunk per frame (WindowedRows): wait for the
    # value the test asserts -- four section groups -- not for the first chunk
    names = json.dumps([t for t, _ in ORDER])
    c.wait(f"[...document.querySelectorAll('.palette-group')].filter((g) => {names}.includes(g.getAttribute('aria-label'))).length >= 4", 15)
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
        """3.1.6.0 R6: the owner's order (Session, Team, Roles, Fleet, then Orchestra; Design a pack's) on the section rows
        (3.3.2.0 R1: the icon rail, no printed key; Alt+1 .. Alt+9 are the palette's Go to hints); each key selects its row; with nothing live Studio still opens on Roles
        and Alt+1 shows Session's Start view; How Session works lists Alt+1 first; the status bar's hint and the
        palette's groups follow the same order."""
        if not chrome():
            raise SkipTest("no Chrome found (the tab order test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        ctx.check(f"nothing live, nothing saved: Studio opens on Agents, on its Agents tab (3.6.0.0 R1; Live while a session runs), got "
                  f"{got.get('landing')!r} {got.get('landing_live')!r} {got.get('landing_view')!r}",
                  got.get("landing") == "Agents" and got.get("landing_live") == "" and got.get("landing_view") == "crew")
        ctx.check(f"3.3.2.0 R1: the rail's rows, in order, titled, no printed key, got {got.get('tabs')}",
                  [tuple(t) for t in got.get("tabs") or []] == [(t, t, 0) for t, _ in ORDER])
        ctx.check(f"the keys in the palette's Go to: Session / Alt+1 first ... Settings / Alt+6 last, got {got.get('palette_goto_keys')}",
                  [tuple(t) for t in got.get("palette_goto_keys") or []][:6] == ORDER)
        want = [[n, ORDER[n - 1][0]] for n in (2, 3, 4, 5, 6, 1)]
        ctx.check(f"Alt+2 .. Alt+6 then Alt+1 select their tabs, got {got.get('pressed')}", got.get("pressed") == want)
        ctx.check(f"Alt+1 with nothing live: the Session Start view, got {got.get('session_start')}", got.get("session_start") == 1)
        ctx.check(f"How Session works: Alt+1 Session is its first key, got {got.get('help_first_key')} {got.get('help_is_session')}",
                  got.get("help_first_key") == ["Alt 1", "Session"] and got.get("help_is_session") is True)
        hk = got.get("hint_keys") or []
        ctx.check(f"the status bar's hint: Alt+1 to Alt+6 (3.3.16.0 R2: Settings last), got {hk}", "Alt 1" in hk and "Alt 6" in hk and hk.index("Alt 1") < hk.index("Alt 6"))
        groups = got.get("palette_groups") or []
        sections = [g for g in groups if g in {t for t, _ in ORDER}]
        # 3.3.16.0 R2: Session, Agents and Local always have a group (Fleet's went with its section); Settings' group
        # is there once its catalog has loaded (settings/commands.ts reads it on the palette's first ask), so three
        # is the floor and a fourth is welcome, not awaited
        ctx.check(f"the palette: Go to, Help, then the section groups in tab order, got {groups}",
                  groups[:2] == ["Go to", "Help"] and sections == [t for t, _ in ORDER if t in sections]
                  and sections[:3] == ["Session", "Agents", "Local"])
        ctx.check(f"Go to lists the tabs in order, got {got.get('palette_goto')}", got.get("palette_goto") == [t for t, _ in ORDER])


if __name__ == "__main__":
    sys.exit(OrderDriver(sys.argv[1:]).main())
