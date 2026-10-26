"""tests.helpers.studio_setup_pages -- Setup one page at a time (Halo 3.3.1.0
R1), real keys and clicks in headless Chrome through the driver base, over a
fresh scratch home (capture_studio's seeded_home with `team` and `roles` unset,
no provider: the Start here overlay is due); a stub catalog of two models; no
provider request, no model call. `goto(c, step)` is the shared step the Setup
drivers (tests/helpers/studio_setup*.py) use to open a block's page first:

1. nothing opens on its own: `?mode=setup` and `?mode=setup&first=1` (no
   `tour=off`) have no help, no Start here, no dialog after 2 s; the overlay
   still shows on Roles (Alt+3); the help is one click away in the header;
2. no panel machinery on Setup: no panel, no panel list, no Arrange;
3. the rail: the steps in the wizard's order with their states;
4. Next from Providers to the Summary (Next before it says Summary), then
   Back to Providers (Back is off there); a rail jump; Ctrl+Right is Next;
5. Enter in the Permissions page's choice is its Save (config.json has it);
6. `?block=team` lands on Team; the Summary's rows and a Change jump;
7. the page remembered for this home; `?block=` wins over it;
8. the Ollama finders' disclosure is closed by default and opens.
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

STEP = "(document.querySelector('[data-testid=setup-step-page]')?.dataset.step || '')"
RAIL = qa("[data-testid=setup-rail-step]") + ".map((b) => [b.dataset.step, b.dataset.state])"
OPEN = ("[!!document.querySelector('[data-testid=section-help]'), !!document.querySelector('[data-testid=start-here]'), "
        "document.querySelectorAll('[role=dialog]').length]")


def goto(c, step: str) -> str:
    """Open Setup's page for `step` by its rail step and wait for it; the element's own click when the pointer missed."""
    btn = q(f"[data-testid=setup-rail-step][data-step={step}]")
    page = f"{STEP} === '{step}'"
    c.wait(f"!!{btn}", 30)
    c.click_on(btn)
    try:
        c.wait(page, 4)
        return "pointer"
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(page, 15)
        return "element"


def click(c, expr: str, done: str) -> None:
    c.wait(f"!!({expr}) && !({expr}).disabled", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)
    try:
        c.wait(done, 4)
    except TimeoutError:
        c.js(f"({expr})?.click(); 1")
        c.wait(done, 15)


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off#{ctx['frag']}"


def _load(c, ctx, query: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load (a door's words leave the address)
    c.go(_url(ctx, query))
    c.wait(f"{CUR}.startsWith('Setup') && !!{q('[data-testid=setup-rail-step]')} && !!{q('[data-testid=setup-strip-cell]')}", 40)


def nothing_opens(c, url, ctx) -> dict:
    out = {}
    for name, query in (("first", "mode=setup&first=1"), ("plain", "mode=setup")):  # plain last: `first=1` holds the offer back
        _load(c, ctx, query)
        time.sleep(2.0)
        out[f"open_{name}"] = c.js(OPEN)
        out[f"page_{name}"] = c.js(STEP)
        if name == "first":
            out["first_line"] = c.js(f"{q('[data-testid=setup-strip-first]')}?.textContent || ''")
    out["setup_panels"] = c.js(f"{qa('[data-section=setup] [data-panel]')}.length")
    out["rail_lists"] = c.js("[!!document.querySelector('.rail nav[aria-label=Panels]'), !!document.querySelector('[data-testid=layout-arrange]')]")
    click(c, q("[data-testid=section-help-btn]"), f"!!{q('[data-testid=section-help-item]')}")
    click(c, q("[data-testid=section-help-item]"), f"!!{q('[data-testid=section-help]')}")
    out["help_title"] = c.js(f"{q('[data-testid=section-help] .dialog-title')}?.textContent || ''")
    c.js(f"{q('[data-testid=section-help-ok]')}.click(); 1")
    c.wait(f"!{q('[data-testid=section-help]')}", 10)
    alt(c, 3)  # the other sections of this fresh home still get the offer
    out["roles_overlay"] = c.wait(f"{CUR}.startsWith('Roles') && !!{q('[data-testid=start-here]')}", 20)
    return out


def rail(c, url, ctx) -> dict:
    _load(c, ctx, "mode=setup&tour=off")
    return {"rail": c.js(RAIL), "rail_titles": c.js(qa("[data-testid=setup-rail-step] .su-step-title") + ".map((t) => t.textContent)")}


def walk(c, url, ctx) -> dict:
    nxt, back = q("[data-testid=setup-next]"), q("[data-testid=setup-back]")
    out = {"walk": [c.js(STEP)], "next_labels": [], "back_off_first": c.js(f"{back}.disabled")}
    for _ in range(12):
        if not c.js(f"!!{nxt}"):
            break
        out["next_labels"].append(c.js(f"{nxt}.textContent"))
        cur = c.js(STEP)
        click(c, nxt, f"{STEP} !== '{cur}'")
        out["walk"].append(c.js(STEP))
    out["summary_next"] = c.js(f"!!{nxt}")
    out["back_walk"] = [c.js(STEP)]
    for _ in range(12):
        if c.js(f"{back}.disabled"):
            break
        cur = c.js(STEP)
        click(c, back, f"{STEP} !== '{cur}'")
        out["back_walk"].append(c.js(STEP))
    out["jump_by"] = goto(c, "theme")
    out["jump"] = [c.js(STEP), c.js(f"{q('[data-testid=setup-rail-step][data-step=theme]')}.dataset.state")]
    c.js(f"{q('[data-testid=setup-step-page]')}.focus(); 1")
    mod_key(c, "ArrowRight", 39, 2, "ArrowRight")  # Ctrl+Right: Next
    out["ctrl_right"] = c.wait(f"{STEP} !== 'theme' && {STEP}", 10)
    return out


def enter_saves(c, url, ctx) -> dict:
    goto(c, "permissions")
    row = "[data-testid=setup-mode][data-id=plan]"
    click(c, q(row), f"{q(row + ' input')}.checked")
    c.js(f"{q(row + ' input')}.focus(); 1")
    c.key("Enter")
    word = f"({q('[data-testid=setup-word][data-block=permission_mode]')}?.textContent || '')"
    out = {"enter_word": c.wait(f"{word} === 'saved' && !!{q('[data-testid=setup-lines][data-block=permission_mode]')} && {word}", 15)}
    p = ctx["state"] / "config.json"
    out["enter_config"] = json.loads(p.read_text(encoding="utf-8")).get("permission_mode") if p.is_file() else None
    goto(c, "theme")
    out["permissions_after"] = c.js(f"{q('[data-testid=setup-rail-step][data-step=permissions]')}.dataset.state")
    return out


def block_and_summary(c, url, ctx) -> dict:
    _load(c, ctx, "mode=setup&block=team&tour=off")
    out = {"block_page": c.wait(f"{STEP} === 'team' && {STEP}", 15), "block_search": c.js("location.search")}
    goto(c, "summary")
    rows = qa("[data-testid=setup-summary-row]")
    c.wait(f"{rows}.length >= 7", 20)
    out["summary_rows"] = c.js(f"{rows}.map((r) => [r.dataset.step, r.dataset.state, r.querySelector('[data-testid=setup-summary-value]').textContent])")
    out["summary_run"] = c.js(f"{q('[data-testid=setup-summary-run]')}?.textContent || ''")
    out["summary_ticked"] = c.js(f"{q('[data-testid=setup-summary-check] .su-note')}?.textContent || ''")
    out["summary_last"] = c.js(f"{q('[data-testid=setup-summary-last]')}?.textContent || ''")
    out["summary_start"] = c.js(f"!!{q('[data-testid=setup-summary-run-start]')}")
    click(c, q("[data-testid=setup-summary-change][data-step=model]"), f"{STEP} === 'model'")
    out["change_page"] = c.js(STEP)
    goto(c, "summary")
    click(c, q("[data-testid=setup-summary-to-check]"), f"{STEP} === 'check'")
    out["to_check_page"] = c.js(STEP)
    return out


def remembered(c, url, ctx) -> dict:
    goto(c, "permissions")
    _load(c, ctx, "mode=setup&tour=off")
    out = {"remembered": c.wait(f"{STEP} === 'permissions' && {STEP}", 15)}
    _load(c, ctx, "mode=setup&block=check&tour=off")
    out["block_wins"] = c.wait(f"{STEP} === 'check' && {STEP}", 15)
    _load(c, ctx, "mode=setup&tour=off")
    out["door_remembered"] = c.wait(f"{STEP} === 'check' && {STEP}", 15)
    return out


def disclosure(c, url, ctx) -> dict:
    goto(c, "providers")
    box = q("[data-testid=setup-ollama-more]")
    find = q("[data-testid=setup-ollama-find]")
    c.wait(f"!!{box}", 20)
    out = {"more_closed": c.js(f"!{box}.open"), "find_hidden": c.js(f"!{find}.checkVisibility()")}
    click(c, f"{box}.querySelector('summary')", f"{box}.open")
    out["more_open"] = c.js(f"{box}.open")
    out["find_shown"] = c.wait(f"{find}.checkVisibility()", 10)
    return out


class PagesDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.studio import model as M
        from halo_harness.theme import unset_config_value
        from tests.helpers.studio_setup import ROWS
        state = seeded_home()
        unset_config_value("team")  # a fresh home: Start here is due
        unset_config_value("roles")
        real = M.model_rows
        M.model_rows = lambda *_a, **_k: [dict(r) for r in ROWS]
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (nothing_opens, rail, walk, enter_saves, block_and_summary, remembered, disclosure))
        finally:
            M.model_rows = real
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PagesDriver(sys.argv[1:]).main())
