"""tests.helpers.studio_design_rest -- the Design checks of Halo 3.0.7.0
round R3b (the classic page's last features, now in the React section),
driven through real clicks, keys and a double-click in headless Chrome:
knobs in the Artboards panel's settings face, a direct text edit (Esc
cancels, Enter saves a version), pinning a comment and resolving it, the
design-system panel (edit a token, Sync a folder), "3 directions" (three
artboards in one row) and the device select (kept across a reload). Run by
`python -m tests.helpers.studio_design design-rest`; no model is called
(turns run through design_api.RUNNER)."""
from __future__ import annotations

import json
import time
from pathlib import Path

Q = "document.querySelectorAll"


def tid(name: str) -> str:
    return f"{Q}('[data-testid=\"{name}\"]')"


def card(aid: str) -> str:
    return f"document.querySelector('[data-testid=\"design-artboard\"][data-id=\"{aid}\"]')"


def until(fn, timeout: float = 8.0):
    end = time.time() + timeout
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.1)
    return fn()


def at(c, expr: str, fx: float = 0.5, fy: float = 0.5) -> None:
    """Scroll `expr` into view inside its panel, then click it."""
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}})")
    time.sleep(0.15)
    c.click_on(expr, fx, fy)


def dblclick(c, x: float, y: float) -> None:
    c.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, button="none", buttons=0)
    for n in (1, 2):
        c.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=n)
        c.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=n)


def arrow_right(c) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key="ArrowRight", code="ArrowRight", windowsVirtualKeyCode=39)


def knobs(c, p, out: dict) -> None:
    at(c, card("hero") + ".querySelector('[data-testid=\"design-knobs\"]')")
    out["knobs"] = c.wait(f"[...{tid('design-knob')}].map((k) => k.dataset.name).join('|')", 10)
    c.js("document.querySelector('[data-testid=\"design-knob\"][data-name=\"Spacing\"] input[type=range]').focus()")
    arrow_right(c)  # 32 -> 34 px (step 2)
    out["knob_chip"] = c.wait("document.querySelector('[data-testid=\"design-knob-version\"]')?.textContent", 10)
    out["knob_css"] = bool(until(lambda: "--space:34px" in (p.artboard_dir("hero") / "index.html").read_text(encoding="utf-8")))
    out["knob_card_version"] = c.wait(card("hero") + ".querySelector('[data-testid=\"design-version\"]').textContent === 'v3' && 'v3'", 10)
    out["settings_device"] = c.js(f"document.querySelector('.inspector [data-testid=\"design-device\"]')?.value")
    c.key("Escape")  # Esc closes the Inspector
    c.wait("!document.querySelector('.inspector')", 5)


def text_edit(c, p, out: dict) -> None:
    page = p.artboard_dir("hero") / "index.html"
    at(c, card("hero") + ".querySelector('.da-title')", 0.3, 0.5)  # select it: a selected card's frame takes the pointer
    time.sleep(1.2)  # the frame reloaded with the knob's version

    def open_editor():
        x, y, w, _h = c.rect(card("hero") + ".querySelector('iframe')")
        k = w / 1280
        for _ in range(4):
            dblclick(c, x + 52 * k, y + 29 * k)  # the nav's PULSE (padding 17 px, a 24 px line)
            try:
                return c.wait("document.querySelector('[data-testid=\"design-text-edit-input\"]')?.value", 10)
            except TimeoutError:
                time.sleep(0.8)
        return None
    before = page.read_text(encoding="utf-8")
    out["edit_text"] = open_editor()
    c.key("Escape")
    try:
        gone = c.wait(f"!{tid('design-text-edit')}.length && 'gone'", 6)
    except TimeoutError:  # the Windows runner's Escape did not reach the editor once (ee033ec): press it on the box
        c.js("document.querySelector('[data-testid=\"design-text-edit-input\"]')?.dispatchEvent("
             "new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); 1")
        out["cancel_by"] = "element"
        gone = c.wait(f"!{tid('design-text-edit')}.length && 'gone'", 15)
    out["edit_cancelled"] = gone == "gone" and page.read_text(encoding="utf-8") == before
    open_editor()
    c.type_text("PULSE AI")  # the editor selected the text
    c.key("Enter")
    saved = bool(until(lambda: "<b>PULSE AI</b>" in page.read_text(encoding="utf-8")))
    if not saved:  # the Linux runner lost the typed text once (4bbb25d): set the editor's value and press Enter on it
        box = "document.querySelector('[data-testid=\"design-text-edit-input\"]')"
        if c.js(f"!!{box}") or open_editor():
            c.js(f"(() => {{ const i = {box}; i.focus(); "
                 "Object.getOwnPropertyDescriptor(Object.getPrototypeOf(i), 'value').set.call(i, 'PULSE AI'); "
                 "i.dispatchEvent(new Event('input', {bubbles: true})); "
                 "i.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); return 1; })()")
            saved = bool(until(lambda: "<b>PULSE AI</b>" in page.read_text(encoding="utf-8")))
            out["edit_by"] = "element"
    out["edit_saved"] = saved
    out["edit_kept_rest"] = "Ship the change" in page.read_text(encoding="utf-8") and "<style>" in page.read_text(encoding="utf-8")
    out["edit_version"] = c.wait(card("hero") + ".querySelector('[data-testid=\"design-version\"]').textContent === 'v4' && 'v4'", 10)


