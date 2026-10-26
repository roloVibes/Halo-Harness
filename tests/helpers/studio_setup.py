"""tests.helpers.studio_setup -- the Setup section checks of
tests/test_studio_setup.py (Halo 3.3.0.0 R1), real keys and clicks in headless
Chrome through the driver base, over a scratch home (capture_studio's
seeded_home: the shipped lineups, halo-dev-cycle active) with a stub catalog
of two models (studio/model.py model_rows); this process serves Studio in a
thread with the live feed on. No provider, no model call:

1. `?mode=setup` opens Setup; Alt+8 (from Roles) opens it too: Setup is the
   eighth tab, its strip names the provider, model, lineup, mode and theme,
   the four later blocks say "comes with R2 / R3", the rail lists the blocks;
2. Permissions: pick plan, the block says "1 changed", Save: config.json has
   it, the strip and the block say so;
3. Terminal theme: the six swatches, pick claude-light, Save: config.json;
4. Default model: the stub catalog grouped by provider, search narrows it,
   pick or:mock/beta, Save: config.json;
5. Team: pick balanced, its preview, Apply: `team` in config.json, the
   strip's lineup follows; One model for everything: team removed, roles off;
6. a `halo config set` from outside (config.json written here): the strip
   follows on the `files_changed` frame.

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
from tests.helpers.studio_packs_steps import CUR, TABS, alt, q, qa  # noqa: E402

ROWS = [{"ref": "or:mock/alpha", "provider": "openrouter", "detail": "Mock Alpha", "price": "$1.00", "context": "128k",
         "best_at": {"line": "code, review", "kinds": ["code"]}},
        {"ref": "or:mock/beta", "provider": "openrouter", "detail": "Mock Beta", "price": "$0.20", "context": "64k",
         "best_at": {"line": "summaries", "kinds": []}}]
STRIP = qa("[data-testid=setup-strip-cell]") + ".map((c) => [c.dataset.key, c.querySelector('.su-cell-value').textContent])"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def _cell(key: str) -> str:
    return _text(f"[data-testid=setup-strip-cell][data-key={key}] .su-cell-value")


def _config(ctx) -> dict:
    p = ctx["state"] / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def choose(c, row: str, check: str) -> str:
    """Click a row's label; when the pointer missed (the Linux runners), click its input itself. Returns how."""
    c.wait(f"!!{q(row)}", 20)
    c.js(f"{q(row)}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(q(row), 0.6, 0.5)
    try:
        c.wait(check, 4)
        return "pointer"
    except TimeoutError:
        c.js(f"{q(row + ' input')}.click(); 1")
        c.wait(check, 10)
        return "element"


def save(c, block: str, label: str = "") -> str:
    btn = q(f"[data-testid=setup-save][data-block={block}]")
    c.wait(f"!!{btn} && !{btn}.disabled", 10)
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(btn)
    word = _text(f"[data-testid=setup-word][data-block={block}]")
    try:
        c.wait(f"{word} === 'saved' && !!{q(f'[data-testid=setup-lines][data-block={block}]')}", 6)
        return "pointer"
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(f"{word} === 'saved' && !!{q(f'[data-testid=setup-lines][data-block={block}]')}", 15)
        return "element"


def by_mode(c, url, ctx) -> dict:
    c.go(url.replace("mode=roles", "mode=setup"))
    c.wait(f"{TABS}.length >= 8 && {CUR}.startsWith('Setup')", 40)
    c.wait(f"!!{q('[data-testid=setup-strip-cell]')}", 30)
    return {"mode_section": c.js(CUR), "mode_first_strip": c.js(STRIP)}


def section(c, url, ctx) -> dict:
    c.go(url)
    c.wait(f"{TABS}.length >= 8 && {CUR}.startsWith('Roles')", 40)
    out = {"tabs": c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)"),
           "kbds": c.js(f"{TABS}.map((t) => t.querySelector('.tab-kbd')?.textContent || '')")}
    alt(c, 8)
    out["alt8"] = c.wait(f"{CUR}.startsWith('Setup') && {CUR}", 15)
    c.wait(f"!!{q('[data-testid=setup-strip-cell]')} && {qa('[data-testid=setup-later]')}.length === 4", 30)
    out["strip"] = c.js(STRIP)
    out["later"] = c.js(qa("[data-testid=setup-later]") + ".map((p) => [p.dataset.block, p.textContent])")
    out["panels"] = c.js(f"{qa('[data-section=setup] .panel-title')}.map((t) => t.textContent)")
    out["rail"] = c.js(qa("[data-testid=setup-rail-block]") + ".map((b) => b.textContent)")
    out["modes"] = c.js(qa("[data-testid=setup-mode]") + ".map((m) => m.dataset.id)")
    out["theme_note"] = c.js(_text("[data-testid=setup-theme-note]"))
    return out


