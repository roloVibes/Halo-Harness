"""tests.helpers.studio_settings -- the Settings section (Halo 3.3.3.0 R2), real keys and clicks in headless Chrome
through the driver base, over a fresh scratch home (capture_studio's seeded_home) with one secret saved
(`embeddings.api_key`, a placeholder); no provider request, no model call:

1. Alt+9 opens Settings with nothing open over it (no help, no Start here, no dialog after 2 s), on General;
2. every group page: the rail's groups and each page's `data-key` rows (the test holds them to the catalog);
3. a bool toggled (config.json has it, the flash says the effect word), an enum picked, a number set, Reset
   (the key gone, the default marker back);
4. a mapping that is not JSON: the problems line under its editor and config.json byte for byte as it was;
5. the search box narrows to rows across groups (a caption per group);
6. the door `?mode=settings&group=fleet` lands on Fleet and drops the group word from the address;
7. a secret row never shows its value; a palette entry opens its row's group and lights the row.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, alt, mod_key, q, qa  # noqa: E402

SECRET = "sk-settings-driver-placeholder-0000"
PAGE = "(document.querySelector('[data-testid=settings-group-page]')?.dataset.group || '')"
OPEN = ("[!!document.querySelector('[data-testid=section-help]'), !!document.querySelector('[data-testid=start-here]'), "
        "document.querySelectorAll('[role=dialog]').length]")
KEYS = qa("[data-testid=settings-group-page] [data-testid=settings-row]") + ".map((r) => r.dataset.key)"


def row(key: str, inner: str = "") -> str:
    return q(f'[data-testid=settings-row][data-key="{key}"] {inner}'.strip())


def config(ctx) -> dict:
    p = ctx["state"] / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def group(c, gid: str) -> None:
    btn = q(f"[data-testid=settings-rail-group][data-group={gid}]")
    c.wait(f"!!{btn}", 20)
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(btn)
    try:
        c.wait(f"{PAGE} === '{gid}'", 4)
    except TimeoutError:
        c.js(f"{btn}.click(); 1")
        c.wait(f"{PAGE} === '{gid}'", 15)


def press(c, expr: str, done: str) -> None:
    """Click `expr` with the pointer and wait for `done`; the element's own click when the pointer missed."""
    c.wait(f"!!({expr}) && !({expr}).disabled", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)
    try:
        c.wait(done, 4)
    except TimeoutError:
        c.js(f"({expr})?.click(); 1")
        c.wait(done, 15)


def set_field(c, expr: str, value: str, event: str = "input") -> None:
    """Type into an input / textarea / select the way React hears it (the native setter, then the event)."""
    proto = {"input": "HTMLInputElement", "textarea": "HTMLTextAreaElement", "select": "HTMLSelectElement"}
    c.js(f"(() => {{ const el = {expr}; el.focus(); const p = {{INPUT: '{proto['input']}', TEXTAREA: '{proto['textarea']}', "
         f"SELECT: '{proto['select']}'}}[el.tagName]; Object.getOwnPropertyDescriptor(window[p].prototype, 'value').set.call(el, "
         f"{json.dumps(value)}); el.dispatchEvent(new Event('{event}', {{bubbles: true}})); return 1; }})()")


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off#{ctx['frag']}"


