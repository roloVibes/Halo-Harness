"""tests.helpers.studio_packs_steps -- the DOM helpers of tests/helpers/studio_packs.py
and its live steps (Halo 3.2.0.0 R3): a pack's event lines in Fleet's Activity,
Session's Live column and its Reviews panel (one declared kind, one generic);
the attention row with the pack's label and keys, answered with A; the pack
disabled and everything of it gone without a reload."""
from __future__ import annotations

import json
import time
from pathlib import Path


TABS = "[...document.querySelectorAll('[data-testid=section-tab]')]"
CUR = "(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '')"


def q(sel: str) -> str:
    return f"document.querySelector({json.dumps(sel)})"


def qa(sel: str) -> str:
    return f"[...document.querySelectorAll({json.dumps(sel)})]"


def pa(pid: str, inner: str) -> str:
    return qa(f'[data-panel="{pid}"] {inner}')


def panel(pid: str, inner: str = "") -> str:
    return q(f'[data-panel="{pid}"] {inner}'.strip())


def mod_key(c, code: str, vk: int, mods: int, key: str) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)


def alt(c, n: int) -> None:
    d = n % 10  # 3.3.5.0 R1: the tenth slot (Local) is Digit0
    mod_key(c, f"Digit{d}", 48 + d, 1, str(d))


def open_tab(c, title: str) -> str:
    """3.3.3.0 R2: open a section by its rail row (a pack's own section has no Alt key: Alt+9 is Settings); the row's
    own click when the pointer missed. Returns the section now current."""
    tab = f"{TABS}.find((t) => t.textContent.startsWith({json.dumps(title)}))"
    c.wait(f"!!{tab}", 15)
    c.click_on(tab)
    try:
        return c.wait(f"{CUR}.startsWith({json.dumps(title)}) && {CUR}", 5)
    except TimeoutError:  # the pointer missed (a Linux runner): click the row itself
        c.js(f"{tab}.click(); 1")
        return c.wait(f"{CUR}.startsWith({json.dumps(title)}) && {CUR}", 10)


def press(c, expr: str) -> None:
    # 3.3.13.0 R2: a control the page holds disabled (the Pack Manager's busy flag lasts until its own reload after the
    # pack_changed frame already redrew the row) drops a press: wait until it takes one
    c.wait(f"!!({expr}) && !({expr}).disabled", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.25)
    c.click_on(expr)


def publish(ctx, kind: str, data) -> None:
    from halo_harness.ext import publish_event
    from halo_harness.studio.events import bridge_for
    assert publish_event("doc-review", kind, data, bridge=bridge_for(ctx["srv"]))


def agents_live(c) -> None:
    """Alt+2, then Agents' Live view (3.3.16.0 R2: the Fleet section folded in)."""
    alt(c, 2)
    c.wait(f"{CUR}.startsWith('Agents')", 20)
    c.click_on(q("[data-testid=agents-view-live]"))
    c.wait("document.querySelector('[data-testid=agents]')?.dataset.view === 'live'", 10)


def fleet_queue(c) -> None:
    """Agents' Attention queue open (the chip; closed on load)."""
    if not c.js(f"{CUR}.startsWith('Agents')"):
        agents_live(c)
    if not c.js(f"!!{q('[data-panel=fleet-attention]')}"):
        c.click_on(q("[data-testid=agents-attention]"))
    c.wait(f"!!{q('[data-panel=fleet-attention]')}", 10)


def events(c, url, ctx) -> dict:
    from tests.helpers.studio_header_menus import plus
    out: dict = {}
    agents_live(c)  # 3.3.16.0 R2: Activity is Live's optional panel (the "+")
    if c.js(f"!!{q('[data-testid=agents-attention-close]')}"):  # the queue from the step before covers the page
        c.click_on(q("[data-testid=agents-attention-close]"))
    if not c.js(f"!!{q('[data-testid=fleet-log]')}"):
        plus(c, "fleet-activity")
    strip = q(".ws-cell[data-panel=fleet-activity] .panel-bar button[aria-label=Open]")
    if c.js(f"!{q('[data-testid=fleet-log]')} && !!{strip}"):  # added as a strip: one click opens it
        c.click_on(strip)
    c.wait(f"!!{q('[data-testid=fleet-log]')}", 20)
    log = qa("[data-testid=fleet-log-line][data-kind=pack]")
    seen = c.js(f"{log}.length")  # 3.3.10.0 R3: the bundle step's own hello.said line came first
    publish(ctx, "review.done", {"file": "README.md", "findings": 3})
    publish(ctx, "review.started", {"file": "docs/A.md"})
    c.wait(f"{log}.length >= {seen + 2}", 15)
    out["activity"] = c.js(f"{log}.slice({seen}).map((l) => l.querySelector('.fac-text').textContent)")
    alt(c, 1)
    live = qa("[data-testid=session-live-line][data-kind=pack]") + ".filter((l) => !l.textContent.includes('HELLO'))"  # not R3's bundle line
    c.wait(f"{live}.length >= 2", 15)
    out["live"] = c.js(f"{live}.map((l) => [l.querySelector('[data-testid=session-live-kind]').textContent, l.querySelector('[data-testid=session-live-pack]').textContent])")
    press(c, panel("doc-review--reviews", "button[aria-label=Open]"))
    lines = qa("[data-panel='doc-review--reviews'] [data-testid=pack-event-line]")
    c.wait(f"{lines}.length >= 2", 10)
    out["panel_lines"] = c.js(f"{lines}.map((l) => [l.querySelector('.fac-kind').textContent, l.querySelector('.fac-text').textContent])")
    return out


