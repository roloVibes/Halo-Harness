"""tests.test_studio_owner_tab_firefox -- "Make this tab yours" works in a REAL FIREFOX (Halo 3.6.0.6 PF, the owner's
point 31: "Owners page issues keeps happening when I try to run packs."). Firefox's plain reload looks to Studio exactly
like a link (`same-origin`, `Sec-Fetch-User: ?1`, no Cache-Control), so the server's rule, which does not change
(studio/owner_proof.py `user_navigation`), cannot take it; the button reloads bypassing the cache (`location.reload(true)`:
Firefox then sends `Cache-Control: no-cache`, which the rule takes). Driven through tests/helpers/firefox_driver.py (a
throwaway profile in a hidden display of its own, or headless; skipped without Firefox) over Studio of a scratch home
with the pack that ships with Halo (doc-review) enabled; each step prints the Fetch Metadata and Cache-Control Studio
received for the page (`heard`):

1. opened on Studio's address as a program opens it: no notice, Try it's write answers 200;
2. the glance opened the same way, then a real click on its "Open Studio" link: the notice row and the button; a write
   answers 403;
3. a real press of "Make this tab yours": the tab reloads, the notice is gone, the same write answers 200;
4. from a view-only tab, Ctrl+R leaves it view-only (this pins what Firefox does: the day it changes, this says so),
   and the notice says why: "Studio could not tell this reload from a link." (needs Xvfb and xdotool for the real key).
Run: python -m tests.test_studio_owner_tab_firefox          (the driver: ... drive)
"""
from __future__ import annotations

TIER = "full"  # a real browser: the full tier

import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
LINE = "This tab can look but not change things, because a link or a script opened it."
RELOAD = "This tab can look but not change things: Studio could not tell this reload from a link."
BUTTON = "Make this tab yours"
GLANCE_STUDIO = "document.querySelector('[data-testid=\"glance-studio\"]')"


def _got(ctx: Ctx) -> dict:
    from tests.helpers import driver_got
    from tests.helpers.firefox_driver import find_firefox
    from tests.helpers.runner import SkipTest
    if not find_firefox():
        raise SkipTest("no Firefox found (the tab is driven in a real Firefox)")
    if "r" not in _RUN:
        _RUN["r"] = driver_got.run("tests.test_studio_owner_tab_firefox", ("drive",), timeout=600)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    return info


def _heard(got: dict, key: str) -> list:
    return [h for h in got.get(key) or [] if h.get("dest") == "document"]


@test
def test_opened_by_a_program_it_is_his(ctx: Ctx):
    got = _got(ctx)
    n = got.get("opened") or {}
    ctx.check(f"no row, no VIEW ONLY, got {n}", n.get("row") is None and n.get("cell") is None)
    ctx.check(f"Try it's write answers 200, got {got.get('opened_try')}", any(w.startswith("POST crew/try 200") for w in got.get("opened_try") or []))
    h = _heard(got, "opened_heard")
    ctx.check(f"Firefox said `Sec-Fetch-Site: none`, got {h}", bool(h) and h[-1].get("site") == "none" and h[-1].get("owner") is True)


@test
def test_the_glances_open_studio_link_gives_a_tab_that_looks(ctx: Ctx):
    got = _got(ctx)
    n = got.get("glance_link") or {}
    ctx.check(f"the notice row and the button, got {n}", n.get("row") == LINE and n.get("button") == BUTTON)
    ctx.check(f"a write answers 403, got {got.get('link_try')}", any(w.startswith("POST crew/try 403") for w in got.get("link_try") or []))
    h = _heard(got, "glance_link_heard")
    ctx.check(f"a link: `same-origin`, `?1`, no Cache-Control, not the owner's page, got {h}",
              bool(h) and h[-1].get("site") == "same-origin" and h[-1].get("user") == "?1" and not h[-1].get("cache")
              and h[-1].get("owner") is False)


@test
def test_the_press_makes_the_tab_his_in_firefox(ctx: Ctx):
    got = _got(ctx)
    p = got.get("pressed") or {}
    h = _heard(got, "pressed_heard")
    ctx.check(f"the press reloaded the tab bypassing the cache (`no-cache`): the owner's page, got {h}",
              bool(h) and "no-cache" in (h[-1].get("cache") or "") and h[-1].get("owner") is True)
    ctx.check(f"after the press: no row, no VIEW ONLY, got {p}", p.get("row") is None and p.get("cell") is None)
    ctx.check(f"the same write answers 200, got {got.get('pressed_try')}", any(w.startswith("POST crew/try 200") for w in got.get("pressed_try") or []))


@test
def test_ctrl_r_leaves_a_link_opened_tab_view_only_in_firefox(ctx: Ctx):
    got = _got(ctx)
    if got.get("ctrl_r") == "headless":
        from tests.helpers.runner import SkipTest
        raise SkipTest("Ctrl+R needs a display of its own (Xvfb and xdotool)")
    n = got.get("ctrl_r") or {}
    h = _heard(got, "ctrl_r_heard")
    ctx.check(f"Firefox's Ctrl+R: `same-origin`, `?1`, no Cache-Control: not the owner's page, got {h}",
              bool(h) and h[-1].get("site") == "same-origin" and not h[-1].get("cache") and h[-1].get("owner") is False)
    ctx.check(f"so the tab still says so, as a reload Studio could not tell from a link, with the button, got {n}",
              n.get("row") == RELOAD and n.get("button") == BUTTON and n.get("cell_hover") == RELOAD)
    ctx.check(f"no page error on the way, got {got.get('page_errors')}", got.get("page_errors") == [])


