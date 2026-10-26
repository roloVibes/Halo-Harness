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
    mod_key(c, f"Digit{n}", 48 + n, 1, str(n))


def press(c, expr: str) -> None:
    c.wait(f"!!({expr})", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.25)
    c.click_on(expr)


def publish(ctx, kind: str, data) -> None:
    from halo_harness.ext import publish_event
    from halo_harness.studio.events import bridge_for
    assert publish_event("doc-review", kind, data, bridge=bridge_for(ctx["srv"]))


def events(c, url, ctx) -> dict:
    out: dict = {}
    alt(c, 4)
    c.wait(f"{CUR}.startsWith('Fleet') && !!{q('[data-testid=fleet-log]')}", 20)
    publish(ctx, "review.done", {"file": "README.md", "findings": 3})
    publish(ctx, "review.started", {"file": "docs/A.md"})
    log = qa("[data-testid=fleet-log-line][data-kind=pack]")
    c.wait(f"{log}.length >= 2", 15)
    out["activity"] = c.js(f"{log}.map((l) => l.querySelector('.fac-text').textContent)")
    alt(c, 1)
    live = qa("[data-testid=session-live-line][data-kind=pack]")
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
    alt(c, 9)  # 3.3.0.0 R1: the first pack section
    c.wait(f"{CUR}.startsWith('Docs review')", 10)
    out["saved_section"] = c.js("localStorage.getItem('halo.studio.section')")
    c.call("Page.enable")  # the new-document script runs only with the Page domain on (off again below)
    script = c.call("Page.addScriptToEvaluateOnNewDocument", source=FIRST_PAINT).get("identifier")
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
    alt(c, 4)
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
