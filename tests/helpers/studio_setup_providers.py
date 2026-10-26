"""tests.helpers.studio_setup_providers -- the Providers and Local models steps
of the Setup driver (tests/helpers/studio_setup.py, Halo 3.3.0.0 R2), real
keys and clicks in headless Chrome over the driver's scratch home, whose env
file is `HALO_ENV_FILE` in that home (never ~/.config/halo/env); no network
(`BRIDGE_TEST_NO_BACKGROUND_NET=1`), no provider request:

1. the eight provider cards; OpenRouter's Save & test with a test key: the env
   file has it, the card says "set, from the env file, ****<tail>", the field
   is empty again, the key is nowhere in the page, the strip names openrouter;
2. Ollama: a host added by name and URL appears in the hosts table (the
   first is the default); (R5, studio_setup_discover.py) Find, Add, Measure;
3. Local models: a folder added appears in the list and the detection lines
   count its model; the runtime saved.
"""
from __future__ import annotations

import json
import time

from tests.helpers.studio_packs_steps import q, qa
from tests.helpers.studio_setup_pages import goto

KEY = "sk-or-v1-s2chrome-test-0011223344"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def fill(c, card: str, field: str, text: str) -> str:
    """Type into a card's field (a click, then the keys); when the pointer missed, set the value itself."""
    sel = f"[data-testid=setup-input][data-card={card}][data-field={field}]"
    c.wait(f"!!{q(sel)}", 20)
    c.js(f"{q(sel)}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(q(sel))
    c.type_text(text)
    try:
        c.wait(f"{q(sel)}.value === {json.dumps(text)}", 4)
        return "keys"
    except TimeoutError:
        c.js(f"(() => {{ const s = {q(sel)}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
             f"set.call(s, {json.dumps(text)}); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()")
        c.wait(f"{q(sel)}.value === {json.dumps(text)}", 10)
        return "element"


def press(c, card: str, done: str) -> str:
    """Click a card's save button and wait for `done`; the element's own click when the pointer missed."""
    btn = q(f"[data-testid=setup-card-save][data-card={card}]")
    c.wait(f"!!{btn} && !{btn}.disabled", 10)
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(btn)
    try:
        c.wait(done, 8)
        return "pointer"
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(done, 15)
        return "element"


def _lines(card: str) -> str:
    return _text(f"[data-testid=setup-card-lines][data-card={card}]")


def providers(c, url, ctx) -> dict:
    goto(c, "providers")  # 3.3.1.0 R1: one block a page
    c.wait(f"{qa('[data-testid=setup-provider]')}.length === 8", 30)
    out = {"cards": c.js(qa("[data-testid=setup-provider]") + ".map((p) => p.dataset.name)"),
           "or_before": c.js(_text("[data-testid=setup-provider-state][data-name=openrouter]")),
           "or_field_type": c.js(f"{q('[data-testid=setup-input][data-card=openrouter][data-field=key]')}.type"),
           "or_placeholder": c.js(f"{q('[data-testid=setup-input][data-card=openrouter][data-field=key]')}.placeholder")}
    out["or_fill_by"] = fill(c, "openrouter", "key", KEY)
    state = _text("[data-testid=setup-provider-state][data-name=openrouter]")
    out["or_save_by"] = press(c, "openrouter", f"{state}.startsWith('set') && !!{q('[data-testid=setup-card-lines][data-card=openrouter]')}")
    out["or_state"] = c.js(state)
    out["or_lines"] = c.js(_lines("openrouter"))
    out["or_test"] = c.js(_text("[data-testid=setup-provider-test][data-name=openrouter]"))
    out["or_enabled"] = c.js(_text("[data-testid=setup-provider-enabled][data-name=openrouter]"))
    out["or_field_after"] = c.js(f"{q('[data-testid=setup-input][data-card=openrouter][data-field=key]')}.value")
    out["or_strip"] = c.wait(f"{_text('[data-testid=setup-strip-cell][data-key=provider] .su-cell-value')} === 'openrouter' && 'openrouter'", 10)
    out["key_in_page"] = c.js(f"document.documentElement.outerHTML.includes({json.dumps(KEY)})")
    env = ctx["env_file"]
    out["env_has_key"] = env.is_file() and f"OPENROUTER_API_KEY={KEY}" in env.read_text(encoding="utf-8").splitlines()
    return out


def ollama(c, url, ctx) -> dict:
    out = {"ollama_fill_by": [fill(c, "ollama", "name", "lan"), fill(c, "ollama", "url", "192.0.2.20:11434")]}
    rows = qa("[data-testid=setup-row][data-card=ollama]")
    out["ollama_save_by"] = press(c, "ollama", f"{rows}.length === 1")
    out["ollama_rows"] = c.js(f"{rows}.map((r) => [...r.querySelectorAll('td')].slice(0, 4).map((t) => t.textContent))")
    out["ollama_state"] = c.js(_text("[data-testid=setup-provider-state][data-name=ollama]"))
    out["ollama_finders"] = c.js(f"[{q('[data-testid=setup-ollama-find]')}.disabled, {q('[data-testid=setup-ollama-scan]')}.disabled]")
    out["ollama_later"] = c.js(_text("[data-testid=setup-ollama-later]"))
    cfg = ctx["state"] / "config.json"
    out["ollama_config"] = [h.get("url") for h in json.loads(cfg.read_text(encoding="utf-8")).get("ollama", {}).get("hosts", [])]
    return out


def local(c, url, ctx) -> dict:
    goto(c, "local")
    folder = ctx["models"]
    out = {"dir_fill_by": fill(c, "local-dir", "path", str(folder))}
    rows = qa("[data-testid=setup-row][data-card=local-dir]")
    out["dir_save_by"] = press(c, "local-dir", f"{rows}.length === 1")
    out["dirs"] = c.js(f"{rows}.map((r) => r.dataset.key)")
    out["detection"] = c.wait(f"{_text('[data-testid=setup-detection]')}.includes('holds 1 model') && {_text('[data-testid=setup-detection]')}", 15)
    out["rail_local"] = c.wait(f"{q('[data-testid=setup-rail-step][data-step=local]')}.dataset.word.startsWith('1 folder') && "
                               f"{q('[data-testid=setup-rail-step][data-step=local]')}.dataset.word", 10)
    row = "[data-testid=setup-runtime][data-id=mlx_lm]"
    c.js(f"{q(row)}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(q(row), 0.6, 0.5)
    try:
        c.wait(f"{q(row + ' input')}.checked", 4)
    except TimeoutError:
        c.js(f"{q(row + ' input')}.click(); 1")
        c.wait(f"{q(row + ' input')}.checked", 10)
    btn = q("[data-testid=setup-runtime-save]")
    c.wait(f"!{btn}.disabled", 10)
    c.click_on(btn)
    try:
        c.wait(f"!!{q('[data-testid=setup-card-lines][data-card=local-runtime]')}", 8)
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(f"!!{q('[data-testid=setup-card-lines][data-card=local-runtime]')}", 15)
    cfg = json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))
    out["runtime_config"] = (cfg.get("huggingface") or {}).get("preferred_runtime")
    out["dirs_config"] = (cfg.get("huggingface") or {}).get("model_dirs")
    return out


# 3.3.0.0 R5: Find, Add, the Models panel and Measure run right after the Ollama host step
from tests.helpers.studio_setup_discover import STEPS as DISCOVER_STEPS  # noqa: E402

STEPS = (providers, ollama, *DISCOVER_STEPS, local)