def _load(c, ctx, query: str, section: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(_url(ctx, query))
    c.wait(f"{CUR}.startsWith('{section}')", 40)


def alt9(c, url, ctx) -> dict:
    _load(c, ctx, "mode=roles&tour=off", "Roles")
    time.sleep(1.0)
    alt(c, 9)
    c.wait(f"{CUR}.startsWith('Settings') && {qa('[data-testid=settings-row]')}.length > 0", 30)
    time.sleep(2.0)
    return {"alt9_open": c.js(OPEN), "alt9_page": c.js(PAGE), "alt9_section": c.js(CUR),
            "alt9_panels": c.js(f"{qa('[data-section=settings] [data-panel]')}.length")}


def every_page(c, url, ctx) -> dict:
    groups = c.js(qa("[data-testid=settings-rail-group]") + ".map((b) => b.dataset.group)")
    pages = {}
    for gid in groups:
        group(c, gid)
        pages[gid] = c.js(KEYS)
    return {"rail_groups": groups, "pages": pages}


def edits(c, url, ctx) -> dict:
    out = {}
    group(c, "fleet")
    press(c, row("fleet.enabled", "[data-testid=settings-toggle]"), f"!!{row('fleet.enabled', '[data-testid=settings-saved]')}")
    out["toggle_flash"] = c.js(f"{row('fleet.enabled', '[data-testid=settings-saved]')}.textContent")
    out["toggle_config"] = config(ctx).get("fleet", {}).get("enabled")
    out["toggle_default_gone"] = c.js(f"!{row('fleet.enabled', '[data-testid=settings-default]')}")
    set_field(c, row("fleet.share", "select"), "full", "change")
    out["enum_flash"] = c.wait(f"{row('fleet.share', '[data-testid=settings-saved]')}?.textContent", 15)
    out["enum_config"] = config(ctx).get("fleet", {}).get("share")
    port = row("fleet.hub.port", "input")
    set_field(c, port, "7431")
    c.js(f"{port}.blur(); 1")
    out["number_flash"] = c.wait(f"{row('fleet.hub.port', '[data-testid=settings-saved]')}?.textContent", 15)
    out["number_config"] = config(ctx).get("fleet", {}).get("hub", {}).get("port")
    out["number_cli"] = c.js(f"{row('fleet.hub.port', '[data-testid=settings-cli]')}.textContent")
    press(c, row("fleet.enabled", "[data-testid=settings-reset]"), f"!!{row('fleet.enabled', '[data-testid=settings-default]')}")
    out["reset_marker"] = True
    out["reset_config"] = "enabled" in config(ctx).get("fleet", {})
    out["reset_off"] = c.js(f"{row('fleet.enabled', '[data-testid=settings-reset]')}.disabled")
    return out


def bad_json(c, url, ctx) -> dict:
    group(c, "providers")
    key = "openai.dialect_overrides"
    before = (ctx["state"] / "config.json").read_bytes()
    set_field(c, row(key, "textarea"), '{"gpt-5": responses')
    problems = row(key, ".st-json [data-testid=settings-problems]")
    press(c, row(key, "[data-testid=settings-json-save]"), f"!!{problems}")
    problems = row(key, ".st-json [data-testid=settings-problems]")
    out = {"json_problems": c.wait(f"{problems}?.textContent", 15)}
    out["json_unchanged"] = (ctx["state"] / "config.json").read_bytes() == before
    out["json_problem_rows"] = c.js(f"{qa('[data-testid=settings-problems]')}.length")
    return out


def search(c, url, ctx) -> dict:
    box = q("[data-testid=settings-search]")
    set_field(c, box, "port")
    c.wait(f"!!{q('[data-testid=settings-hits]')}", 15)
    out = {"search_keys": c.js(qa("[data-testid=settings-hits] [data-testid=settings-row]") + ".map((r) => r.dataset.key)"),
           "search_groups": c.js(qa("[data-testid=settings-hits-group]") + ".map((g) => g.dataset.group)")}
    set_field(c, box, "")
    c.wait(f"!{q('[data-testid=settings-hits]')} && {PAGE} === 'providers'", 15)
    return out


def door(c, url, ctx) -> dict:
    group(c, "general")
    _load(c, ctx, "mode=settings&group=fleet", "Settings")
    out = {"door_page": c.wait(f"{PAGE} === 'fleet' && {PAGE}", 20), "door_search": c.js("location.search")}
    _load(c, ctx, "mode=settings", "Settings")
    out["door_remembered"] = c.wait(f"{PAGE} === 'fleet' && {PAGE}", 20)
    return out


def secret(c, url, ctx) -> dict:
    group(c, "local")
    key = "embeddings.api_key"
    out = {"secret_masked": c.wait(f"!!{row(key, '[data-testid=settings-masked]')}", 15),
           "secret_type": c.js(f"{row(key, 'input')}.type"), "secret_value": c.js(f"{row(key, 'input')}.value")}
    seen = c.js("document.body.innerText + [...document.querySelectorAll('input, textarea')].map((i) => i.value).join(' ')")
    out["secret_seen"] = SECRET in seen or SECRET[-12:] in seen
    return out


def palette(c, url, ctx) -> dict:
    group(c, "general")
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait(f"!!{q('[data-testid=palette]')}", 10)
    c.js(f"{q('.palette-input')}.focus(); 1")
    c.type_text("Settings: Hub port")
    c.wait(f"{qa('[role=option]')}.some((o) => /Settings: Hub port/.test(o.textContent))", 10)
    c.key("Enter")
    out = {"palette_page": c.wait(f"{PAGE} === 'fleet' && {PAGE}", 15)}
    out["palette_lit"] = c.wait(f"!!{q('[data-testid=settings-row][data-lit]')} && {q('[data-testid=settings-row][data-lit]')}.dataset.key", 10)
    return out


class SettingsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.theme import set_config_value
        state = seeded_home()
        set_config_value("embeddings.api_key", SECRET)
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (alt9, every_page, edits, bad_json, search, door, secret, palette))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(SettingsDriver(sys.argv[1:]).main())
