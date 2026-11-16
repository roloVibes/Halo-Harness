"""tests.helpers.studio_setup_done -- Setup's Done (Halo 3.3.3.0 R1, "Setup hands
off to halo"): the last step of the Setup pages driver (tests/helpers/
studio_setup_pages.py), over its fresh home with no provider. Real clicks in
headless Chrome; no provider request, no model call:

1. `?mode=setup&first=1`: the rail's line says "set up this box"; the
   Summary's foot is the primary "Done: start halo" with its title;
2. a click: the section is Session, nothing opens over it, Done and the
   rail's line are gone, `mode=setup` left the address, setup-done.json is in
   the seeded home with `at` and `home`;
3. the page loaded again at that address lands on Session (no provider set,
   and still not Setup: Done was pressed); `?mode=setup&first=1` again draws
   no "set up this box" (the state's `done_at`).
"""
from __future__ import annotations

import json

from tests.helpers.studio_packs_steps import CUR, q, qa

OPEN = ("[!!document.querySelector('[data-testid=section-help]'), !!document.querySelector('[data-testid=start-here]'), "
        "document.querySelectorAll('[role=dialog]').length]")
FIRST = "!!document.querySelector('[data-testid=setup-strip-first]')"


def done(c, url, ctx) -> dict:
    import os

    from tests.helpers.studio_setup_pages import STEP, _load, click, goto
    _load(c, ctx, "mode=setup&first=1&tour=off")
    out = {"done_first_before": c.wait(FIRST, 15)}
    # Local models only (fix): this home has no model a session can call, so the Summary offers no Done: one line
    # saying what is missing and one button to the page that fixes it (no dialog)
    goto(c, "summary")
    fix = q("[data-testid=setup-done-fix]")
    c.wait(f"!!{fix}", 20)
    out["missing_line"] = c.js(f"{q('[data-testid=setup-done-missing]')}?.textContent || ''")
    out["missing_done"] = c.js(f"!!{q('[data-testid=setup-done]')}")
    out["missing_dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    out["missing_fix"] = [c.js(f"{fix}.dataset.step"), c.js(f"{fix}.textContent")]
    click(c, fix, f"{STEP} !== 'summary'")
    out["missing_went"] = c.js(STEP)
    out.update(_ollama_host_only_rail(c, ctx))
    key = "OPENROUTER_API_KEY"  # a key (never sent: nothing calls a model here) makes the built-in default resolve
    saved = os.environ.get(key)
    os.environ[key] = "sk-or-v1-setup-done-pages-0123456789abcdef"
    try:
        return _done_pressed(c, ctx, out)
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved


def _ollama_host_only_rail(c, ctx) -> dict:
    """jb10 (local models only): an Ollama host (a dead port here, never a real Ollama) and no model: the rail ticks
    neither Providers nor Default model (the Summary refuses Done); the home's config.json is put back after."""
    from tests.helpers.studio_setup_pages import _load
    cfg = ctx["state"] / "config.json"
    before = cfg.read_text(encoding="utf-8") if cfg.is_file() else None
    data = json.loads(before) if before else {}
    data["ollama"] = {"hosts": [{"name": "default", "url": "http://127.0.0.1:9", "default": True}]}
    cfg.write_text(json.dumps(data), encoding="utf-8")
    try:
        _load(c, ctx, "mode=setup&block=check&tour=off")  # the page open is Check: the two steps read as ticked or not
        step ="[data-testid=setup-rail-step][data-step={}]"
        return {"ollama_only_rail": [c.js(f"{q(step.format(s))}?.dataset.state || ''") for s in ("providers", "model")]}
    finally:
        if before is None:
            cfg.unlink()
        else:
            cfg.write_text(before, encoding="utf-8")


def _done_pressed(c, ctx, out: dict) -> dict:
    from tests.helpers.studio_setup_pages import _load, click, goto
    _load(c, ctx, "mode=setup&first=1&tour=off")  # the state read again: a model now resolves
    goto(c, "summary")
    btn = q("[data-testid=setup-done]")
    c.wait(f"!!{btn}", 20)
    out["done_label"] = c.js(f"{btn}.textContent")
    out["done_title"] = c.js(f"{btn}.title")
    out["done_primary"] = c.js(f"{btn}.className")
    out["done_last"] = c.js(f"{qa('[data-testid=setup-summary] > section')}.map((s) => s.dataset.testid)")
    click(c, btn, f"{CUR}.startsWith('Session')")
    out["done_section"] = c.js(CUR)
    out["done_open"] = c.js(OPEN)
    out["done_gone"] = c.js(f"!{btn} || !{btn}.checkVisibility()")  # Setup stays mounted, hidden, once visited
    out["done_first_after"] = c.js(FIRST)
    out["done_search"] = c.js("location.search")
    marker = ctx["state"] / "setup-done.json"
    out["done_marker"] = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else None
    again = c.js("location.origin + location.pathname + location.search")
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(f"{again}#{ctx['frag']}")
    c.wait(f"!!{q('[data-testid=section-tab][aria-selected=true]')}", 40)
    out["done_reload_section"] = c.js(CUR)
    _load(c, ctx, "mode=setup&first=1&tour=off")
    c.wait(f"!!{q('[data-testid=setup-strip-cell]')}", 20)
    out["done_first_again"] = c.js(FIRST)
    return out
