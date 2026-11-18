"""tests.helpers.studio_controls_steps -- the `session` and `map` groups of tests/helpers/studio_controls.py (Halo 3.6.0.2 R42).

    session   Session's Live drawer at 1280 x 800: the pair "Running: {A} | Just built: {B}" (a builder_done for review-flow
              while the session runs on auto), Zoom out, the zoom, Zoom in, Fit (pressed after a hand zoom; fitted, it is
              hidden with its slot kept: `fit`), the T-state line's [New session] and its form's x; "↓ n more below" (the
              map `seven` at 1280 x 640); a step row, a box and a line (each opens the step-in card), the card's Pause,
              Resume, the steer field (Enter sends), Stop (up to its confirm) and the confirm's Cancel, its x, [Open in
              Agents -> Live], an off-map line's "Open the map at main"; the drawer's [Open in Agents -> Live]
    map       Agents -> 3 · Map at 1500 x 900: [Watch it in Live] (L1: the session on auto), the picker, + New map, its
              Make with a name it refuses, the error's Dismiss, the switch New sessions run on this, Undo, Run a goal,
              Lock (on, off), "n new, not connected yet" (a box added from the list to the strip) and Undo, [Open it]
              (L4: a build of review-flow), the zoom row, the four tabs, the Attention chip and its x (3.6.0.3 B: History's
              Replay and both Back to now left Studio); `gone`: the run overlay's old controls (R55) are not on the page
"""
from __future__ import annotations

import json
import time

from tests.helpers.studio_controls import VISIBLE, choose, presses

M = "document.querySelector('[data-testid=\"session-lit-map\"]')"
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"


def vis(sel: str) -> str:
    """The first VISIBLE element matching `sel` (a hidden section can hold a twin of it)."""
    return f"([...document.querySelectorAll({sel!r})].find((e) => {VISIBLE}(e)) || null)"