# -- the driver (run as `python -m tests.test_studio_owner_tab_firefox drive`) -----------------------------------------

def _hear() -> tuple:
    """What Studio heard for each page it served (the Fetch Metadata, Cache-Control, the rule's answer): the rule itself
    is called as is (studio/owner_proof.py `user_navigation`), only watched."""
    from halo_harness.studio import owner_proof
    seen, rule = [], owner_proof.user_navigation

    def user_navigation(handler) -> bool:
        ok = rule(handler)
        h = handler.headers
        seen.append({"path": handler.path.split("?")[0], "site": h.get("Sec-Fetch-Site"), "mode": h.get("Sec-Fetch-Mode"),
                     "dest": h.get("Sec-Fetch-Dest"), "user": h.get("Sec-Fetch-User"), "cache": h.get("Cache-Control"), "owner": ok})
        return ok
    owner_proof.user_navigation = user_navigation
    return seen, lambda: setattr(owner_proof, "user_navigation", rule)


def _sent(c, heard: list, mark: int, key: str, out: dict) -> None:
    out[key + "_heard"] = heard[mark:]


def opened(c, rig, heard) -> dict:
    from tests.helpers.studio_owner_tab import FLOW, FORM, notice, try_it, writes
    mark, out = len(heard), {}
    c.go(rig.url(f"&view=workflows&workflow={FLOW}"))  # as a program opens it
    c.wait(f"document.readyState === 'complete' && !!{FORM} && !!window.__first", 60)
    out["opened"] = notice(c)
    _sent(c, heard, mark, "opened", out)
    try_it(c, "Review notes.md")
    c.wait("(window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    out["opened_try"] = writes(c, "crew/try")
    return out


def glance_link(c, rig, heard) -> dict:
    from tests.helpers.studio_owner_tab import by_link, notice, try_it, writes
    out = {}
    s = rig.server
    c.go(f"http://127.0.0.1:{s.server_address[1]}/?mode=glance&tour=off#t={s.token}")
    c.wait(f"document.readyState === 'complete' && !!{GLANCE_STUDIO}", 60)
    mark = len(heard)
    c.js("window.__before = 1; 1")
    c.click_on(GLANCE_STUDIO)
    c.wait("!window.__before && document.readyState === 'complete' && !!document.querySelector('.topbar') && !!window.__first", 60)
    out["glance_link"] = notice(c)
    _sent(c, heard, mark, "glance_link", out)
    by_link(c, rig)  # on to the pack's workflow by a link in the page: still a tab that looks
    try_it(c, "Review notes.md")
    c.wait("(window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    out["link_try"] = writes(c, "crew/try")
    return out


def press(c, rig, heard) -> dict:
    from tests.helpers.studio_owner_tab import ROW, landed, notice, try_it, writes
    mark, out = len(heard), {}
    c.js("window.__before = 1; 1")
    c.click_on(f"{ROW}.querySelector('[data-testid=\"owner-tab-yours\"]')")
    landed(c)
    out["pressed"] = notice(c)
    _sent(c, heard, mark, "pressed", out)
    try_it(c, "Review notes.md")
    c.wait("(window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    out["pressed_try"] = writes(c, "crew/try")
    return out


def ctrl_r(c, rig, heard) -> dict:
    from tests.helpers.studio_owner_tab import by_link, landed, notice
    by_link(c, rig)
    mark = len(heard)
    c.js("window.__before = 1; 1")
    if c.press_keys("ctrl+r") is None:
        return {"ctrl_r": "headless"}
    landed(c)
    out = {"ctrl_r": notice(c)}
    _sent(c, heard, mark, "ctrl_r", out)
    return out


def errors(c) -> dict:
    from tests.helpers.studio_session import page_errors
    return {"page_errors": page_errors(c)}


def _driver():
    from tests.helpers.firefox_driver import FirefoxDriver

    class OwnerTabFirefox(FirefoxDriver):
        width, height = 1500, 900

        @contextmanager
        def session(self, c):
            from tests.helpers.crew_rig import CrewRig
            from tests.helpers.studio_owner_tab import WATCH
            from tests.helpers.studio_session import collect_page_errors
            heard, unhear = _hear()
            try:
                with CrewRig() as rig:
                    rig.with_pack().studio()
                    collect_page_errors(c)
                    c.call("Page.addScriptToEvaluateOnNewDocument", source=WATCH)
                    yield ((opened, (c, rig, heard)), (glance_link, (c, rig, heard)), (press, (c, rig, heard)),
                           (ctrl_r, (c, rig, heard)), (errors, (c,)))
            finally:
                unhear()
    return OwnerTabFirefox


if __name__ == "__main__":
    if sys.argv[1:2] == ["drive"]:
        sys.exit(_driver()(sys.argv[2:]).main())
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
