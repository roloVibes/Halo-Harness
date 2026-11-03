"""tests.helpers.studio_setup_packs -- a pack's own Setup blocks (Halo 3.3.11.0 R3), real clicks in headless Chrome
through the driver base, over capture_studio's seeded home with the fixture pack setup-blocks installed (disabled
first, then enabled); a stub catalog of two models; no provider request, no model call:

1. the pack disabled: the rail is the core one (its steps counted), no pack name in it;
2. enabled: its three blocks in the rail -- the form right after Default model with the pack's name on it, the check
   and the note after the core steps under the pack's name, the Summary last;
3. the form saves (style long, depth 3: config.json's packs.settings.setup-blocks) and the rail says done;
4. the note: Mark as read -> done;
5. the Check page: a "From packs" line, the pack row unticked with its what / cost / time / writes line; ticked and
   run alone, it goes green through the job with its two lines, and the block is done;
6. the Summary lists the three with their state; `?block=pack:setup-blocks:reach` lands on that block.
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
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_setup_pages import STEP, _load, click, goto  # noqa: E402

PACK = "pack:setup-blocks"
RAIL = qa("[data-testid=setup-rail-step]") + ".map((b) => [b.dataset.step, b.dataset.state])"
TITLES = qa("[data-testid=setup-rail-step] .su-step-title") + ".map((t) => t.textContent)"
WORD = "(document.querySelector('[data-testid=setup-pack-state]')?.dataset.word || '')"


def rail_step(block: str) -> str:
    return q(f'[data-testid=setup-rail-step][data-step="{PACK}:{block}"]')


def goto_block(c, block: str) -> None:
    """studio_setup_pages.goto for a pack's step (its id has colons: the attribute is quoted)."""
    btn, page = rail_step(block), f"{STEP} === '{PACK}:{block}'"
    c.wait(f"!!{btn}", 30)
    c.click_on(btn)
    try:
        c.wait(page, 4)
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(page, 15)


def _setv(c, sel: str, value: str, proto: str = "HTMLSelectElement", ev: str = "change") -> None:
    c.wait(f"!!{q(sel)}", 15)
    c.js(f"(() => {{ const s = {q(sel)}; const set = Object.getOwnPropertyDescriptor({proto}.prototype, 'value').set; "
         f"set.call(s, {json.dumps(value)}); s.dispatchEvent(new Event({json.dumps(ev)}, {{bubbles: true}})); return 1; }})()")


def disabled_rail(c, url, ctx) -> dict:
    _load(c, ctx, "mode=setup&tour=off")
    out = {"off_rail": c.js(RAIL), "off_groups": c.js(f"{qa('[data-testid=setup-rail-pack]')}.length")}
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    ok, lines = enable(find("setup-blocks", cwd=ctx["proj"]))
    out["enable_lines"] = [ln for ln in lines if ln.startswith("setup: ")] if ok else lines
    return out


def enabled_rail(c, url, ctx) -> dict:
    _load(c, ctx, "mode=setup&tour=off")
    c.wait(f"{qa('[data-testid=setup-rail-step]')}.some((b) => b.dataset.step.startsWith('{PACK}'))", 30)
    return {"on_rail": c.js(RAIL), "on_titles": c.js(TITLES), "on_groups": c.js(f"{qa('[data-testid=setup-rail-pack]')}.map((g) => g.textContent)")}


def form(c, url, ctx) -> dict:
    goto_block(c, "prefs")
    out = {"form_title": c.wait(f"!!{q('[data-testid=pack-form]')} && {q('[data-testid=setup-page-title]')}.textContent", 20),
           "form_keys": c.js(f"{qa('[data-testid=setup-pack-form] [data-testid=pack-form-input]')}.map((i) => i.dataset.key)")}
    _setv(c, "[data-testid=setup-pack-form] select[data-key=style]", "long")
    _setv(c, "[data-testid=setup-pack-form] input[data-key=depth]", "3", "HTMLInputElement", "input")
    click(c, q("[data-testid=setup-pack-form] [data-testid=pack-form-save]"), f"{WORD} === 'done'")
    out["form_word"] = c.js(WORD)
    cfg = ctx["state"] / "config.json"
    out["form_saved"] = (json.loads(cfg.read_text(encoding="utf-8")).get("packs") or {}).get("settings") if cfg.is_file() else None
    return out


