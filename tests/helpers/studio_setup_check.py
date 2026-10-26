"""tests.helpers.studio_setup_check -- the fresh-home landing, the Check block
and the Linux fixes block steps of the Setup driver (tests/helpers/studio_setup.py,
Halo 3.3.0.0 R3), real clicks in headless Chrome over the driver's scratch
home; no network, no model call (the five checks are stubs, the Linux fixes
are stubs: nothing downloaded, no rc file written):

FIRST (no provider set up yet, the home fresh for the moment):
1. `?mode=roles` still wins; the Start here overlay's first button reads
   "Set up this box"; its Run answers 422 `no_provider`: Setup opens, the
   overlay closes, a toast says so, the strip says "no provider set";
2. no `?mode=`, Roles saved for this browser: the page opens on Setup (the
   served page says `data-no-provider`) with no overlay over it (3.3.1.0 R1);
   on Roles (Alt+3) the overlay shows, and "Set up this box" closes it on Setup.
LAST (after the other blocks):
3. the Check block: five rows, doctor / catalog / hello ticked; ticking the
   gym lists its models; the guided first run's box is off until its card
   is shown; Run the ticked checks fills each row's log and glyph, the
   summary, the strip's Last check and last-check.json;
4. the Linux fixes block (a box stubbed as missing both): the two items,
   Apply runs both stubs, the lines say so.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from tests.helpers.studio_packs_steps import CUR, alt, q, qa
from tests.helpers.studio_setup_pages import goto

ROW = "[data-testid=setup-check-row]"
RESULTS = {"doctor": (True, ["doctor stub: config ok"]), "catalog": (True, ["[ok] openrouter: 2 models (stub)"]),
           "hello": (False, ["no pong (stub)"]), "gym": (True, ["or:mock/beta: not run (stub)"])}


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def click(c, sel: str, done: str) -> str:
    """A pointer click on `sel`, waiting for `done`; the element's own click when the pointer missed."""
    c.wait(f"!!{q(sel)}", 20)
    c.js(f"{q(sel)}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(q(sel))
    try:
        c.wait(done, 5)
        return "pointer"
    except TimeoutError:
        c.js(f"{q(sel)}?.click(); 1")
        c.wait(done, 15)
        return "element"


@contextmanager
def stubs():
    """The five checks' runs swapped for stubs (they run in this process's Studio thread)."""
    from halo_harness.start import checks as C
    saved = {c["key"]: c["run"] for c in C.CHECKS}

    def make(key):
        def run(_ctx):
            ok, lines = RESULTS[key]
            if not ok:
                raise C.CheckFailed(lines)
            return lines
        return run
    for c in C.CHECKS:
        if c["key"] in RESULTS:
            c["run"] = make(c["key"])
    try:
        yield
    finally:
        for c in C.CHECKS:
            c["run"] = saved[c["key"]]


def _fresh(on: bool) -> None:
    from halo_harness.theme import set_config_value, unset_config_value
    if on:
        unset_config_value("team")
        unset_config_value("roles")
    else:
        set_config_value("team", "halo-dev-cycle")
        set_config_value("roles.enabled", True)


def no_provider_jump(c, url, ctx) -> dict:
    _fresh(True)
    try:
        c.go(url.replace("tour=off&", ""))  # ?mode=roles, the overlay on
        c.wait(f"{CUR}.startsWith('Roles') && !!{q('[data-testid=start-here-run]')}", 40)
        out = {"jump_first_button": c.js(f"{q('[data-testid=start-here] .os-buttons .btn')}.textContent.trim()")}
        out["jump_by"] = click(c, "[data-testid=start-here-run]", f"{CUR}.startsWith('Setup') && !{q('[data-testid=start-here]')}")
        out["jump_section"] = c.js(CUR)
        out["jump_toast"] = c.wait(f"[...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => t.includes('no provider')) || ''", 10)
        out["jump_strip"] = c.wait(f"{_text('[data-testid=setup-strip-cell][data-key=provider] .su-cell-value')}", 20)
        return out
    finally:
        _fresh(False)


def landing(c, url, ctx) -> dict:
    _fresh(True)
    try:
        c.go(url)
        c.wait(f"{CUR}.startsWith('Roles')", 40)
        c.js("localStorage.setItem('halo.studio.section', 'roles'); 1")
        c.go(url.replace("mode=roles&tour=off&", ""))
        out = {"land_section": c.wait(f"{CUR}.startsWith('Setup') && {CUR}", 40),
               "land_boot": c.js("document.documentElement.dataset.noProvider || ''")}
        c.wait(f"!!{q('[data-testid=setup-rail-step]')}", 30)
        time.sleep(2.0)
        out["land_overlay_on_setup"] = c.js(f"!!{q('[data-testid=start-here]')}")
        alt(c, 3)  # the overlay is for the other sections of a fresh home
        out["land_first_button"] = c.wait(f"{CUR}.startsWith('Roles') && {q('[data-testid=start-here] .os-buttons .btn')}?.textContent.trim()", 30)
        out["land_by"] = click(c, "[data-testid=start-here-setup]", f"!{q('[data-testid=start-here]')}")
        out["land_after"] = c.js(CUR)
        return out
    finally:
        _fresh(False)


def _row(key: str, inner: str = "") -> str:
    return f"{ROW}[data-key={key}] {inner}".strip()


def check_block(c, url, ctx) -> dict:
    c.go(url.replace("mode=roles", "mode=setup"))
    goto(c, "check")
    c.wait(f"{qa(ROW)}.length === 5", 40)
    ticks = f"{qa('[data-testid=setup-check-tick]')}.map((t) => t.checked)"
    out = {"check_rows": c.js(f"{qa(ROW)}.map((r) => r.dataset.key)"), "check_ticks": c.js(ticks),
           "check_start_locked": c.js(f"{q(_row('start', '[data-testid=setup-check-tick]'))}.disabled"),
           "check_detail": c.js(_text(_row("hello", ".su-check-detail")))}
    gym = _row("gym", "[data-testid=setup-check-tick]")
    out["gym_by"] = click(c, gym, f"!!{q('[data-testid=setup-check-gym-models]')} || !!{q('[data-testid=setup-check-gym-none]')}")
    out["gym_models"] = c.js(f"{qa('[data-testid=setup-check-gym-model]')}.map((m) => m.dataset.ref)")
    out["card_by"] = click(c, "[data-testid=setup-check-show-card]", f"!!{q('[data-testid=setup-check-card]')}")
    out["card_first"] = c.js(f"{_text('[data-testid=setup-check-card]')}.split('\\n')[0]")
    out["start_unlocked"] = c.js(f"!{q(_row('start', '[data-testid=setup-check-tick]'))}.disabled")
    summary = _text("[data-testid=setup-check-summary]")
    out["run_by"] = click(c, "[data-testid=setup-check-run]", f"{summary}.includes('failed')")
    out["summary"] = c.js(summary)
    out["glyphs"] = c.js(f"{qa('[data-testid=setup-check-glyph]')}.map((g) => g.textContent)")
    out["logs"] = c.js(f"{qa('[data-testid=setup-check-log]')}.map((l) => [l.dataset.key, l.textContent])")
    cell = _text("[data-testid=setup-strip-cell][data-key=check] .su-cell-value")
    out["strip_check"] = c.wait(f"{cell}.includes('failed') && {cell}", 20)
    out["rail_check"] = c.js(f"{q('[data-testid=setup-rail-step][data-step=check]')}?.dataset.word || ''")
    p = ctx["state"] / "studio" / "last-check.json"
    out["last_check_file"] = p.is_file()
    return out


def linux_block(c, url, ctx) -> dict:
    from pathlib import Path

    from halo_harness import linux_fixes as LF
    from halo_harness.studio import setup_check_state as S
    calls: list = []
    saved = (S.platform_name, S.rg_on_path, LF.install_static_ripgrep, LF.ensure_local_bin_on_rc, LF.local_bin_on_noninteractive_path)
    out = {"linux_before": c.js(_text("[data-testid=setup-linux-none]"))}
    try:
        S.platform_name, S.rg_on_path = (lambda: "linux"), (lambda: ("rg", "") in calls)
        LF.local_bin_on_noninteractive_path = lambda **_k: ("rc", "") in calls
        LF.install_static_ripgrep = lambda dest, **_k: calls.append(("rg", "")) or (True, str(dest / "rg"))
        LF.ensure_local_bin_on_rc = lambda **_k: calls.append(("rc", "")) or (True, Path("~/.profile"))
        S.forget_linux()
        # 3.3.1.0 R1: the page is already at this address (check_block), and Chrome treats the same address with a
        # `#t=` fragment as a fragment hop, not a load -- the state read before the stubs would stay (a box that
        # needs no fixes for real, like the Linux runner, never showed the step); a blank hop first makes it a load
        c.go("about:blank")
        c.go(url.replace("mode=roles", "mode=setup"))
        try:
            goto(c, "linux")  # 3.3.1.0 R1: a step only while this box needs the fixes
            c.wait(f"{qa('[data-testid=setup-linux-item]')}.length === 2", 40)
        except TimeoutError as e:
            # GitHub's Windows runner timed out here (f408d5c): record what the server and the page say, and let the
            # other steps run -- the test that reads linux_items fails alone, with these numbers in its line
            out["linux_timeout"] = {"error": str(e)[:160], "server_block": S.linux_block(),
                                    "none_text": c.js(_text("[data-testid=setup-linux-none]")),
                                    "items_now": c.js(f"{qa('[data-testid=setup-linux-item]')}.length"),
                                    "strip": c.js(_text("[data-testid=setup-strip]")),
                                    "body": c.js("document.body.innerText.slice(0, 300)")}
            return out
        out["linux_items"] = c.js(f"{qa('[data-testid=setup-linux-item]')}.map((i) => i.dataset.id)")
        out["linux_rail"] = c.js(f"{q('[data-testid=setup-rail-step][data-step=linux]')}?.dataset.word || ''")
        lines = "[data-testid=setup-card-lines][data-card=linux]"
        out["linux_by"] = click(c, "[data-testid=setup-linux-apply]", f"!!{q(lines)}")
        out["linux_lines"] = c.js(_text(lines))
        out["linux_after"] = c.wait(f"{_text('[data-testid=setup-linux-none]')}", 15)
        out["linux_calls"] = [k for k, _ in calls]
    finally:
        S.platform_name, S.rg_on_path, LF.install_static_ripgrep, LF.ensure_local_bin_on_rc, LF.local_bin_on_noninteractive_path = saved
        S.forget_linux()
    return out


FIRST = (no_provider_jump, landing)
LAST = (check_block, linux_block)
