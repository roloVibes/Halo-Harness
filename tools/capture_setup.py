"""tools/capture_setup.py -- the Setup capture for tools/capture_studio.py
--mode setup (Halo 3.3.0.0 R4: the modes banner's eighth tile and the
README's first screenshot after install), through headless Chrome over the
DevTools protocol (tests/helpers/cdp.py), over the scratch home capture_studio
seeds (no model call, no network, no probe: BRIDGE_TEST_NO_BACKGROUND_NET):

    docs/media/studio-setup.png   Setup as `halo init` opens it (`?mode=setup&first=1`, the help kept shut with
                                  `tour=off`): the strip leading with "set up this box", OpenRouter set from the
                                  env file (a placeholder key), a default model of a two-row fixture catalog, the
                                  halo-dev-cycle lineup, acceptEdits, a last check that passed; the Providers and
                                  Local models blocks on top

With --dom the page is counted by data-testid (the last stdout line is the
JSON). Never two Chromes at once; every page is guarded before it is counted
or shot (tools/capture_identity.py: you@studio, no real path or name).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

IDS = ("section-tab", "setup-strip-first", "setup-strip-cell", "setup-rail-block", "setup-provider", "panel-about",
       "section-help", "start-here-setup")
ROWS = [{"ref": "or:demo/atlas-pro", "provider": "openrouter", "detail": "Atlas Pro (fixture)", "price": "$3.00", "context": "200k",
         "best_at": {"line": "code, review, plans", "kinds": ["code"]}},
        {"ref": "or:demo/atlas-mini", "provider": "openrouter", "detail": "Atlas Mini (fixture)", "price": "$0.30", "context": "128k",
         "best_at": {"line": "summaries, quick edits", "kinds": []}}]
KEY = "sk-or-capture-placeholder-0000"  # not a key: the card shows its last four as ****0000


def seed(state: Path) -> dict:
    """OpenRouter set from an env file in the scratch home, a default model, a mode, a passed last check."""
    from halo_harness.theme import set_config_value
    saved = {k: os.environ.get(k) for k in ("HALO_ENV_FILE", "OPENROUTER_API_KEY", "BRIDGE_TEST_NO_BACKGROUND_NET")}
    env_file = state.parent / "halo-env"
    env_file.write_text(f"OPENROUTER_API_KEY={KEY}\n", encoding="utf-8")
    os.environ.update({"HALO_ENV_FILE": str(env_file), "OPENROUTER_API_KEY": KEY, "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
    set_config_value("model", "or:demo/atlas-pro")
    set_config_value("permission_mode", "acceptEdits")
    results = [{"key": k, "title": t, "ok": True, "lines": [f"{t}: ok"]} for k, t in
               (("doctor", "Doctor"), ("catalog", "Model catalog"), ("hello", "Hello"))]
    last = state / "studio" / "last-check.json"
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(json.dumps({"when": time.time(), "ok": True, "results": results}), encoding="utf-8")
    return saved


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def ready(c, url: str) -> None:
    c.go(url)
    c.wait("(document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || '').startsWith('Setup')", 40)
    c.wait("!!document.querySelector('[data-testid=setup-strip-first]') && !!document.querySelector('[data-testid=setup-strip-cell]')", 30)
    c.wait("document.querySelectorAll('[data-testid=setup-provider]').length > 0", 20)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.0)


def capture(out: str, as_dom: bool, serve, state: Path) -> int:
    from tests.helpers.chrome_driver import open_chrome
    from halo_harness.studio import model as M
    placeholder(state)
    saved = seed(state)
    real = M.model_rows
    M.model_rows = lambda *_a, **_k: [dict(r) for r in ROWS]
    srv, url = serve(state)
    url = url.replace("mode=orchestra&feed=off", "mode=setup&first=1&tour=off&view=workspace&feed=off")
    c = open_chrome(1500, 900)
    if c is None:
        srv.shutdown()
        M.model_rows = real
        print("no Chrome found")
        return 2
    try:
        ready(c, url)
        guard_page(c, "setup")
        if as_dom:
            print(json.dumps({"setup": counts(c)}))
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
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