def seed(rig) -> None:
    """The maps Session's drawer is shown on: hops and offmap (studio_session_run), seven (studio_session_map_down_draw),
    review-flow (studio_session_just_built)."""
    from halo_harness.crew import store
    from tests.helpers.studio_session_map_down_draw import SEVEN
    from tests.helpers.studio_session_run import HOPS, OFFMAP
    from tests.helpers.studio_session_just_built import REVIEW_FLOW
    for m in (HOPS, OFFMAP, SEVEN):
        store.write_text(store.path_for("map", m["name"], state_dir=rig.state), json.dumps(m))
    store.write_text(store.path_for("map", "review-flow", state_dir=rig.state), REVIEW_FLOW)


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def session(c, rig, lv, rows) -> dict:
    from halo_harness.crew import store
    from tests.helpers.studio_session import boot_go, url
    from tests.helpers.studio_session_just_built import _frame as built_frame
    from tests.helpers.studio_session_map_down_draw import _agents
    from tests.helpers.studio_session_run import _frame, _hop, _kid, _main, _open, case2
    from tests.helpers.studio_session_step_in import _line
    a, b = lv.sid, "none"
    out: dict = {}
    down = lambda tid: vis(f".mp-down [data-testid={tid}]")  # noqa: E731
    card = lambda tid: vis(f"[data-testid=map-step-in] [data-testid={tid}]")  # noqa: E731
    pair = lambda which: vis(f"[data-testid=session-map-pair] [data-which={which}]")  # noqa: E731
    body = store.read(store.path_for("map", "review-flow", state_dir=rig.state)) or {}

    def built():
        rows.reset()
        rows.idle(a, map="auto", map_plain=True, map_next="review-flow")
        _size(c, 1280, 800)
        boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))
        c.wait(f"!!{M} && {M}.dataset.map === 'auto' && !!{M}.querySelector('[data-box=main]')", 40)
        built_frame(rig, a, [{"kind": "workflow", "name": "review", "added": True}, {"kind": "map", "name": "review-flow", "added": True}],
                    {"review-flow": body}, undo="ctl-1", next_="review-flow")
        c.wait(f"{vis('[data-testid=session-map-pair]')}?.textContent.includes('Just built: review-flow')", 20)

    def fit_box():
        out["fit_before"] = c.js(f"(() => {{ const r = {down('canvas-fit')}?.getBoundingClientRect(); return r ? [r.left, r.top, r.width, r.height] : null; }})()")

    def more():
        rows.reset()
        rows.set(a, map="seven", busy=False, status="idle", agents=_agents(rows, a))
        _size(c, 1280, 640)
        boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))
        c.wait(f"!!{M} && {M}.dataset.map === 'seven' && {M}.querySelectorAll('[data-testid=session-lit-box]').length >= 8", 40)
        time.sleep(1.0)

    blk = f"{M}?.querySelector('[data-testid=session-map-block][data-workflow=W]')"
    step3 = f"{blk}?.querySelector('[data-testid=session-map-step][data-n=\"3\"]')"
    on = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}

    def steer():
        c.click_on(card("fleet-steer"))
        c.type_text("use the fast suite")

    def hops():
        _open(c, rig, rows, a, b, "hops", False, [_main(rows, a), _kid("c1", "coder", "running", crew=on)])
        c.wait(f"!!{M}.querySelector('path[data-hit=\"main>code\"]')", 20)

    def off_line():
        w1 = _kid("w1", "coder", "running", crew={"map": "hops", "workflow": "W", "step": 1, "agent": "coder", "saved": True})
        _open(c, rig, rows, a, b, "hops", False, [_main(rows, a, current="Workflow: W"), w1])
        _hop(rig, a, "main", "workflow:W", "start", workflow="W", off=True)
        _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": ["one", "two"]})
        c.wait(f"!!{M}.querySelector('path[data-hit=\"main>workflow:W\"]')", 20)
        _line(c, "main", "workflow:W")
        c.wait(f"!!{card('map-step-in-map')}", 10)

    cancel = "([...document.querySelectorAll('[data-testid=fleet-confirm] button')].find((b) => b.textContent.trim() === 'Cancel') || null)"
    recs = presses(c, [
        ("the pair: Running", pair("running"), built), ("the pair: Just built", pair("built")),
        ("Zoom out", down("canvas-zoom-out")), ("the zoom (100%)", down("canvas-zoom-level")), ("Zoom in", down("canvas-zoom-in")),
        ("Fit", down("canvas-fit"), fit_box),
    ])
    fit = f"[...document.querySelectorAll('.mp-down [data-testid=canvas-fit]')].find((e) => {VISIBLE}(e.closest('.mp-down')))"  # hidden when fitted
    out["fit_after"] = c.js(f"(() => {{ const e = {fit}; const r = e?.getBoundingClientRect(); return e ? [getComputedStyle(e).visibility, [r.left, r.top, r.width, r.height]] : null; }})()")
    recs += presses(c, [
        ("[New session]", vis("[data-testid=session-truth-new]")), ("the New session form's x", vis("[data-testid=session-truth-form-close]")),
        ("↓ n more below", down("map-more-below"), more),
        ("a step row", step3, lambda: case2(c, rig, rows, a, b)),
        ("the card: Pause", card("map-step-in-pause")), ("the card: Resume", card("map-step-in-pause")),
        ("the card: steer field (Enter sends)", card("fleet-steer"), steer, ("key", "Enter")),
        ("the card: Stop", card("map-step-in-stop")), ("Stop's confirm: Cancel", cancel),
        ("the card: x", card("map-step-in-close")),
        ("a box", f"{M}?.querySelector('[data-box=main] .mp-name')"),
        ("the card: Open in Agents -> Live", card("map-step-in-live")),
        ("a line", f"{M}?.querySelector('path[data-hit=\"main>code\"]')", hops, lambda: _line(c, "main", "code")),
        ("an off-map line's card: Open the map at main", card("map-step-in-map"), off_line),
        ("[Open in Agents -> Live]", down("session-lit-open"), hops),
    ])
    out["session"] = recs
    return out