#: 3.2.1.0 R1: on every new document, the visible section ids in the order they show, and whether the
#: "loading the pack's section" frame showed (installed before the page's own script runs)
FIRST_PAINT = """(() => { window.__sections = []; window.__sawLoading = false;
  const look = () => { const v = document.querySelector('.section-view:not([hidden])'); const id = v && v.dataset.section;
    if (id && window.__sections[window.__sections.length - 1] !== id) window.__sections.push(id);
    if (document.querySelector('[data-testid=pack-section-loading]')) window.__sawLoading = true; };
  new MutationObserver(look).observe(document, {subtree: true, childList: true, attributes: true, attributeFilter: ['hidden']}); })();"""


def first_paint(c, url, ctx) -> dict:
    """3.2.1.0 R1: on Docs review (saved for this browser), a reload with no ?mode= paints Docs review first: the
    first visible section is the pack's (its frame says it is loading), never the core section it fell back to."""
    out: dict = {}
    open_tab(c, "Docs review")  # 3.3.3.0 R2: by its rail row (Alt+9 is Settings)
    out["saved_section"] = c.js("localStorage.getItem('halo.studio.section')")
    c.call("Page.enable")  # the new-document script runs only with the Page domain on (off again below)
    script = c.call("Page.addScriptToEvaluateOnNewDocument", source=FIRST_PAINT).get("identifier")
    from halo_harness.theme import set_config_value, unset_config_value
    set_config_value("model", "ol:first-paint:1b")  # 3.3.0.0 R3: a home with no provider opens on Setup, whatever was saved
    try:
        c.go("about:blank")
        c.wait("location.href === 'about:blank'", 10)
        c.go(url.replace("mode=roles&", ""))
        c.wait(f"{CUR}.startsWith('Docs review') && !!{panel('doc-review--notes', '[data-testid=pack-markdown]')}", 30)
        out["paint_sections"] = c.js("window.__sections")
        out["paint_loading_seen"] = c.js("window.__sawLoading")
        out["paint_boot_attr"] = c.js("JSON.parse(document.documentElement.dataset.packSections || '[]').map((s) => s.id)")
        out["paint_loading_after"] = c.js(f"!!{q('[data-testid=pack-section-loading]')}")
    finally:
        unset_config_value("model")
        if script:
            c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=script)
        c.call("Page.disable")
    alt(c, 1)  # the new page: Session mounted again (its Live column collects the events step's lines)
    c.wait(f"{CUR}.startsWith('Session') && !!{panel('doc-review--reviews', '.panel')}", 20)
    return out


def _row(ctx, rid: str) -> Path:
    folder = ctx["state"] / "packs" / ".data" / "doc-review" / "attention"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{rid}.json"
    path.write_text(json.dumps({"kind": "review.ask", "what": f"{rid}: 3 findings wait for you"}), encoding="utf-8")
    return path


def attention(c, url, ctx) -> dict:
    out: dict = {}
    first = _row(ctx, "readme")
    fleet_queue(c)  # 3.3.16.0 R2: Agents' Attention chip
    row = q('[data-panel="fleet-attention"] [data-testid=fleet-attn-row][data-kind="pack:doc-review:review.ask"]')
    c.wait(f"!!{row}", 25)
    out["attn_chip"] = c.js(f"{row}.querySelector('.fat-kind').textContent")
    out["attn_what"] = c.js(f"{row}.querySelector('.fat-what').textContent")
    out["attn_keys"] = c.js(f"[...{row}.querySelectorAll('[data-testid=fleet-attn-key]')].map((b) => b.textContent)")
    press(c, f"{row}.querySelector('[data-key=a]')")
    c.wait(f"!{row}", 15)
    answer = ctx["state"] / "packs" / ".data" / "doc-review" / "answers" / "readme.json"
    out["attn_answer"] = json.loads(answer.read_text(encoding="utf-8")).get("answer") if answer.is_file() else None
    out["attn_row_gone"] = not first.exists()
    return out


def disabled(c, url, ctx) -> dict:
    out: dict = {}
    _row(ctx, "later")
    row = q('[data-panel="fleet-attention"] [data-testid=fleet-attn-row][data-kind="pack:doc-review:review.ask"]')
    c.wait(f"!!{row}", 25)
    from halo_harness.packs.grants import disable
    disable("doc-review")
    c.wait(f"!{TABS}.some((t) => t.textContent.startsWith('Docs review'))", 15)
    out["tabs_after"] = c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)")
    out["attn_after"] = bool(c.wait(f"!{row}", 25))
    alt(c, 1)
    c.wait(f"{CUR}.startsWith('Session')", 10)
    out["session_panel_after"] = c.js(f"!!{panel('doc-review--reviews')}")
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait(f"!!{q('[data-testid=palette]')}", 10)
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("review checks")
    time.sleep(0.4)
    out["palette_after"] = c.js(f"{qa('.palette-label')}.map((l) => l.textContent).filter((t) => t.includes('review checks'))")
    c.key("Escape")
    live = qa("[data-testid=session-live-line][data-kind=pack]")
    before = c.js(f"{live}.length")
    try:  # 3.2.0.0 R5: a disabled pack's event is refused with one line (ext/events.py), so nothing new shows
        publish(ctx, "review.done", {"file": "README.md", "findings": 1})
        out["refused"] = ""
    except ValueError as e:
        out["refused"] = str(e)
    time.sleep(1.0)
    out["live_after"] = [before, c.js(f"{live}.length")]
    out["reloads"] = c.js("performance.getEntriesByType('navigation').length")
    return out
