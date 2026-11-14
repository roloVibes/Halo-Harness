"""tools/capture_picker.py -- the model picker capture for tools/capture_studio.py --mode picker (Halo 3.3.17.1 docs: the
README shows Studio's picker, not the terminal's), through headless Chrome over the DevTools protocol (tests/helpers/cdp.py),
over the scratch home capture_studio seeds. No model is called and nothing is fetched: the catalog is eight fixture rows
(`demo/` names, five providers) that studio/model.py's `model_rows` answers in place of the live catalogs:

    docs/media/studio-model-picker.png   Agents -> Cast with the implementer's card selected and the picker of its bio's
                                         model open in the Inspector: the search box, the sort, eight rows each with its
                                         price in / out, its context and its TAKES tags (text, vision, audio, video, pdf,
                                         image, tools, think; `?` when the catalog states nothing), one row highlighted
                                         and its detail line under the list: the honest best-at line

1500 x 900 CSS px at scale 2. With --dom the page is counted by data-testid (the last stdout line is the JSON). The page is
guarded before it is counted or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "roles-canvas", "roles-card", "roles-model-strip", "bio-form", "model-picker", "model-search", "model-row",
       "model-takes", "model-detail")
HOT = "or:demo/atlas-pro"
# ref, provider, group, price in / out per 1M, context tokens, takes, best-at line (None: nothing stated: `?`)
FIXTURE = (
    ("or:demo/atlas-pro", "openrouter", "OpenRouter", 3.0, 15.0, 200_000, ["text", "vision", "tools", "think"], "code, review, long plans"),
    ("or:demo/atlas-mini", "openrouter", "OpenRouter", 0.3, 1.2, 128_000, ["text", "tools"], "summaries, quick edits, bulk work"),
    ("dbx:demo/helix-70b", "databricks", "Databricks", 1.0, 3.0, 128_000, ["text", "tools"], "code, tool calls"),
    ("ant:demo/vesper-large", "anthropic", "Anthropic API", 15.0, 75.0, 400_000, ["text", "vision", "pdf", "tools", "think"], "hard reasoning, long documents"),
    ("oai:demo/orbit-5", "openai", "OpenAI API", 2.5, 10.0, 1_000_000, ["text", "vision", "audio", "tools"], "long documents, images in"),
    ("ol:demo/mica-coder:30b", "ollama", "Ollama (lab)", 0.0, 0.0, 65_536, ["text", "tools"], "code, runs on your own GPU"),
    ("hf:demo/lumen-vl", "huggingface", "Hugging Face", 0.8, 2.4, 64_000, ["text", "vision", "video"], "images and video in"),
    ("or:demo/quill-x", "openrouter", "OpenRouter", None, None, None, ["?"], None),
)


def rows() -> list:
    from halo_harness.model_display import format_price_per_m, format_token_count
    out = []
    for ref, prov, group, pin, pout, ctx, takes, line in FIXTURE:
        out.append({"ref": ref, "provider": prov, "group": group, "detail": ref.split("/", 1)[1], "price_in": pin, "price_out": pout,
                    "price": format_price_per_m(pin) or "?", "context": format_token_count(ctx) or "?", "context_tokens": ctx, "speed": "?",
                    "local": prov == "ollama", "chips": "text", "takes": takes, "best_at": {"line": line or "", "kinds": []},
                    "learned": {}, "effort_word": "", "verified": True})
    return out


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


# The capture's own arrangement: the canvas narrow on the left, the Bios panel (its form holds the picker) wide beside it.
LAYOUT = {"v": 2, "panels": {
    "roles-graph": {"x": 0, "y": 0, "w": 9, "h": 86, "face": "detail", "collapsed": False},
    "roles-bios": {"x": 9, "y": 0, "w": 15, "h": 86, "face": "detail", "collapsed": False},
    **{pid: {"x": 9, "y": 66 + 5 * i, "w": 6, "h": 20, "face": "detail", "collapsed": True}
       for i, pid in enumerate(("roles-inspector", "roles-problems", "roles-lineups", "roles-models"))}}}


def ready(c, url: str) -> None:
    """Cast, the implementer's card selected, its bio's model picker opened, one row pointed at."""
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(url)
    c.js(f"localStorage.setItem('halo.studio.layout.roles', {json.dumps(json.dumps(LAYOUT))}); location.reload(); 1")
    time.sleep(1.0)
    bio = "document.querySelector('[data-testid=\"roles-bio\"][data-name=\"implementer\"]')"
    c.wait(f"!!{bio}", 40)
    c.js(f"{bio}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(bio)
    more = "document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"model-select\"]')"
    c.wait(f"!!{more}", 20)
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    picker = "document.querySelector('[data-testid=\"model-picker\"]')"
    c.wait(f"{picker}?.querySelectorAll('[data-testid=\"model-row\"]').length === {len(FIXTURE)}", 20)
    c.js("document.querySelector('[data-testid=\"bio-form\"]').scrollIntoView({block: 'start'}); 1")
    time.sleep(0.3)
    row = f"{picker}.querySelector('[data-testid=\"model-row\"][data-ref=\"{HOT}\"]')"
    x, y, w, h = c.rect(row)
    c.mouse("mouseMoved", x + w * 0.5, y + h / 2)  # the pointer on the row: it is highlighted and its detail line shows
    c.wait(f"{picker}.querySelector('[data-testid=\"model-detail\"]')?.dataset.ref === {json.dumps(HOT)}", 10)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    from halo_harness.studio import model as M
    placeholder(state)
    from halo_harness.agents_yaml import load_agent_bio_raw, save_agent_bio
    bio = {k: v for k, v in (load_agent_bio_raw("implementer", state_dir=state) or {}).items() if not str(k).startswith("_")}
    bio.setdefault("models", {})["preference"] = HOT  # the implementer already runs on a model: the picker shows it picked
    save_agent_bio("implementer", bio, state_dir=state)
    real = M.model_rows
    M.model_rows = lambda *_a, **_k: rows()
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=agents&view=cast&tour=off&feed=off&open=roles-inspector,roles-problems")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        M.model_rows = real
        print("no Chrome found")
        return 2
    try:
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=2, mobile=False)
        ready(c, url)
        guard_page(c, "picker")
        if as_dom:
            print(json.dumps({"picker": counts(c)}))
            return 0
        png = Path(out).resolve()
        size = c.shot(png)
        ok = size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {png} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.go("about:blank")
        c.close()
        srv.shutdown()
        srv.server_close()
        M.model_rows = real