def map_view(c, rig, lv, rows) -> dict:
    from tests.helpers.studio_map_quiet import RF, built, setup, to_map, use
    from tests.helpers.studio_map_steps import open_list
    P = "[data-part=map]"
    t = lambda tid: vis(f"{P} [data-testid={tid}]")  # noqa: E731
    tab = lambda part, v: vis(f"[data-part={part}] [data-testid=agents-view-{v}]")  # noqa: E731
    out: dict = {}
    full, rig.full = rig.full, False  # a person's layout
    _size(c, 1500, 900)

    def l1():
        setup(rig, lv, rows, flow=False)
        to_map(c, rig, "auto")
        c.wait(f"!!{t('map-watch-live')}", 30)

    def shop():
        to_map(c, rig, "shop")

    def back_to(name: str):
        def go():
            if c.js(f"{VIEW}") != "map":
                c.js("document.activeElement?.blur(); 1")
                from tests.helpers.studio_agents import key
                key(c, "3")
                c.wait(f"{VIEW} === 'map'", 15)
            if c.js(f"{t('map-switcher')}?.value") != name:
                choose(c, t("map-switcher"), name)
            c.wait(f"{t('map-switcher')}?.value === {name!r} && !!{vis(P + ' [data-testid=map-world] [data-map-box]')}", 20)
        return go

    def bad_name():
        c.js(f"{t('map-new-name')}.focus(); 1")
        c.type_text("Bad Name")

    def fresh():
        back_to("shop")()
        open_list(c)
        row = f"([...document.querySelectorAll('{P} [data-testid=map-add-row]')].find((r) => !document.querySelector(`{P} [data-testid=map-world] [data-map-box=\"${{r.dataset.ref}}\"]`)) || null)"
        c.js(f"{row}.focus(); 1")
        c.key("Enter")
        c.wait(f"!!{t('map-fresh')}", 20)

    def l4():
        back_to("shop")()
        built(lv, "review-flow", body=RF)
        c.wait(f"!!{t('map-built-open')}", 20)

    def auto_his_shop():
        """crew.map = shop (his map set elsewhere): on auto the switch is a switch again (P4 batch 12)."""
        use(rig, "shop")
        to_map(c, rig, "auto")

    try:
        recs = presses(c, [
            ("[Watch it in Live]", t("map-watch-live"), l1),
            ("the map picker", t("map-switcher"), shop, ("choose", "auto")),
            ("+ New map", t("map-switcher"), back_to("shop"), ("choose", "+")),
            ("Make (a name it refuses)", t("map-new-make"), bad_name),
            ("the error's Dismiss", f"{t('map-error')}?.querySelector('button')"),
            ("the new map's Cancel", f"{t('map-new-make')}?.nextElementSibling"),
            ("New sessions run on this", t("map-uses"), back_to("shop")),
            ("Undo (the switch)", t("map-undo")),
            ("New sessions run on this (auto, his map shop)", t("map-uses"), auto_his_shop),
            ("Run a goal", t("map-run-goal")),
            ("Lock", t("map-lock")), ("Lock (off again)", t("map-lock")),
            ("n new, not connected yet", t("map-fresh"), fresh),
            ("Undo (the box)", t("map-undo")),
            ("[Open it]", t("map-built-open"), l4),
            ("Zoom out", t("canvas-zoom-out"), back_to("shop")), ("the zoom (100%)", t("canvas-zoom-level")), ("Zoom in", t("canvas-zoom-in")),
            ("Fit", t("canvas-fit")),
            ("the tab 1 · Agents", tab("map", "crew")), ("the tab 2 · Workflows", tab("crew", "workflows")),
            ("the tab 4 · Live", tab("workflows", "live")), ("the tab 3 · Map", tab("live", "map")),
            ("Attention", t("agents-attention")), ("Attention's x", vis("[data-testid=agents-attention-close]")),
        ])
        out["gone"] = c.js("document.querySelectorAll('[data-testid=map-lit-pick], [data-testid=map-show-running], [data-testid=map-lit-show-nomap]').length")
        # P4 batch 12: no map set, on the default map: no switch (it could change nothing), the plain sentence instead
        use(rig, None)
        to_map(c, rig, "auto")
        out["default_uses"] = [c.js(f"!!{t('map-uses')}"), c.js(f"{t('map-uses-default')}?.textContent || ''")]
        # P7: roles off and no map set, new sessions run on NO map (`next_none`): the default map says the words file's
        # sentence for that, beside a switch (off); its press puts new sessions on the default map, and the bar says so
        out["none_uses"] = none_uses(c, rig, t)
    finally:
        rig.full = full
        _roles(True)
        use(rig, None)
    out["map"] = recs
    return out


def _roles(on: bool) -> None:
    from halo_harness.roles import set_roles_enabled
    set_roles_enabled(on)


def none_uses(c, rig, t) -> dict:
    """Roles off, crew.map unset, on the default map: [switch drawn, its aria-checked, map-uses-none's words, the plain
    sentence's]; then its press: the same four once the bar has re-read the maps, and the API's `next_none`."""
    from tests.helpers.studio_map_quiet import to_map
    from tests.helpers.studio_run_parts import until
    read = (f"[!!{t('map-uses')}, {t('map-uses')}?.getAttribute('aria-checked') || '', {t('map-uses-none')}?.textContent || '', "
            f"{t('map-uses-default')}?.textContent || '']")
    _roles(False)
    out = {"api": rig.api("GET", "crew/maps")[1].get("next_none")}
    to_map(c, rig, "auto")
    out["off"] = c.js(read)
    # P8 batch 2: the space between the switch (its label: the button and its words) and the 'no map' sentence (with
    # roles off the words ran into the sentence, 0 px)
    out["gap"] = c.js(f"(() => {{ const s = {t('map-uses')}?.closest('label'), w = {t('map-uses-none')}; if (!s || !w) return null; "
                      "return Math.round(w.getBoundingClientRect().left - s.getBoundingClientRect().right); })()")
    if out["off"][0]:
        c.js(f"{t('map-uses')}.click(); 1")
        out["pressed"] = until(c, read, [False, "", "", "New sessions run on Auto (the default)."], 20)
        out["api_after"] = rig.api("GET", "crew/maps")[1].get("next_none")
    return out