def comments(c, p, out: dict) -> None:
    at(c, "document.querySelector('[data-testid=\"design-tool-comment\"]')")
    at(c, card("logo-mark") + ".querySelector('.da-frame')", 0.25, 0.5)
    out["comment_box"] = c.wait(f"{tid('design-comment')}.length", 5)
    c.type_text("Make the pulse line thicker")
    c.key("Enter")
    mine = lambda: [x for x in p.comments() if x["artboard"] == "logo-mark"]  # noqa: E731
    got = until(mine)
    out["comment_saved"] = [got[0]["text"], 15 <= got[0]["x"] <= 35, 35 <= got[0]["y"] <= 65] if got else None
    out["comment_pins"] = c.wait(card("logo-mark") + ".querySelectorAll('[data-testid=\"design-pin\"]').length", 10)
    at(c, "document.querySelector('[data-testid=\"design-tool-select\"]')")
    at(c, card("logo-mark") + ".querySelector('[data-testid=\"design-pin\"]')")
    out["pin_pop"] = c.wait("document.querySelector('[data-testid=\"design-pin-pop\"] .da-pop-text')?.textContent", 5)
    at(c, "document.querySelector('[data-testid=\"design-resolve\"]')")
    out["resolved"] = bool(until(lambda: all(x.get("resolved") for x in mine())))
    out["pins_after"] = c.wait(card("logo-mark") + ".querySelectorAll('[data-testid=\"design-pin\"]').length === 0 && 'none'", 10)


def system(c, p, state: Path, out: dict) -> None:
    out["tokens"] = c.wait(f"{tid('design-token')}.length", 10)
    accent = "document.querySelector('[data-testid=\"design-token\"][data-group=\"colors\"][data-name=\"--accent\"] input')"
    at(c, accent)
    c.js(f"{accent}.select()")
    c.type_text("#ff3366")
    at(c, "document.querySelector('[data-testid=\"design-tokens-save\"]')")
    out["token_saved"] = bool(until(lambda: p.system().get("tokens", {}).get("colors", {}).get("--accent") == "#ff3366"))
    code = state.parent / "codebase"
    code.mkdir(exist_ok=True)
    (code / "theme.css").write_text(":root{--brand:#ff6600;--gap:12px}", encoding="utf-8")
    at(c, "document.querySelector('[data-testid=\"design-sync-source\"]')")
    c.type_text(str(code))
    at(c, "document.querySelector('[data-testid=\"design-sync\"]')")
    out["sync_title"] = c.wait("document.querySelector('[data-testid=\"design-sync-dialog\"] .dialog-title')?.textContent", 15)
    c.click_on("document.querySelector('[data-testid=\"design-sync-dialog\"] .btn-primary')")
    out["tokens_after"] = c.wait(f"{tid('design-token')}.length > {int(out['tokens'] or 0)} && {tid('design-token')}.length", 10)
    out["synced_brand"] = "--brand" in json.dumps(p.system().get("tokens", {}))


