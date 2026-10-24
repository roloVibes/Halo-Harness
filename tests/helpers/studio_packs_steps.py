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
    publish(ctx, "review.done", {"file": "README.md", "findings": 1})
    live = qa("[data-testid=session-live-line][data-kind=pack]")
    c.wait(f"{live}.length >= 3", 15)
    out["live_after"] = c.js(f"(() => {{ const l = {live}.pop(); return [l.querySelector('[data-testid=session-live-kind]').textContent, l.querySelector('[data-testid=session-live-pack]').textContent]; }})()")
    out["reloads"] = c.js("performance.getEntriesByType('navigation').length")
    return out
