"""tests.helpers.studio_doors -- "a door never leads nowhere" (Halo 3.6.0.2 P4 batch 9), in headless Chrome as a person
uses it, over tests/helpers/studio_session_rig.py (this harness's real session) and tests/helpers/studio_live_rig.py
(the session runs on the map `shop`; the reviewer is the workflow review's step, drawn in the box `check`). No model.

    ask_map      a COLD page loaded straight onto Agents -> 3 · Map (no other section shown in its life); the reviewer
                 waits on him (its row `waiting`, its ask in the Feed); Attention -> the row's O, pressed ONCE: within 5 s Agents -> 4 · Live shows
                 the session with the box `check` selected (`data-selected`) and waiting (`data-state=waiting`), its card
                 open with the ask's choices; "Open changed nothing" when the section, the view, the drawer and the
                 selection are all as they were
    ask_session  Session, its Attention drawer: the same row's O lands on Session's Live drawer, `check` selected and
                 waiting, the card with the ask's choices
    ask_stranger an agent the drawing puts on no box asks: O from Agents and from Session opens the Feed on it with the
                 ask's choices and the line "{agent} is not on the map: its question is in the Feed." (P4 batch 12)
    ask_held     the same with the ask's frame held back until after the press (P9 batch 2): the row and its choices are
                 in the Feed when the line shows, timed in the page from the press; the late frame draws no second row
    run_open     a live goal run, the run's file read held by the browser (never answered): the Map's top line's Open is
                 the same DOM node before and after the Map settled (one parent whatever the line says), and one press
                 opens the Map's drawer on the run at once
    builder_left the builder box on 3 · Map: Apply's answer names a switch of new sessions it LEFT OUT (the engine's
                 words, map_facts.USE_LEFT); the box shows that line under its result (the two answers are the
                 browser's stand-ins for the server's: this step runs last, its stand-in stays for the page's life)

    python -m tests.helpers.studio_doors
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
SECTION = "(document.querySelector('.section-view:not([hidden])')?.dataset.section || '')"
CARD_LIVE = "document.querySelector('[data-part=live] [data-testid=map-step-in]')"
BOX_LIVE = "document.querySelector('[data-part=live] [data-box=check]')"
SESSION = "document.querySelector('.section-view[data-section=session]')"
SHOWN = "(sel) => [...document.querySelectorAll(sel)].find((e) => e.offsetParent)"


def vis(sel: str) -> str:
    return f"({SHOWN})({json.dumps(sel)})"


def asked(lv) -> None:
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-door", "name": "Bash", "input": {"command": "git push origin feature/basket"}})


def landed(box: str, card: str) -> str:
    return (f"(() => {{ const b = {box}, c = {card}; return !!b && b.hasAttribute('data-selected') && !!c && "
            f"[b.dataset.state, c.querySelectorAll('[data-testid=map-step-in-ask] [data-testid=map-step-in-ask-key]').length, "
            f"c.querySelector('[data-testid=map-step-in-title]')?.textContent || '']; }})()")


def ask_map(c, rig, lv) -> dict:
    out: dict = {}
    c.go(rig.url("agents", "&view=map"))
    c.wait(f"{VIEW} === 'map'", 40)
    asked(lv)
    chip = vis("[data-testid=agents-attention]")
    c.wait(f"Number({chip}?.dataset.count) > 0", 30)
    c.click_on(chip)
    row = "document.querySelector('[data-testid=fleet-attention] [data-testid=fleet-attn-row][data-kind=waiting]')"
    out["ask_map_keys"] = c.wait(f"{row} && [...{row}.querySelectorAll('[data-testid=fleet-attn-key]')].map((k) => k.dataset.key)", 30)
    before = f"[{SECTION}, {VIEW}, !!document.querySelector('[data-part=live] .stage-drawer'), !!document.querySelector('[data-selected]')]"
    was = c.js(before)
    c.click_on(f"{row}.querySelector('[data-testid=fleet-attn-key][data-key=o]')")
    try:
        out["ask_map"] = c.wait(f"{VIEW} === 'live' && {landed(BOX_LIVE, CARD_LIVE)}", 5)
        out["ask_map_state"] = c.wait(f"{BOX_LIVE}?.dataset.state === 'waiting' && 'waiting'", 20)  # the waiting mark (P3)
    except TimeoutError:
        now = c.js(before)
        out["ask_map"] = "Open changed nothing" if now == was else f"landed elsewhere: {now} (was {was})"
    out["ask_map_attention_closed"] = c.js("!document.querySelector('[data-testid=fleet-attention]')")
    return out


def ask_session(c, rig, lv) -> dict:
    out: dict = {}
    c.go(rig.url("session"))
    c.wait(f"!!{SESSION} && !{SESSION}.hidden", 40)
    btn = "document.querySelector('[data-testid=viewbar-btn][data-panel=session-attention]')"
    c.wait(f"!!{btn}", 30)
    c.click_on(btn)
    row = "document.querySelector('[data-panel=session-attention] [data-testid=fleet-attn-row][data-kind=waiting]')"
    c.wait(f"!!{row}", 30)
    c.click_on(f"{row}.querySelector('[data-testid=fleet-attn-key][data-key=o]')")
    # Session's Live drawer (its view-bar button pressed), the box and the card in it
    box = "document.querySelector('.section-view[data-section=session] [data-testid=session-lit-box][data-box=check]')"
    card = "document.querySelector('.section-view[data-section=session] [data-testid=session-lit-box]')?.closest('.mp-down')?.querySelector('[data-testid=map-step-in]')"
    out["ask_session_live_btn"] = None
    try:
        out["ask_session"] = c.wait(landed(box, card), 8)
        out["ask_session_state"] = c.wait(f"{box}?.dataset.state === 'waiting' && 'waiting'", 20)
        out["ask_session_live_btn"] = c.js("document.querySelector('[data-testid=viewbar-btn][data-panel=session-map]')?.getAttribute('aria-pressed')")
    except TimeoutError:
        out["ask_session"] = (f"not on the drawing: drawers {c.js('[...document.querySelectorAll(`.stage-drawer`)].map((d) => d.dataset.panelIn)')}, "
                              f"box {c.js(f'!!{box}')}, toasts {c.js('[...document.querySelectorAll(`.toast`)].map((t) => t.textContent)')}, "
                              f"section {c.js(SECTION)}, in session {c.js('[...document.querySelectorAll(`.section-view[data-section=session] [data-panel-in]`)].map((d) => d.className.split(` `)[0] + `:` + d.dataset.panelIn)')}, "
                              f"live btn {c.js('document.querySelector(`[data-testid=viewbar-btn][data-panel=session-map]`)?.getAttribute(`aria-pressed`)')}, "
                              f"lit boxes {c.js('[...document.querySelectorAll(`[data-testid=session-lit-box]`)].map((b) => b.dataset.box)')}")
    return out


def ask_stranger(c, rig, lv) -> dict:
    """P4 batch 12 (the owner's point 24): an ask from an agent the drawing puts on NO box (its row names the box `gone`, not
    on shop): O from Agents and from Session opens the Feed on that agent with the ask's choices in view and one line
    saying so; nothing else closes (Session's Attention drawer stays)."""
    out: dict = {}
    line = "scout is not on the map: its question is in the Feed."
    toast = "[...document.querySelectorAll('.toast')].map((t) => t.textContent).join(' | ')"
    keys = f"({SHOWN})('[data-testid=session-live-ask] [data-testid=session-live-key]')"
    row = "(sel) => [...document.querySelectorAll(sel)].find((r) => r.textContent.includes('scout'))"
    for where in ("agents", "session"):
        if where == "agents":
            c.go(rig.url("agents", "&view=map"))
            c.wait(f"{VIEW} === 'map'", 40)
            # it asks while the page is open (its words reach the Feed as they are said)
            lv.spawn("s0c0u7t0", "scout", "scout", "or:mock/qwen3-coder", "Scout: look around the basket code")
            lv.rows["s0c0u7t0"]["crew"] = {"box": "gone"}
            lv.state("scout", state="waiting")
            lv.ask("scout", "permission_request", {"id": "perm-off", "name": "Bash", "input": {"command": "ls"}})
            chip = vis("[data-testid=agents-attention]")
            c.wait(f"Number({chip}?.dataset.count) > 0", 30)
            c.click_on(chip)
            r = f"({row})('[data-testid=fleet-attention] [data-testid=fleet-attn-row]')"
        else:
            c.go(rig.url("session"))
            c.wait(f"!!{SESSION} && !{SESSION}.hidden", 40)
            lv.ask("scout", "permission_request", {"id": "perm-off-2", "name": "Bash", "input": {"command": "pwd"}})  # asked again, the page open
            btn = "document.querySelector('[data-testid=viewbar-btn][data-panel=session-attention]')"
            c.wait(f"!!{btn}", 30)
            c.click_on(btn)
            r = f"({row})('[data-panel=session-attention] [data-testid=fleet-attn-row]')"
        c.wait(f"!!{r}", 30)
        c.click_on(f"{r}.querySelector('[data-testid=fleet-attn-key][data-key=o]')")
        try:  # the line, while it is shown (a toast lasts 8 s); then the row it names (waited for, never slept on)
            seen = c.wait(f"({toast}).includes({json.dumps(line)}) && ({toast})", 8)
        except TimeoutError:
            seen = c.js(toast) or ""
        try:
            c.wait(f"!!{keys}", 10)
            if line not in seen:
                raise TimeoutError("no line")
            out[f"stranger_{where}"] = [c.js(f"{keys}.closest('[data-testid=session-live-ask]') ? 'feed' : ''"), seen]
        except TimeoutError:
            out[f"stranger_{where}"] = [f"no Feed ask in view: keys {c.js(f'!!{keys}')}, view {c.js(VIEW)}, card "
                                        f"{c.js(CARD_LIVE + '?.textContent?.slice(0, 80) || null')}, selected "
                                        f"{c.js('document.querySelector(`[data-selected]`)?.dataset.box || null')}, feed panel "
                                        f"{c.js('document.querySelector(`[data-testid=viewbar-btn][data-panel=live-feed]`)?.getAttribute(`aria-pressed`) || null')}, feed "
                                        f"{c.js('[...document.querySelectorAll(`[data-testid=map-feed]`)].map((e) => [e.dataset.filter, !!e.offsetParent, e.querySelectorAll(`[data-testid=session-live-ask]`).length])')}", seen]
        if where == "session":
            out["stranger_session_attention"] = c.js(f"!!({SHOWN})('[data-panel=session-attention] [data-testid=fleet-attn-row]')")
        else:
            out["stranger_agents_view"] = c.js(VIEW)
    out["stranger_line"] = line
    return out


HELD_WATCH = """(() => { const w = window.__held = { t0: null, row: null, line: null, atLine: null };
  const asks = () => [...document.querySelectorAll('[data-testid=map-feed] [data-testid=session-live-ask]')]
    .filter((e) => e.offsetParent && e.querySelector('[data-testid=session-live-key]')).length;
  const said = () => [...document.querySelectorAll('.toast')].some((t) => t.textContent.includes(LINE));
  const look = () => { if (w.t0 === null) return; const n = asks(), ms = Math.round(performance.now() - w.t0);
    if (w.row === null && n) w.row = ms;
    if (w.line === null && said()) { w.line = ms; w.atLine = n; } };
  document.addEventListener('click', () => { if (w.t0 === null) w.t0 = performance.now(); }, true);
  new MutationObserver(look).observe(document.body, { childList: true, subtree: true, characterData: true });
  return 1; })()"""


def ask_held(c, rig, lv) -> dict:
    """P9 batch 2 (CI on the candidate: the line said the question is in the Feed while the Feed held no row): an agent the
    drawing puts on no box waits on him and NO frame of its ask has reached the page (held back until after the press).
    O from Agents: the Feed on that agent shows the ask's row with its choices -- at the moment the line says so, timed in
    the page from the press -- and the frame that brings the ask later fills that row (no second row)."""
    out: dict = {}
    line = "lookout is not on the map: its question is in the Feed."
    c.go(rig.url("agents", "&view=map"))
    c.wait(f"{VIEW} === 'map'", 40)
    lv.spawn("l0o0k0u7", "lookout", "lookout", "or:mock/qwen3-coder", "Lookout: watch the basket code")
    lv.rows["l0o0k0u7"]["crew"] = {"box": "gone"}
    lv.state("lookout", state="waiting")  # it waits on him; its ask's frame is held back
    chip = vis("[data-testid=agents-attention]")
    c.wait(f"Number({chip}?.dataset.count) > 0", 30)
    c.click_on(chip)
    r = "[...document.querySelectorAll('[data-testid=fleet-attention] [data-testid=fleet-attn-row]')].find((e) => e.textContent.includes('lookout'))"
    c.wait(f"!!{r}", 30)
    c.js(HELD_WATCH.replace("LINE", json.dumps(line)))
    c.click_on(f"{r}.querySelector('[data-testid=fleet-attn-key][data-key=o]')")
    try:
        c.wait("window.__held.row !== null && window.__held.line !== null", 15)
    except TimeoutError:
        pass
    out["held"] = c.js("[window.__held.row, window.__held.line, window.__held.atLine]")
    rows = "[...document.querySelectorAll('[data-testid=map-feed] [data-testid=session-live-ask]')].filter((e) => e.offsetParent)"
    out["held_texts"] = c.js(f"{rows}.map((e) => e.querySelector('.slv-ask-what')?.textContent || '')")
    lv.ask("lookout", "permission_request", {"id": "perm-held", "name": "Bash", "input": {"command": "ls"}})  # the held frame comes
    try:
        c.wait(f"{rows}.some((e) => e.textContent.includes('asks to run: ls'))", 20)
    except TimeoutError:
        pass
    out["held_after"] = c.js(f"{rows}.map((e) => e.querySelector('.slv-ask-what')?.textContent || '')")
    out["held_line"] = line
    return out


def run_open(c, rig, lv) -> dict:
    from tests.helpers.studio_session_links import live_run
    out: dict = {}
    run = live_run(rig).name
    c.call("Fetch.enable", patterns=[{"urlPattern": "*/file?*"}])  # the run's file read: held, never answered
    try:
        c.go(rig.url("agents", "&view=map"))
        opener = "document.querySelector('[data-part=map] [data-testid=map-lit-run-open]')"
        c.wait(f"!!{opener}", 30)
        c.js(f"window.__open1 = {opener}; 1")
        c.wait("!!document.querySelector('[data-part=map] [data-testid=map][data-settled]')", 30)
        out["run_same_node"] = c.js(f"window.__open1 === {opener} && window.__open1.isConnected")
        c.click_on(opener)
        drawer = "document.querySelector('[data-part=map] [data-testid=map-drawer]')"
        t0 = time.time()
        try:
            out["run_open"] = c.wait(f"{drawer}?.offsetParent && {drawer}.dataset.page === 'run:{run}' && {drawer}.dataset.page", 3)
        except TimeoutError:
            out["run_open"] = f"closed after 3 s ({c.js(f'{drawer}?.dataset.page || null')})"
        out["run_open_s"] = round(time.time() - t0, 2)
        out["run_id"] = f"run:{run}"
    finally:
        c.call("Fetch.disable")
    return out


STAND_IN = """(() => { const real = window.fetch.bind(window);
  window.fetch = (u, init) => { const p = new URL(String(u && u.url || u), location.href).pathname;
    const json = (o) => Promise.resolve(new Response(JSON.stringify(o), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    if (p.endsWith('/api/builder/ask')) return json({ reply: 'One change: new sessions run on review-flow.', cost_usd: 0, meta: null,
      changes: [{ id: 'c1', kind: 'change', target: 'config:crew.map', summary: 'New sessions run on review-flow', widen: false, ticked: true }] });
    if (p.endsWith('/api/builder/apply')) return json({ undo_id: '', wrote: [], removed: [], skipped: [], filled: [], left: [LEFT] });
    return real(u, init); }; })();"""


def builder_left(c, rig, lv) -> dict:
    from halo_harness.crew.map_facts import USE_LEFT
    out: dict = {}
    left = USE_LEFT.format(B="review-flow", F4="starter (the default)")
    out["left_sent"] = left
    c.call("Page.enable")
    c.call("Page.addScriptToEvaluateOnNewDocument", source=STAND_IN.replace("LEFT", json.dumps(left)))
    c.go("about:blank")  # a new document (the same URL again would be a fragment change: no script run)
    c.go(rig.url("agents", "&view=map"))
    box = vis("[data-part=map] [data-testid=builder-input]")
    c.wait(f"!!{box}", 30)
    c.js(f"(() => {{ const i = {box}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
         f" set.call(i, 'new sessions on review-flow'); i.dispatchEvent(new Event('input', {{bubbles: true}})); }})(); 1")
    c.click_on(vis("[data-part=map] [data-testid=builder-send]"))
    msgs = "[...document.querySelectorAll('[data-part=map] [data-testid=builder-msg]')]"
    try:
        c.wait(f"!!{vis('[data-part=map] [data-testid=builder-apply]')}", 20)
    except TimeoutError:
        raise TimeoutError(f"no Apply: the box says {c.js(msgs + '.map((m) => m.textContent)')}")
    c.click_on(vis("[data-part=map] [data-testid=builder-apply]"))
    c.wait(f"{msgs}.some((m) => /wrote|Nothing to write/.test(m.textContent))", 20)
    out["builder_left"] = c.js(f"[...document.querySelectorAll('[data-part=map] [data-testid=builder-left]')].map((e) => e.textContent)")
    out["builder_result"] = c.js(f"{msgs}.map((m) => m.querySelector('.cw-msg-text')?.textContent || '').pop()")
    return out


class DoorsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_map_live import MAP
        with StudioSessionRig() as rig:
            from halo_harness.crew import store
            store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)
            lv = Live(rig)
            lv.rows["r3v1e2w0"]["square"] = {"name": "review", "engine": "steps"}  # the workflow review's step: box check
            lv.refresh(map="shop", map_next="shop")
            try:
                yield tuple((fn, (c, rig, lv)) for fn in (ask_map, ask_session, ask_stranger, run_open, ask_held, builder_left))
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(DoorsDriver(sys.argv[1:]).main())