def permissions(c, url, ctx) -> dict:
    row = "[data-testid=setup-mode][data-id=plan]"
    out = {"mode_by": choose(c, row, f"{q(row + ' input')}.checked")}
    out["mode_word"] = c.wait(f"{_text('[data-testid=setup-word][data-block=permission_mode]')} === '1 changed' && 'changed'", 10)
    out["mode_save_by"] = save(c, "permission_mode")
    out["mode_lines"] = c.js(_text("[data-testid=setup-lines][data-block=permission_mode]"))
    out["mode_strip"] = c.wait(f"{_cell('permissions')} === 'plan' && {_cell('permissions')}", 10)
    out["mode_config"] = _config(ctx).get("permission_mode")
    return out


def theme(c, url, ctx) -> dict:
    row = "[data-testid=setup-theme-swatch][data-name=claude-light]"
    out = {"swatches": c.js(qa("[data-testid=setup-theme-swatch]") + ".map((s) => s.dataset.name)"),
           "swatch_bg": c.js(f"getComputedStyle({q(row + ' .su-sw-screen')}).backgroundColor"),
           "theme_by": choose(c, row, f"{q(row + ' input')}.checked")}
    out["theme_save_by"] = save(c, "theme")
    out["theme_strip"] = c.wait(f"{_cell('theme')} === 'claude-light' && {_cell('theme')}", 10)
    out["theme_config"] = _config(ctx).get("theme")
    return out


def model(c, url, ctx) -> dict:
    out = {"groups": c.js(qa("[data-testid=setup-model-group]") + ".map((g) => g.dataset.provider)"),
           "models": c.js(qa("[data-testid=setup-model-row]") + ".map((r) => r.dataset.ref)")}
    search = q("[data-testid=setup-model-search]")
    c.js(f"(() => {{ const s = {search}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
         f"set.call(s, 'summar'); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()")
    out["searched"] = c.wait(f"{qa('[data-testid=setup-model-row]')}.length === 1 && {qa('[data-testid=setup-model-row]')}.map((r) => r.dataset.ref)", 10)
    row = "[data-testid=setup-model-row][data-ref='or:mock/beta']"
    out["model_by"] = choose(c, row, f"{q(row + ' input')}.checked")
    out["model_save_by"] = save(c, "model")
    out["model_strip"] = c.wait(f"{_cell('model')} === 'or:mock/beta' && {_cell('model')}", 10)
    out["model_config"] = _config(ctx).get("model")
    return out


def team(c, url, ctx) -> dict:
    row = "[data-testid=setup-lineup][data-name=balanced]"
    out = {"lineups": c.js(qa("[data-testid=setup-lineup]") + ".map((r) => r.dataset.name)"),
           "in_use": c.js(qa("[data-testid=setup-lineup][data-active]") + ".map((r) => r.dataset.name)"),
           "team_by": choose(c, row, f"{q(row + ' input')}.checked")}
    out["preview"] = c.wait(f"{_text('[data-testid=setup-team-preview]')}.startsWith('balanced') && {_text('[data-testid=setup-team-preview]')}.split('\\n')[0]", 15)
    out["team_save_by"] = save(c, "team")
    out["team_strip"] = c.wait(f"{_cell('lineup')} === 'balanced' && {_cell('lineup')}", 10)
    cfg = _config(ctx)
    out["team_config"] = [cfg.get("team"), (cfg.get("roles") or {}).get("enabled")]
    one = "[data-testid=setup-lineup][data-name=one-model]"
    choose(c, one, f"{q(one + ' input')}.checked")
    save(c, "team")
    out["one_strip"] = c.wait(f"{_cell('lineup')} === 'one model for everything' && {_cell('lineup')}", 10)
    cfg = _config(ctx)
    out["one_config"] = ["team" in cfg, (cfg.get("roles") or {}).get("enabled")]
    return out


def outside(c, url, ctx) -> dict:
    """A write from outside the page (a `halo config set` in a terminal): the strip follows the frame."""
    from halo_harness.theme import set_config_value
    set_config_value("permission_mode", "acceptEdits")
    return {"outside_strip": c.wait(f"{_cell('permissions')} === 'acceptEdits' && {_cell('permissions')}", 20)}


class SetupDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.studio import model as M
        state = seeded_home()
        real = M.model_rows
        M.model_rows = lambda *_a, **_k: [dict(r) for r in ROWS]
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra&feed=off", "mode=roles&tour=off&view=workspace")
        ctx = {"state": state, "srv": srv}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (by_mode, section, permissions, theme, model, team, outside))
        finally:
            M.model_rows = real
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(SetupDriver(sys.argv[1:]).main())
