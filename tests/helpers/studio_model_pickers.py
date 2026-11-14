"""tests.helpers.studio_model_pickers -- THE model picker in headless Chrome for tests/test_studio_model_pickers_ui.py
(Halo 3.4.1.3 "Pick, don't type"), real keys and clicks through the driver base, over a fresh home with a catalog of
two fake OpenRouter models and no other provider; no provider request, no model call (the probe is stubbed):

    python -m tests.helpers.studio_model_pickers pickers

1. Agents -> Models: "Test a model" is the picker field; at the panel's default size nothing in it scrolls sideways;
   a click opens the picker with its search focused, typing filters, Enter picks the first match, Test answers;
2. a letter typed on the closed field opens the picker with that letter searched; Esc closes it;
3. the last row: a wrong prefix says which prefixes exist and Use it stays off; a good ref is checked as typed and
   Enter uses it; the field then marks it "not in your catalog" and the picker shows it as its saved row;
4. Settings: a model row (compactionModel) is the picker -- a row saves the key, the first row (the default) resets
   it; a role's model (roles.<role>) is the picker too; embeddings.model lists Ollama models only and says so.
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
from tests.helpers.model_pick import open_picker, scope  # noqa: E402
from tests.helpers.studio_model_select import BETA, seed_catalog  # noqa: E402
from tests.helpers.studio_roles_model import PROBE  # noqa: E402

REF = "document.querySelector('[data-testid=\"roles-models-ref\"]')"
TRIG = f"{REF}?.querySelector('[data-testid=\"model-select\"]')"
SEARCH = f"{REF}?.querySelector('[data-testid=\"model-search\"]')"
ACTIVE = "document.activeElement?.dataset?.testid"
# the nearest ancestor that scrolls sideways (or the page), and whether it does
SIDEWAYS = """((el) => { const out = []; for (let n = el; n && n !== document.body; n = n.parentElement) {
  const s = getComputedStyle(n); if (/(auto|scroll)/.test(s.overflowX) && n.scrollWidth > n.clientWidth + 1) out.push(n.className || n.tagName); }
  return out; })"""


def _clear_and_type(c, expr: str, text: str) -> None:
    c.js(f"(() => {{ const s = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
         f"set.call(s, ''); s.dispatchEvent(new Event('input', {{bubbles: true}})); s.focus(); return 1; }})()")
    c.type_text(text)


def models_panel(c, url: str) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"!!{TRIG}", 40)
    c.js(f"{REF}.scrollIntoView({{block: 'center'}}); 1")
    out["sideways_closed"] = c.js(f"{SIDEWAYS}(document.querySelector('[data-testid=\"roles-models-body\"]'))")
    out["is_button"] = c.js(f"{TRIG}.tagName")
    c.click_on(TRIG)
    out["search_focused"] = c.wait(f"{ACTIVE} === 'model-search' && 'focused'", 10)
    out["sideways_open"] = c.js(f"{SIDEWAYS}({REF}.querySelector('[data-testid=\"model-row\"]'))")
    out["rows"] = c.wait(f"(() => {{ const r = [...{REF}.querySelectorAll('[data-testid=\"model-row\"]')].map((r) => r.dataset.ref); return r.length === 2 && r; }})()", 20)
    out["groups"] = c.js(f"[...{REF}.querySelectorAll('[data-testid=\"model-group\"]')].map((g) => g.textContent)")
    c.type_text("beta")
    out["typed_rows"] = c.wait(f"(() => {{ const r = [...{REF}.querySelectorAll('[data-testid=\"model-row\"]')]; return r.length === 1 && r[0].dataset.hot && r.map((x) => [x.dataset.ref, !!x.dataset.hot]); }})()", 10)
    c.key("Enter")
    try:
        out["enter_pick"] = c.wait(f"{REF}.dataset.value === {json.dumps(BETA)} && !{SEARCH} && {REF}.dataset.value", 10)
    except TimeoutError:
        raise TimeoutError("enter: " + json.dumps(c.js(f"[{REF}?.dataset.value, !!{SEARCH}, {ACTIVE}, location.search, "
                                                       "document.querySelectorAll('[data-testid=roles-models-body]').length, "
                                                       "document.querySelectorAll('[data-testid=model-select]').length, document.activeElement?.outerHTML?.slice(0, 160)]")))
    c.click_on(f"{REF}.querySelector('[data-testid=\"model-select-test\"]')")
    out["probe"] = c.wait(f"{REF}.querySelector('[data-testid=\"model-select-result\"]')?.textContent", 10)
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)
    c.js(f"{TRIG}.focus(); 1")
    c.key("a")
    out["key_open"] = c.wait(f"{SEARCH}?.value", 10)
    c.key("Escape")
    out["esc_closed"] = c.wait(f"!{SEARCH} && 'closed'", 10)
    return out


def not_listed(c) -> dict:
    out: dict = {}
    open_picker(c, REF)
    c.js(f"{REF}.querySelector('[data-testid=\"model-not-listed\"]').click(); 1")
    box = f"{REF}.querySelector('[data-testid=\"model-typed\"]')"
    line = f"{REF}.querySelector('[data-testid=\"model-typed-check\"]')"
    use = f"{REF}.querySelector('[data-testid=\"model-typed-use\"]')"
    c.wait(f"{ACTIVE} === 'model-typed'", 10)
    _clear_and_type(c, box, "zz:thing")
    out["bad_line"] = c.wait(f"{line}?.textContent.includes('not a prefix') && {line}.textContent", 10)
    out["bad_use_off"] = c.js(f"{use}.disabled")
    _clear_and_type(c, box, "or:vendor/other-9")
    out["good_line"] = c.wait(f"{line}?.dataset.ok && {line}.textContent", 10)
    c.js(f"{box}.focus(); 1")
    c.key("Enter")
    out["typed_value"] = c.wait(f"{REF}.dataset.value === 'or:vendor/other-9' && {REF}.dataset.value", 10)
    out["off_mark"] = c.js(f"{REF}.querySelector('[data-testid=\"model-select-off\"]')?.textContent")
    open_picker(c, REF)
    out["saved_row"] = c.js(f"[{scope(REF)}.querySelector('[data-testid=\"model-saved\"]')?.dataset.ref, "
                            f"{scope(REF)}.querySelector('[data-testid=\"model-saved\"]')?.textContent]")
    c.key("Escape")
    return out


def settings(c, url: str, state: Path) -> dict:
    from tests.helpers.studio_settings import group, row
    cfg = lambda: json.loads((state / "config.json").read_text(encoding="utf-8")) if (state / "config.json").is_file() else {}  # noqa: E731
    out: dict = {}
    c.go("about:blank")
    c.go(url.replace("mode=roles", "mode=settings"))
    c.wait("document.querySelectorAll('[data-testid=settings-row]').length > 0", 40)
    group(c, "general")
    field = row("compactionModel")
    open_picker(c, field)
    out["settings_rows"] = c.wait(f"(() => {{ const r = [...{field}.querySelectorAll('[data-testid=settings-model-row]')].map((r) => r.dataset.ref); "
                                  f"return r.length === 2 && r; }})()", 20)
    c.js(f"{field}.querySelector('[data-testid=settings-model-row][data-ref=\"{BETA}\"]').click(); 1")
    for _ in range(60):
        if cfg().get("compactionModel") == BETA:
            break
        time.sleep(0.2)
    out["compaction_saved"] = cfg().get("compactionModel")
    open_picker(c, field)
    c.js(f"{field}.querySelector('[data-testid=settings-model-inherit]').click(); 1")
    for _ in range(60):
        if "compactionModel" not in cfg():
            break
        time.sleep(0.2)
    out["compaction_reset"] = "compactionModel" not in cfg()
    group(c, "agents")
    out["role_fields"] = c.wait(f"{row('roles.<role>')} && {row('roles.<role>')}.querySelectorAll('[data-testid=settings-entry] [data-testid=model-select]').length", 15)
    group(c, "local")
    emb = row("embeddings.model")
    open_picker(c, emb)
    out["embed_why"] = c.wait(f"{emb}.querySelector('[data-testid=models-empty]')?.textContent", 10)
    return out


def pickers(c, url: str, state: Path) -> dict:
    out = models_panel(c, url)
    out.update(not_listed(c))
    out.update(settings(c, url, state))
    return out


class PickersDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness import model_probe as probe
        state = seeded_home()
        seed_catalog(state)
        probe.probe_model = lambda ref, **_kw: {**PROBE, "ref": ref}
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)
        try:
            yield ((pickers, (c, url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace"), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:2] != ["pickers"]:
        print("usage: python -m tests.helpers.studio_model_pickers pickers", file=sys.stderr)
        sys.exit(2)
    sys.exit(PickersDriver(sys.argv[2:]).main())