def note(c, url, ctx) -> dict:
    goto_block(c, "about")
    out = {"form_rail": c.wait(f"{rail_step('prefs')}.dataset.state === 'done' && 'done'", 10),  # the page left: done, not current
           "note_head": c.wait(f"{q('[data-testid=setup-pack-note] [role=heading]')}?.textContent || ''", 15)}
    click(c, q("[data-testid=setup-pack-dismiss]"), f"{WORD} === 'done'")
    out["note_word"] = c.js(WORD)
    return out


def check(c, url, ctx) -> dict:
    goto(c, "check")
    row = f'[data-testid=setup-check-row][data-key="{PACK}:reach"]'
    c.wait(f"!!{q(row)}", 20)
    out = {"from_packs": c.js(f"{q('[data-testid=setup-check-from-packs]')}?.textContent || ''"),
           "check_ticked": c.js(f"{q(row + ' [data-testid=setup-check-tick]')}.checked"),
           "check_detail": c.js(f"{q(row + ' .su-check-detail')}.textContent")}
    for key in ("doctor", "catalog", "hello"):  # this run: the pack's check alone
        box = q(f"[data-testid=setup-check-tick][data-key={key}]")
        if c.js(f"{box}.checked"):
            c.js(f"{box}.click(); 1")
    click(c, q(row + " [data-testid=setup-check-tick]"), f"{q(row + ' [data-testid=setup-check-tick]')}.checked")
    click(c, q("[data-testid=setup-check-run]"), f"{q(row)}.dataset.state === 'done' || {q(row)}.dataset.state === 'failed'")
    out["check_state"] = c.wait(f"{q(row)}.dataset.state === 'done' && {q(row)}.dataset.state", 30)
    out["check_log"] = c.wait(f"({q(row + ' [data-testid=setup-check-log]')}?.textContent || '').includes('answered') && "
                              f"{q(row + ' [data-testid=setup-check-log]')}.textContent", 15)
    out["check_rail"] = c.wait(f"{rail_step('reach')}.dataset.state === 'done' && 'done'", 20)
    return out


def summary(c, url, ctx) -> dict:
    goto(c, "summary")
    rows = qa("[data-testid=setup-summary-row]")
    c.wait(f"{rows}.some((r) => r.dataset.step.startsWith('{PACK}'))", 20)
    out = {"summary_packs": c.js(f"{rows}.filter((r) => r.dataset.step.startsWith('{PACK}')).map((r) => [r.dataset.step, r.dataset.state, "
                                 "r.querySelector('[data-testid=setup-summary-value]').textContent])")}
    _load(c, ctx, f"mode=setup&block={PACK}:reach&tour=off")
    out["door_page"] = c.wait(f"{STEP} === '{PACK}:reach' && {STEP}", 20)
    out["door_title"] = c.js(f"{q('[data-testid=setup-page-title]')}.textContent")
    return out


class SetupPacksDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.packs import registry
        from halo_harness.packs.install import install
        from halo_harness.studio import model as M
        from tests.helpers.packs_home import fixture
        from tests.helpers.studio_setup import ROWS
        state = seeded_home()
        proj = state.parent / "project"
        proj.mkdir(exist_ok=True)
        registry.invalidate()
        ok, lines = install(str(fixture("setup-blocks")), cwd=proj)
        assert ok, lines
        real = M.model_rows
        M.model_rows = lambda *_a, **_k: [dict(r) for r in ROWS]
        srv, url = serve(state, True, proj)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag, "proj": proj}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (disabled_rail, enabled_rail, form, note, check, summary))
        finally:
            M.model_rows = real
            srv.shutdown()
            srv.server_close()
            registry.invalidate()
            time.sleep(0.2)
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(SetupPacksDriver(sys.argv[1:]).main())
