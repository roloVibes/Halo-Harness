"""tests.helpers.studio_switch_lists -- the page checks of
tests/test_studio_switch_lists.py (Halo 3.3.5.0 R0 (f), (g), (h)): real clicks in
headless Chrome through the driver base, over a seeded home (capture_studio's
seeded_home) with a stub catalog of 300 OpenRouter rows (studio/model.py
model_rows) and a fake Claude Code settings.json whose `env` names a
Databricks workspace host (the placeholder) and no token. No provider
request, no model call:

1. Setup -> Default model: all 300 rows are in the page (drawn a window at a
   time), the count line says 300, the search still narrows;
2. Setup -> Providers: the Databricks card reads "host from Claude Code's
   settings.json · token not set" and prints no host;
3. a Save on a paged section raises no toast, and a toast (one put in the
   toasts layer) sits top right, clear of the foot's Next;
4. Roles: the bio form's model picker lists all 300 rows with its count line.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_setup_pages import goto  # noqa: E402

N = 300
HOST = "https://your-workspace.cloud.databricks.com"
ROWS = [{"ref": f"or:mock/m{i:03d}", "provider": "openrouter", "group": "OpenRouter", "detail": f"Mock {i}", "price": "$1.00",
         "context": "128k", "context_tokens": 128000, "price_in": 1.0, "price_out": 2.0, "chips": [],
         "best_at": {"line": "summaries" if i == 7 else "", "kinds": []}, "learned": {}} for i in range(N)]
FORM = "document.querySelector('[data-testid=\"bio-form\"][data-bio=\"implementer\"]')"
STRIP = "document.querySelector('[data-testid=\"roles-model-strip\"]')"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def _type(c, sel: str, text: str) -> None:
    c.js(f"(() => {{ const s = {q(sel)}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
         f"set.call(s, {json.dumps(text)}); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()")


def setup_list(c, url, ctx) -> dict:
    c.go(url.replace("mode=roles", "mode=setup"))
    goto(c, "model")
    rows = qa("[data-testid=setup-model-row]")
    out = {"rows": c.wait(f"{rows}.length === {N} && {rows}.length", 20),
           "count_line": c.js(_text("[data-testid=setup-model-count]"))}
    out["refs_unique"] = c.js(f"new Set({rows}.map((r) => r.dataset.ref)).size")
    _type(c, "[data-testid=setup-model-search]", "summar")
    out["searched"] = c.wait(f"{rows}.length === 1 && {rows}.map((r) => r.dataset.ref)", 10)
    _type(c, "[data-testid=setup-model-search]", "")
    c.wait(f"{rows}.length === {N}", 20)
    return out


def card_source(c, url, ctx) -> dict:
    goto(c, "providers")
    state = _text("[data-testid=setup-provider-state][data-name=databricks]")
    out = {"dbx_state": c.wait(f"{state}.length > 0 && {state}", 20)}
    out["host_in_state"] = c.js(f"{state}.includes('your-workspace')")
    return out


def toasts(c, url, ctx) -> dict:
    goto(c, "permissions")
    row = q("[data-testid=setup-mode][data-id=plan] input")
    c.js(f"{row}.click(); 1")
    btn = q("[data-testid=setup-save][data-block=permission_mode]")
    c.wait(f"!!{btn} && !{btn}.disabled", 10)
    c.js(f"{btn}.click(); 1")
    c.wait(f"{_text('[data-testid=setup-word][data-block=permission_mode]')} === 'saved'", 10)
    time.sleep(0.4)
    out = {"toasts_after_save": c.js("document.querySelectorAll('.toasts .toast').length")}
    # a toast another section raised: the layer is the same on every section
    c.js("(() => { const t = document.createElement('div'); t.className = 'toast toast-done'; t.dataset.probe = '1';"
         " t.textContent = 'a toast from another section, long enough to be wide'; document.querySelector('.toasts').appendChild(t); return 1; })()")
    nxt = q("[data-testid=setup-next]")
    c.wait(f"!!{nxt}", 10)
    out["overlap"] = c.js(f"""(() => {{ const a = document.querySelector('.toasts [data-probe]').getBoundingClientRect();
      const b = {nxt}.getBoundingClientRect();
      return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top); }})()""")
    out["toast_top"] = c.js("Math.round(document.querySelector('.toasts').getBoundingClientRect().top)")
    out["topbar"] = c.js("Math.round(document.querySelector('.topbar, header')?.getBoundingClientRect().bottom || 0)")
    c.js("document.querySelector('.toasts [data-probe]').remove(); 1")
    return out


def card(agent: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === '{agent}')"


def roles_picker(c, url, ctx) -> dict:
    c.go(url)
    c.wait(f"!!{card('implementer')}", 40)
    c.js(f"{card('implementer')}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(card("implementer"), 0.5, 0.2)
    c.wait(f"{STRIP}?.dataset.card && !{STRIP}.dataset.main", 15)
    c.click_on(f"{STRIP}.querySelector('[data-testid=\"roles-model-bio-link\"]')")
    c.wait(f"!!{FORM}", 15)
    more = f"{FORM}.querySelector('[data-testid=\"bio-model\"] [data-testid=\"model-select-more\"]')"
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    rows = f"{FORM}.querySelectorAll('[data-testid=\"model-row\"]')"
    out = {"picker_rows": c.wait(f"{rows}.length === {N} && {rows}.length", 20),
           "picker_count": c.js(f"{FORM}.querySelector('[data-testid=\"model-count\"]')?.textContent")}
    return out


class SwitchListsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.studio import model as M
        state = seeded_home()
        claude = Path(os.environ["BRIDGE_TEST_HOME"]) / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "databricks-claude-sonnet-4",
                                                                  "DATABRICKS_HOST": HOST}}), encoding="utf-8")
        saved_env = {k: os.environ.get(k) for k in ("HALO_ENV_FILE",)}
        os.environ["HALO_ENV_FILE"] = str(state.parent / "halo-env")
        real = M.model_rows
        M.model_rows = lambda *_a, **_k: [dict(r) for r in ROWS]
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url).replace("mode=orchestra&feed=off", "mode=roles&tour=off&view=workspace")
        ctx = {"state": state}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (setup_list, card_source, toasts, roles_picker))
        finally:
            M.model_rows = real
            for k, v in saved_env.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(SwitchListsDriver(sys.argv[1:]).main())