def directions(c, p, state: Path, out: dict) -> None:
    from halo_harness.studio import design_api
    seen: dict = {}

    def runner(cmd, cwd, env, on_line, stdin="", cancel=None):
        seen["prompt"] = stdin
        for s in "abc":
            d = Path(cwd) / "artboards" / f"pricing-{s}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(f"<!doctype html><html><body><h1>Pricing {s}</h1></body></html>", encoding="utf-8")
        on_line(json.dumps({"type": "result", "result": "Three directions.", "total_cost_usd": 0.01}))
        return 0
    design_api.RUNNER, design_api.REGISTERED = runner, set()
    at(c, "document.querySelector('[data-testid=\"design-send-box\"]')")
    c.type_text("a pricing section with three tiers")
    at(c, "document.querySelector('[data-testid=\"design-directions-base\"]')")
    c.type_text("pricing")
    at(c, "document.querySelector('[data-testid=\"design-directions\"]')")
    out["directions_cards"] = c.wait(f"{tid('design-artboard')}.length >= 5 && [...{tid('design-artboard')}].map((a) => a.dataset.id).sort().join('|')", 20)
    out["directions_prompt"] = str(seen.get("prompt", ""))[:60]
    tops = lambda: c.js("['hero', 'pricing-a', 'pricing-b', 'pricing-c'].map((id) =>"  # noqa: E731
                        " document.querySelector(`[data-testid=\"design-artboard\"][data-id=\"${id}\"]`)?.offsetTop ?? -1)")
    out["directions_tops"] = until(lambda: (lambda t: t if t and t[1] == t[2] == t[3] and t[1] > t[0] else None)(tops()), 8) or tops()
    out["directions_selected"] = c.wait(card("pricing-a") + "?.dataset.selected === 'true' && 'pricing-a'", 8)
    layout = state / "studio" / "layouts" / f"_design-{p.slug}.json"
    saved = until(lambda: layout.is_file() and json.loads(layout.read_text(encoding="utf-8")), 6) or {}
    out["directions_saved"] = all(f"pricing-{s}" in (saved.get("nodes") or saved) for s in "abc")


def device(c, url: str, out: dict) -> None:
    sel = "document.querySelector('.da-bar [data-testid=\"design-device\"]')"
    c.js(f"(() => {{ const el = {sel}; Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(el, 'phone');"
         " el.dispatchEvent(new Event('change', {bubbles: true})); })()")
    out["device_card"] = c.wait(card("hero") + ".dataset.device === 'phone' && 'phone'", 5)
    out["device_frame"] = c.js(card("hero") + ".querySelector('iframe').style.width")
    out["device_saved"] = c.js("localStorage.getItem('halo.studio.design.panel.design-artboards')")
    c.go("about:blank")
    c.go(url)
    c.wait(f"{tid('design-artboard')}.length >= 2", 20)
    out["device_reloaded"] = c.wait(f"{sel}?.value === 'phone' && " + card("hero") + ".dataset.device", 10)


def design_rest(c, url: str, state: Path) -> dict:
    from design_demo import seed
    p = seed(state)
    out: dict = {}
    c.go(url)
    out["artboards"] = c.wait(f"{tid('design-artboard')}.length >= 2 && {tid('design-artboard')}.length", 20)
    out["system_panel"] = c.wait(f"{tid('design-system')}.length", 10)
    for step in (lambda: knobs(c, p, out), lambda: text_edit(c, p, out), lambda: comments(c, p, out),
                 lambda: system(c, p, state, out), lambda: directions(c, p, state, out), lambda: device(c, url, out)):
        try:
            step()
        except Exception as e:  # one step's failure is reported; the next steps still run
            out.setdefault("errors", []).append(f"{type(e).__name__}: {str(e)[:200]}")
    return out
